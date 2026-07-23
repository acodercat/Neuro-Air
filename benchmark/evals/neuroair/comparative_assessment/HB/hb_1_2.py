"""Neuro-Air HB 1-2 (verbatim) — NOx emission comparison between two steel plants.

Original query analyzes NOx emissions between Jingye Metallurgical Technology (company_id
2417) and Hebei Yanshan Steel Group (company_id 2418) on 2025-06-08. The validator recomputes
each plant's total and mean hourly NOx that day and the higher-NOx company. GT recomputed from DB.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

JINGYE = 2417
YANSHAN = 2418
DAY = "2025-06-08"


def _nox(cid):
    r = pd.read_sql(
        text(
            f"SELECT SUM(nox) AS total, AVG(nox) AS mean FROM hourly_polluting_company_emission "
            f"WHERE company_id = {cid} AND timestamp >= '{DAY}' AND timestamp < '{DAY}'::date + 1"
        ),
        engine,
    ).iloc[0]
    return float(r["total"]), float(r["mean"])


def validate_hb_1_2(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    jt, jm = _nox(JINGYE)
    yt, ym = _nox(YANSHAN)
    higher = JINGYE if jt > yt else YANSHAN
    exp = {"total_nox_jingye": jt, "mean_nox_jingye": jm, "total_nox_yanshan": yt, "mean_nox_yanshan": ym,
           "higher_nox_company_id": higher}
    for var, tol in [("total_nox_jingye", max(1.0, jt * 0.005)), ("mean_nox_jingye", max(0.5, jm * 0.005)),
                     ("total_nox_yanshan", max(1.0, yt * 0.005)), ("mean_nox_yanshan", max(0.5, ym * 0.005))]:
        val = runtime.retrieve(var)
        if val is None:
            return ValidatorResult(False, f"{var} not set", variables_not_set=True)
        if not is_finite_number(val) or not compare_numeric(float(val), float(exp[var]), tolerance=tol):
            return ValidatorResult(False, f"{var}={val!r}, expected ~{round(exp[var],1)}")
    hc = runtime.retrieve("higher_nox_company_id")
    if hc is None:
        return ValidatorResult(False, "higher_nox_company_id not set", variables_not_set=True)
    if not is_finite_number(hc) or int(hc) != higher:
        return ValidatorResult(False, f"higher_nox_company_id={hc!r}, expected {higher}")
    return ValidatorResult(True, f"Correct: Jingye NOx total={round(jt,0)} vs Yanshan={round(yt,0)}, higher = company {higher}")


tools = []
variables = [
    Variable("total_nox_jingye", None, "Total NOx of Jingye Metallurgical Technology on 2025-06-08 (float)."),
    Variable("mean_nox_jingye", None, "Mean hourly NOx of Jingye that day (float)."),
    Variable("total_nox_yanshan", None, "Total NOx of Hebei Yanshan Steel Group that day (float)."),
    Variable("mean_nox_yanshan", None, "Mean hourly NOx of Yanshan that day (float)."),
    Variable("higher_nox_company_id", None, "The company_id of the higher-NOx company (int)."),
]
validators = {"validate_hb_1_2": validate_hb_1_2}
