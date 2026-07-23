"""Neuro-Air HB 1-9 (verbatim) — daily air-quality profile at Construction Building station.

Original query analyzes the pollution situation at Construction Building station (name
建设大厦, station_id 86) on 2025-06-02. The validator recomputes that day's profile: mean/peak
PM2.5, mean AQI, and exceedance hours (PM2.5>75). The PM2.5 daily peak is tied across hours
that day, so the peak-hour is intentionally not graded. GT recomputed from the DB.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

STATION_ID = 86
DAY = "2025-06-02"


def validate_hb_1_9(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    r = pd.read_sql(
        text(
            f"SELECT AVG(pm2_5) AS mean_pm25, MAX(pm2_5) AS max_pm25, AVG(aqi) AS mean_aqi, "
            f"COUNT(*) FILTER (WHERE pm2_5 > 75) AS exceedance_hours FROM hourly_station_air_quality "
            f"WHERE station_id = {STATION_ID} AND timestamp >= '{DAY}' AND timestamp < '{DAY}'::date + 1"
        ),
        engine,
    ).iloc[0]
    exp = {
        "mean_pm25": float(r["mean_pm25"]),
        "max_pm25": float(r["max_pm25"]),
        "mean_aqi": float(r["mean_aqi"]),
        "exceedance_hours": int(r["exceedance_hours"]),
    }
    checks = [("mean_pm25", "num", 2.0), ("max_pm25", "num", 2.0), ("mean_aqi", "num", 2.0), ("exceedance_hours", "int", 0)]
    for var, kind, tol in checks:
        val = runtime.retrieve(var)
        if val is None:
            return ValidatorResult(False, f"{var} not set", variables_not_set=True)
        e = exp[var]
        if kind == "int":
            if not is_finite_number(val) or int(val) != int(e):
                return ValidatorResult(False, f"{var}={val!r}, expected {e}")
        else:
            if not is_finite_number(val) or not compare_numeric(float(val), float(e), tolerance=tol):
                return ValidatorResult(False, f"{var}={val!r}, expected ~{round(e,1)} (tol {tol})")
    return ValidatorResult(True, f"Correct: mean PM2.5={round(exp['mean_pm25'],1)}, mean AQI={round(exp['mean_aqi'],1)}, {exp['exceedance_hours']} exceedance hours")


tools = []
variables = [
    Variable("mean_pm25", None, "Mean PM2.5 at Construction Building station on 2025-06-02 (float)."),
    Variable("max_pm25", None, "Peak (max) hourly PM2.5 that day (float)."),
    Variable("mean_aqi", None, "Mean AQI that day (float)."),
    Variable("exceedance_hours", None, "Hours with PM2.5 > 75 that day (int)."),
]
validators = {"validate_hb_1_9": validate_hb_1_9}
