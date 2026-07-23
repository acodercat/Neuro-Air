"""Neuro-Air HB 2-21 (verbatim) — county air-quality comparison in Shijiazhuang.

Original query compares spatial pollution patterns between Zhengding County and Xingtang
County on 2025-06-20. Both are Shijiazhuang (city 1) districts: Zhengding = district_id 10,
Xingtang = district_id 11. The validator recomputes each county's daily mean PM2.5 and mean
NO2 that day. GT is recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

ZHENGDING = 10
XINGTANG = 11
DAY = "2025-06-20"


def _means(did):
    r = pd.read_sql(
        text(
            f"SELECT AVG(pm2_5) AS pm, AVG(no2) AS no2 FROM hourly_district_air_quality "
            f"WHERE district_id = {did} AND timestamp >= '{DAY}' AND timestamp < '{DAY}'::date + 1"
        ),
        engine,
    ).iloc[0]
    return float(r["pm"]), float(r["no2"])


def validate_hb_2_21(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    z_pm, z_no2 = _means(ZHENGDING)
    x_pm, x_no2 = _means(XINGTANG)
    exp = {
        "mean_pm25_zhengding": z_pm, "mean_no2_zhengding": z_no2,
        "mean_pm25_xingtang": x_pm, "mean_no2_xingtang": x_no2,
    }
    for var, tol in [("mean_pm25_zhengding", 1.0), ("mean_no2_zhengding", 1.0), ("mean_pm25_xingtang", 1.0), ("mean_no2_xingtang", 1.0)]:
        val = runtime.retrieve(var)
        if val is None:
            return ValidatorResult(False, f"{var} not set", variables_not_set=True)
        if not is_finite_number(val) or not compare_numeric(float(val), float(exp[var]), tolerance=tol):
            return ValidatorResult(False, f"{var}={val!r}, expected ~{round(exp[var],2)} (tol {tol})")
    return ValidatorResult(True, f"Correct: Zhengding PM2.5={round(z_pm,1)}/NO2={round(z_no2,1)}, Xingtang PM2.5={round(x_pm,1)}/NO2={round(x_no2,1)}")


tools = []
variables = [
    Variable("mean_pm25_zhengding", None, "Mean PM2.5 in Zhengding County on 2025-06-20 (float)."),
    Variable("mean_no2_zhengding", None, "Mean NO2 in Zhengding County that day (float)."),
    Variable("mean_pm25_xingtang", None, "Mean PM2.5 in Xingtang County that day (float)."),
    Variable("mean_no2_xingtang", None, "Mean NO2 in Xingtang County that day (float)."),
]
validators = {"validate_hb_2_21": validate_hb_2_21}
