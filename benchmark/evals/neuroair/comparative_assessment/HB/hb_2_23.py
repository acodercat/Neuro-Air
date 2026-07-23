"""Neuro-Air HB 2-23 (verbatim) — urban-to-rural pollution transmission gradient.

Original query assesses pollution transmission from urban districts (Chang'an, Qiaoxi) to rural
Gaoyi County on 2025-06-18. All three are in Shijiazhuang: Chang'an = district_id 1, Qiaoxi =
district_id 2, Gaoyi County = district_id 13. The validator recomputes each district's daily
mean AQI and the urban-to-rural difference (mean of the two urban districts minus Gaoyi). GT
recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

CHANGAN = 1
QIAOXI = 2
GAOYI = 13
DAY = "2025-06-18"


def _mean(did):
    v = pd.read_sql(
        text(
            f"SELECT AVG(aqi) AS v FROM hourly_district_air_quality "
            f"WHERE district_id = {did} AND timestamp >= '{DAY}' AND timestamp < '{DAY}'::date + 1"
        ),
        engine,
    ).iloc[0]["v"]
    return float(v)


def validate_hb_2_23(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    ca, qx, gy = _mean(CHANGAN), _mean(QIAOXI), _mean(GAOYI)
    diff = (ca + qx) / 2 - gy
    exp = {"mean_aqi_changan": ca, "mean_aqi_qiaoxi": qx, "mean_aqi_gaoyi": gy, "urban_to_rural_diff": diff}
    for var, tol in [("mean_aqi_changan", 1.0), ("mean_aqi_qiaoxi", 1.0), ("mean_aqi_gaoyi", 1.0), ("urban_to_rural_diff", 1.5)]:
        val = runtime.retrieve(var)
        if val is None:
            return ValidatorResult(False, f"{var} not set", variables_not_set=True)
        if not is_finite_number(val) or not compare_numeric(float(val), float(exp[var]), tolerance=tol):
            return ValidatorResult(False, f"{var}={val!r}, expected ~{round(exp[var],2)} (tol {tol})")
    return ValidatorResult(True, f"Correct: urban Chang'an={round(ca,1)}/Qiaoxi={round(qx,1)} vs rural Gaoyi={round(gy,1)} (diff {round(diff,1)})")


tools = []
variables = [
    Variable("mean_aqi_changan", None, "Mean AQI in Chang'an District on 2025-06-18 (float)."),
    Variable("mean_aqi_qiaoxi", None, "Mean AQI in Qiaoxi District that day (float)."),
    Variable("mean_aqi_gaoyi", None, "Mean AQI in rural Gaoyi County that day (float)."),
    Variable("urban_to_rural_diff", None, "Mean AQI of the two urban districts minus Gaoyi (float)."),
]
validators = {"validate_hb_2_23": validate_hb_2_23}
