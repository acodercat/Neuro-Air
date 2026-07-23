"""Neuro-Air HB 1-26 (verbatim) — most consistent emission performer among three plants.

Original query identifies the most consistent emission performer among Hebei Puyang Steel
(company_id 2495), Tangshan Ruifeng Steel (2420) and Tangshan Ganglu Steel (2443) on
2025-06-10. "Consistent" is operationalised as the lowest coefficient of variation (CV =
population std / mean) of hourly exhaust_gas that day. The validator recomputes each CV and
the company with the lowest. GT is recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

COMPANIES = {"puyang": 2495, "ruifeng": 2420, "ganglu": 2443}
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


def validate_hb_1_26(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    cvs = {name: _cv(cid) for name, cid in COMPANIES.items()}
    most_consistent = COMPANIES[min(cvs, key=lambda k: cvs[k])]

    exp = {
        "cv_puyang": cvs["puyang"],
        "cv_ruifeng": cvs["ruifeng"],
        "cv_ganglu": cvs["ganglu"],
        "most_consistent_company_id": most_consistent,
    }
    for var, tol in [("cv_puyang", 0.005), ("cv_ruifeng", 0.005), ("cv_ganglu", 0.005)]:
        val = runtime.retrieve(var)
        if val is None:
            return ValidatorResult(False, f"{var} not set", variables_not_set=True)
        if not is_finite_number(val) or not compare_numeric(float(val), float(exp[var]), tolerance=tol):
            return ValidatorResult(False, f"{var}={val!r}, expected ~{round(exp[var],4)} (tol {tol})")
    mc = runtime.retrieve("most_consistent_company_id")
    if mc is None:
        return ValidatorResult(False, "most_consistent_company_id not set", variables_not_set=True)
    if not is_finite_number(mc) or int(mc) != most_consistent:
        return ValidatorResult(False, f"most_consistent_company_id={mc!r}, expected {most_consistent}")
    return ValidatorResult(True, f"Correct: most consistent = company {most_consistent} (CV {round(min(cvs.values()),4)})")


tools = []
variables = [
    Variable("cv_puyang", None, "Coefficient of variation (std/mean) of hourly flue-gas for Hebei Puyang Steel on 2025-06-10 (float)."),
    Variable("cv_ruifeng", None, "CV of hourly flue-gas for Tangshan Ruifeng Steel that day (float)."),
    Variable("cv_ganglu", None, "CV of hourly flue-gas for Tangshan Ganglu Steel that day (float)."),
    Variable("most_consistent_company_id", None, "The company_id of the lowest-CV company = most consistent (int)."),
]
validators = {"validate_hb_1_26": validate_hb_1_26}
