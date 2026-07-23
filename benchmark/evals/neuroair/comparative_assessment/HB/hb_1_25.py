"""Neuro-Air HB 1-25 (verbatim) — emission variability/stability between two steel plants.

Original query analyzes emission variability and stability between Hebei Taihang Steel Group
(company_id 2447) and Hegang Leting Steel (company_id 2412) on 2025-06-10. Stability is
operationalised as the coefficient of variation (population std / mean) of hourly exhaust_gas.
The validator recomputes each CV and the more stable (lower-CV) company. GT recomputed from DB.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

TAIHANG = 2447
LETING = 2412
DAY = "2025-06-10"


def _cv(cid):
    r = pd.read_sql(
        text(
            f"SELECT AVG(exhaust_gas) AS m, STDDEV_POP(exhaust_gas) AS sd FROM hourly_polluting_company_emission "
            f"WHERE company_id = {cid} AND timestamp >= '{DAY}' AND timestamp < '{DAY}'::date + 1"
        ),
        engine,
    ).iloc[0]
    return float(r["sd"]) / float(r["m"])


def validate_hb_1_25(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    cv_t, cv_l = _cv(TAIHANG), _cv(LETING)
    more_stable = TAIHANG if cv_t < cv_l else LETING
    exp = {"cv_taihang": cv_t, "cv_leting": cv_l, "more_stable_company_id": more_stable}
    for var, tol in [("cv_taihang", 0.005), ("cv_leting", 0.005)]:
        val = runtime.retrieve(var)
        if val is None:
            return ValidatorResult(False, f"{var} not set", variables_not_set=True)
        if not is_finite_number(val) or not compare_numeric(float(val), float(exp[var]), tolerance=tol):
            return ValidatorResult(False, f"{var}={val!r}, expected ~{round(exp[var],4)}")
    ms = runtime.retrieve("more_stable_company_id")
    if ms is None:
        return ValidatorResult(False, "more_stable_company_id not set", variables_not_set=True)
    if not is_finite_number(ms) or int(ms) != more_stable:
        return ValidatorResult(False, f"more_stable_company_id={ms!r}, expected {more_stable}")
    return ValidatorResult(True, f"Correct: CV Taihang={round(cv_t,4)} vs Leting={round(cv_l,4)}, more stable = company {more_stable}")


tools = []
variables = [
    Variable("cv_taihang", None, "Coefficient of variation of hourly flue-gas for Hebei Taihang Steel Group on 2025-06-10 (float)."),
    Variable("cv_leting", None, "CV of hourly flue-gas for Hegang Leting Steel that day (float)."),
    Variable("more_stable_company_id", None, "The company_id of the lower-CV company = more stable (int)."),
]
validators = {"validate_hb_1_25": validate_hb_1_25}
