"""Neuro-Air HB 3-28 (verbatim) — cumulative impact of two Qian'an steel plants on district AQ.

Original query evaluates the cumulative impact of two major steel enterprises in Qian'an —
Qian'an Jiujiang Wire Rod (company_id 2426) and Shougang Qian'an Steel (company_id 2452) — on
Qian'an District air quality (district_id 41) during 2025-07-01 to 2025-07-15. The validator
recomputes each plant's total flue-gas volume over the 15-day window, their combined total, and
the district's mean and peak AQI over the same window. GT recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

JIUJIANG = 2426
SHOUGANG = 2452
DISTRICT_ID = 41  # Qian'an
WIN_START = "2025-07-01 00:00:00"
WIN_END = "2025-07-16 00:00:00"


def _total(cid):
    v = pd.read_sql(
        text(
            f"SELECT SUM(exhaust_gas) AS v FROM hourly_polluting_company_emission "
            f"WHERE company_id = {cid} AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}'"
        ),
        engine,
    ).iloc[0]["v"]
    return float(v)


def validate_hb_3_28(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    tj, ts = _total(JIUJIANG), _total(SHOUGANG)
    d = pd.read_sql(
        text(
            f"SELECT AVG(aqi) AS mean_aqi, MAX(aqi) AS max_aqi FROM hourly_district_air_quality "
            f"WHERE district_id = {DISTRICT_ID} AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}'"
        ),
        engine,
    ).iloc[0]
    exp = {
        "total_flue_gas_jiujiang": tj,
        "total_flue_gas_shougang": ts,
        "combined_total_flue_gas": tj + ts,
        "district_mean_aqi": float(d["mean_aqi"]),
        "district_max_aqi": float(d["max_aqi"]),
    }
    checks = [
        ("total_flue_gas_jiujiang", "num", max(1.0, tj * 0.005)),
        ("total_flue_gas_shougang", "num", max(1.0, ts * 0.005)),
        ("combined_total_flue_gas", "num", max(1.0, (tj + ts) * 0.005)),
        ("district_mean_aqi", "num", 2.0),
        ("district_max_aqi", "num", 2.0),
    ]
    for var, kind, tol in checks:
        val = runtime.retrieve(var)
        if val is None:
            return ValidatorResult(False, f"{var} not set", variables_not_set=True)
        e = exp[var]
        if not is_finite_number(val) or not compare_numeric(float(val), float(e), tolerance=tol):
            return ValidatorResult(False, f"{var}={val!r}, expected ~{round(e,1)} (tol {round(tol,1)})")
    return ValidatorResult(True, f"Correct: combined flue gas={round(exp['combined_total_flue_gas'],0)}, district mean AQI={round(exp['district_mean_aqi'],1)}")


tools = []
variables = [
    Variable("total_flue_gas_jiujiang", None, "Total flue-gas volume of Qian'an Jiujiang Wire Rod over 2025-07-01 to 2025-07-15 (float)."),
    Variable("total_flue_gas_shougang", None, "Total flue-gas volume of Shougang Qian'an Steel over the window (float)."),
    Variable("combined_total_flue_gas", None, "Sum of the two plants' total flue-gas volume (float)."),
    Variable("district_mean_aqi", None, "Mean AQI of Qian'an District over the window (float)."),
    Variable("district_max_aqi", None, "Peak (max) hourly AQI of Qian'an District over the window (float)."),
]
validators = {"validate_hb_3_28": validate_hb_3_28}
