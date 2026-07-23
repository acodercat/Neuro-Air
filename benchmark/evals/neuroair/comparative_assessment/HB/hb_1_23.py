"""Neuro-Air HB 1-23 (verbatim) — emission comparison between two large steel plants.

Original query compares emission patterns between Shougang Jingtang Steel (company_id 2444)
and Hangang Group Hanbao Steel (company_id 2611) on 2025-06-10. The validator recomputes each
plant's total flue-gas volume that day, which is higher, and the ratio. GT recomputed from DB.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

A = 2444
B = 2611
DAY = "2025-06-10"


def _total(cid):
    v = pd.read_sql(
        text(
            f"SELECT SUM(exhaust_gas) AS v FROM hourly_polluting_company_emission "
            f"WHERE company_id = {cid} AND timestamp >= '{DAY}' AND timestamp < '{DAY}'::date + 1"
        ),
        engine,
    ).iloc[0]["v"]
    return float(v)


def validate_hb_1_23(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    ta, tb = _total(A), _total(B)
    higher = A if ta > tb else B
    ratio = round(max(ta, tb) / min(ta, tb), 2)
    exp = {"total_flue_gas_jingtang": ta, "total_flue_gas_hanbao": tb, "higher_emitter_company_id": higher, "emission_ratio": ratio}
    for var, tol in [("total_flue_gas_jingtang", max(1.0, ta * 0.005)), ("total_flue_gas_hanbao", max(1.0, tb * 0.005)), ("emission_ratio", 0.2)]:
        val = runtime.retrieve(var)
        if val is None:
            return ValidatorResult(False, f"{var} not set", variables_not_set=True)
        if not is_finite_number(val) or not compare_numeric(float(val), float(exp[var]), tolerance=tol):
            return ValidatorResult(False, f"{var}={val!r}, expected ~{round(exp[var],2)}")
    he = runtime.retrieve("higher_emitter_company_id")
    if he is None:
        return ValidatorResult(False, "higher_emitter_company_id not set", variables_not_set=True)
    if not is_finite_number(he) or int(he) != higher:
        return ValidatorResult(False, f"higher_emitter_company_id={he!r}, expected {higher}")
    return ValidatorResult(True, f"Correct: company {A}={round(ta,0)} vs {B}={round(tb,0)}, higher={higher} (x{ratio})")


tools = []
variables = [
    Variable("total_flue_gas_jingtang", None, "Total flue-gas volume of Shougang Jingtang Steel on 2025-06-10 (float)."),
    Variable("total_flue_gas_hanbao", None, "Total flue-gas volume of Hangang Group Hanbao Steel that day (float)."),
    Variable("higher_emitter_company_id", None, "The company_id of the company that emitted more (int)."),
    Variable("emission_ratio", None, "Higher total divided by lower total (float, 2dp)."),
]
validators = {"validate_hb_1_23": validate_hb_1_23}
