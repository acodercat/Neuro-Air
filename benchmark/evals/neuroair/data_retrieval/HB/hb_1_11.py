"""Neuro-Air HB 1-11 (verbatim) — city-level air-quality profile for Tangshan.

Original query analyzes the air-quality patterns in Tangshan City (city_id 2) on 2025-06-02.
The validator recomputes that day's city-level profile from hourly_city_air_quality: mean/max
AQI, peak PM2.5, and the hour-of-day of the AQI peak. GT recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

CITY_ID = 2  # Tangshan
DAY = "2025-06-02"


def validate_hb_1_11(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    r = pd.read_sql(
        text(
            f"SELECT AVG(aqi) AS mean_aqi, MAX(aqi) AS max_aqi, MAX(pm2_5) AS max_pm25 "
            f"FROM hourly_city_air_quality WHERE city_id = {CITY_ID} "
            f"AND timestamp >= '{DAY}' AND timestamp < '{DAY}'::date + 1"
        ),
        engine,
    ).iloc[0]
    # Accept ANY hour achieving the max aqi: on a tie there are several
    # legitimate "peak hours", so the validator must not demand one arbitrary pick.
    peak_hours = {
        int(h) for h in pd.read_sql(
            text(
                f"SELECT EXTRACT(HOUR FROM timestamp) AS hod FROM hourly_city_air_quality "
                f"WHERE city_id = {CITY_ID} AND timestamp >= '{DAY}' AND timestamp < '{DAY}'::date + 1 "
                f"AND aqi = (SELECT MAX(aqi) FROM hourly_city_air_quality "
                f"WHERE city_id = {CITY_ID} AND timestamp >= '{DAY}' AND timestamp < '{DAY}'::date + 1)"
            ),
            engine,
        )["hod"]
    }
    exp = {
        "mean_aqi": float(r["mean_aqi"]),
        "max_aqi": float(r["max_aqi"]),
        "max_pm25": float(r["max_pm25"]),
    }
    checks = [("mean_aqi", "num", 2.0), ("max_aqi", "num", 2.0), ("max_pm25", "num", 2.0)]
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
    pk = runtime.retrieve("peak_aqi_hour_of_day")
    if pk is None:
        return ValidatorResult(False, "peak_aqi_hour_of_day not set", variables_not_set=True)
    if not is_finite_number(pk) or int(pk) not in peak_hours:
        return ValidatorResult(False, f"peak_aqi_hour_of_day={pk!r}, expected one of {sorted(peak_hours)}")
    return ValidatorResult(True, f"Correct: mean AQI={round(exp['mean_aqi'],1)}, max AQI={round(exp['max_aqi'],0)}, peak at hour {sorted(peak_hours)}")


tools = []
variables = [
    Variable("mean_aqi", None, "Mean city AQI for Tangshan on 2025-06-02 (float)."),
    Variable("max_aqi", None, "Maximum hourly city AQI that day (float)."),
    Variable("max_pm25", None, "Peak (max) hourly city PM2.5 that day (float)."),
    Variable("peak_aqi_hour_of_day", None, "Hour-of-day (0-23) of the city AQI peak (int)."),
]
validators = {"validate_hb_1_11": validate_hb_1_11}
