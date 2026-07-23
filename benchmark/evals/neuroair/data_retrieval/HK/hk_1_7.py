"""Neuro-Air HK 1-7 (verbatim) — Causeway Bay AQHI/PM2.5 profile for a day.

Original query analyzes hourly AQHI patterns at Causeway Bay station (station_id 17) on
2025-06-15. AQHI is a small integer whose daily maximum ties across many hours, so the
validator grades the mean and max AQHI plus the continuous PM2.5 mean and max (not a
fragile peak-hour). GT is recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HK.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

STATION_ID = 17
DAY = "2025-06-15"


def validate_hk_1_7(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    r = pd.read_sql(
        text(
            f"SELECT AVG(aqhi) AS mean_aqhi, MAX(aqhi) AS max_aqhi, AVG(pm2_5) AS mean_pm25, MAX(pm2_5) AS max_pm25 "
            f"FROM hourly_station_air_quality WHERE station_id = {STATION_ID} "
            f"AND datetime >= '{DAY}' AND datetime < '{DAY}'::date + 1"
        ),
        engine,
    ).iloc[0]
    exp = {
        "mean_aqhi": float(r["mean_aqhi"]),
        "max_aqhi": float(r["max_aqhi"]),
        "mean_pm25": float(r["mean_pm25"]),
        "max_pm25": float(r["max_pm25"]),
    }
    checks = [("mean_aqhi", 0.2), ("max_aqhi", 0.5), ("mean_pm25", 1.0), ("max_pm25", 1.0)]
    for var, tol in checks:
        val = runtime.retrieve(var)
        if val is None:
            return ValidatorResult(False, f"{var} not set", variables_not_set=True)
        if not is_finite_number(val) or not compare_numeric(float(val), float(exp[var]), tolerance=tol):
            return ValidatorResult(False, f"{var}={val!r}, expected ~{round(exp[var],2)} (tol {tol})")
    return ValidatorResult(True, f"Correct: mean AQHI={round(exp['mean_aqhi'],2)}, max AQHI={round(exp['max_aqhi'],0)}, mean PM2.5={round(exp['mean_pm25'],1)}")


tools = []
variables = [
    Variable("mean_aqhi", None, "Mean AQHI at Causeway Bay station 17 on 2025-06-15 (float)."),
    Variable("max_aqhi", None, "Maximum AQHI at station 17 that day (float)."),
    Variable("mean_pm25", None, "Mean PM2.5 at station 17 that day (float)."),
    Variable("max_pm25", None, "Peak (max) hourly PM2.5 at station 17 that day (float)."),
]
validators = {"validate_hk_1_7": validate_hk_1_7}
