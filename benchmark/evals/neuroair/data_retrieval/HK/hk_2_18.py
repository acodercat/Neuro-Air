"""Neuro-Air HK 2-18 (verbatim) — PM2.5 profile at station 2.
Recomputes station 2's profile over 2025-05-12: mean/max PM2.5 plus mean and max AQHI.
GT is recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HK.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

STATION_ID = 2
WIN_START = "2025-05-12 00:00:00"
WIN_END = "2025-05-13 00:00:00"


def validate_hk_2_18(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    r = pd.read_sql(text(f"SELECT AVG(pm2_5) AS m, MAX(pm2_5) AS x, AVG(aqhi) AS qa, MAX(aqhi) AS qx FROM hourly_station_air_quality WHERE station_id = {STATION_ID} AND datetime >= '{WIN_START}' AND datetime < '{WIN_END}'"), engine).iloc[0]
    exp = {"mean_pm2_5": float(r["m"]), "max_pm2_5": float(r["x"]), "mean_aqhi": float(r["qa"]), "max_aqhi": float(r["qx"])}
    for var, tol in [("mean_pm2_5", 1.0), ("max_pm2_5", 1.5), ("mean_aqhi", 0.2), ("max_aqhi", 0.5)]:
        val = runtime.retrieve(var)
        if val is None:
            return ValidatorResult(False, f"{var} not set", variables_not_set=True)
        if not is_finite_number(val) or not compare_numeric(float(val), float(exp[var]), tolerance=tol):
            return ValidatorResult(False, f"{var}={val!r}, expected ~{round(exp[var],2)} (tol {tol})")
    return ValidatorResult(True, f"Correct: mean PM2.5={round(exp['mean_pm2_5'],1)}, max AQHI={round(exp['max_aqhi'],0)}")


tools = []
variables = [
    Variable("mean_pm2_5", None, "Mean PM2.5 at station 2 over 2025-05-12 (float)."),
    Variable("max_pm2_5", None, "Peak (max) hourly PM2.5 over the window (float)."),
    Variable("mean_aqhi", None, "Mean AQHI at station 2 over the window (float)."),
    Variable("max_aqhi", None, "Maximum AQHI over the window (float)."),
]
validators = {"validate_hk_2_18": validate_hk_2_18}
