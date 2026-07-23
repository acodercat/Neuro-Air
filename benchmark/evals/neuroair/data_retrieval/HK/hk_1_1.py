"""Neuro-Air HK 1-1 (verbatim) — network-wide air quality during Chinese New Year.

Original query asks how Hong Kong's air quality typically changes during Chinese New Year
(2025-01-28 to 2025-02-02) and whether it improves. The validator recomputes the network-wide
(all stations) AQ over that period: mean/peak PM2.5 and mean/peak AQHI. GT recomputed from the DB.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HK.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

WIN_START = "2025-01-28 00:00:00"
WIN_END = "2025-02-03 00:00:00"


def validate_hk_1_1(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    r = pd.read_sql(
        text(
            f"SELECT AVG(pm2_5) AS mean_pm25, MAX(pm2_5) AS max_pm25, AVG(aqhi) AS mean_aqhi, MAX(aqhi) AS max_aqhi "
            f"FROM hourly_station_air_quality WHERE datetime >= '{WIN_START}' AND datetime < '{WIN_END}'"
        ),
        engine,
    ).iloc[0]
    exp = {
        "net_mean_pm25": float(r["mean_pm25"]),
        "net_max_pm25": float(r["max_pm25"]),
        "net_mean_aqhi": float(r["mean_aqhi"]),
        "net_max_aqhi": float(r["max_aqhi"]),
    }
    for var, tol in [("net_mean_pm25", 1.0), ("net_max_pm25", 1.5), ("net_mean_aqhi", 0.2), ("net_max_aqhi", 0.5)]:
        val = runtime.retrieve(var)
        if val is None:
            return ValidatorResult(False, f"{var} not set", variables_not_set=True)
        if not is_finite_number(val) or not compare_numeric(float(val), float(exp[var]), tolerance=tol):
            return ValidatorResult(False, f"{var}={val!r}, expected ~{round(exp[var],2)} (tol {tol})")
    return ValidatorResult(True, f"Correct: CNY network mean PM2.5={round(exp['net_mean_pm25'],1)}, mean AQHI={round(exp['net_mean_aqhi'],2)}")


tools = []
variables = [
    Variable("net_mean_pm25", None, "Network-wide mean PM2.5 across all HK stations over 2025-01-28 to 2025-02-02 (float)."),
    Variable("net_max_pm25", None, "Network-wide peak (max) hourly PM2.5 over the period (float)."),
    Variable("net_mean_aqhi", None, "Network-wide mean AQHI over the period (float)."),
    Variable("net_max_aqhi", None, "Network-wide maximum AQHI over the period (float)."),
]
validators = {"validate_hk_1_1": validate_hk_1_1}
