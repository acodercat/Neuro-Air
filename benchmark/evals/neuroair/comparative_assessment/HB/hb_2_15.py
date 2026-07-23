"""Neuro-Air HB 2-15 (verbatim) — district air-quality comparison in Shijiazhuang.

Original query compares air-quality spatial patterns between Qiaoxi District and Xinhua
District, focusing on PM2.5 and NO2, over 2025-08-01 to 2025-08-05. Both are Shijiazhuang
(city 1) districts: Qiaoxi = district_id 2, Xinhua = district_id 3. The validator recomputes
each district's mean PM2.5 and mean NO2 over that window. GT recomputed from the DB.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

QIAOXI = 2
XINHUA = 3
WIN_START = "2025-08-01 00:00:00"
WIN_END = "2025-08-06 00:00:00"


def _means(did):
    r = pd.read_sql(
        text(
            f"SELECT AVG(pm2_5) AS pm, AVG(no2) AS no2 FROM hourly_district_air_quality "
            f"WHERE district_id = {did} AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}'"
        ),
        engine,
    ).iloc[0]
    return float(r["pm"]), float(r["no2"])


def validate_hb_2_15(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    q_pm, q_no2 = _means(QIAOXI)
    x_pm, x_no2 = _means(XINHUA)
    exp = {
        "mean_pm25_qiaoxi": q_pm, "mean_no2_qiaoxi": q_no2,
        "mean_pm25_xinhua": x_pm, "mean_no2_xinhua": x_no2,
    }
    for var, tol in [("mean_pm25_qiaoxi", 1.0), ("mean_no2_qiaoxi", 1.0), ("mean_pm25_xinhua", 1.0), ("mean_no2_xinhua", 1.0)]:
        val = runtime.retrieve(var)
        if val is None:
            return ValidatorResult(False, f"{var} not set", variables_not_set=True)
        if not is_finite_number(val) or not compare_numeric(float(val), float(exp[var]), tolerance=tol):
            return ValidatorResult(False, f"{var}={val!r}, expected ~{round(exp[var],2)} (tol {tol})")
    return ValidatorResult(True, f"Correct: Qiaoxi PM2.5={round(q_pm,1)}/NO2={round(q_no2,1)}, Xinhua PM2.5={round(x_pm,1)}/NO2={round(x_no2,1)}")


tools = []
variables = [
    Variable("mean_pm25_qiaoxi", None, "Mean PM2.5 in Qiaoxi District, 2025-08-01 to 2025-08-05 (float)."),
    Variable("mean_no2_qiaoxi", None, "Mean NO2 in Qiaoxi district over the window (float)."),
    Variable("mean_pm25_xinhua", None, "Mean PM2.5 in Xinhua District over the window (float)."),
    Variable("mean_no2_xinhua", None, "Mean NO2 in Xinhua district over the window (float)."),
]
validators = {"validate_hb_2_15": validate_hb_2_15}
