"""Neuro-Air HB 7-29 (verbatim) — PM2.5 episode profile at a railway station.

Original query does source attribution for high PM2.5 episodes at Railway station
(station_id 272) on 2025-07-05. The objective anchor the validator recomputes is that
day's PM2.5 episode profile: mean/peak PM2.5, mean AQI, exceedance hours (PM2.5>75), and
the hour-of-day of the peak. GT is recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

STATION_ID = 272
DAY = "2025-07-05"


def validate_hb_7_29(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    r = pd.read_sql(
        text(
            f"SELECT AVG(pm2_5) AS mean_pm25, MAX(pm2_5) AS max_pm25, AVG(aqi) AS mean_aqi, "
            f"COUNT(*) FILTER (WHERE pm2_5 > 75) AS exceedance_hours FROM hourly_station_air_quality "
            f"WHERE station_id = {STATION_ID} AND timestamp >= '{DAY}' AND timestamp < '{DAY}'::date + 1"
        ),
        engine,
    ).iloc[0]
    # Accept ANY hour achieving the max pm2_5: on a tie there are several
    # legitimate "peak hours", so the validator must not demand one arbitrary pick.
    peak_hours = {
        int(h) for h in pd.read_sql(
            text(
                f"SELECT EXTRACT(HOUR FROM timestamp) AS hod FROM hourly_station_air_quality "
                f"WHERE station_id = {STATION_ID} AND timestamp >= '{DAY}' AND timestamp < '{DAY}'::date + 1 "
                f"AND pm2_5 = (SELECT MAX(pm2_5) FROM hourly_station_air_quality "
                f"WHERE station_id = {STATION_ID} AND timestamp >= '{DAY}' AND timestamp < '{DAY}'::date + 1)"
            ),
            engine,
        )["hod"]
    }

    exp = {
        "mean_pm25": float(r["mean_pm25"]),
        "max_pm25": float(r["max_pm25"]),
        "mean_aqi": float(r["mean_aqi"]),
        "exceedance_hours": int(r["exceedance_hours"]),
    }
    checks = [
        ("mean_pm25", "num", 2.0), ("max_pm25", "num", 2.0), ("mean_aqi", "num", 2.0),
        ("exceedance_hours", "int", 0),
    ]
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
    pk = runtime.retrieve("peak_pm25_hour_of_day")
    if pk is None:
        return ValidatorResult(False, "peak_pm25_hour_of_day not set", variables_not_set=True)
    if not is_finite_number(pk) or int(pk) not in peak_hours:
        return ValidatorResult(False, f"peak_pm25_hour_of_day={pk!r}, expected one of {sorted(peak_hours)}")
    return ValidatorResult(True, f"Correct: mean PM2.5={round(exp['mean_pm25'],1)}, peak hour in {sorted(peak_hours)}")


tools = []
variables = [
    Variable("mean_pm25", None, "Mean PM2.5 at station 272 on 2025-07-05 (float)."),
    Variable("max_pm25", None, "Peak (max) hourly PM2.5 that day (float)."),
    Variable("mean_aqi", None, "Mean AQI that day (float)."),
    Variable("exceedance_hours", None, "Hours with PM2.5 > 75 that day (int)."),
    Variable("peak_pm25_hour_of_day", None, "Hour-of-day (0-23) of the PM2.5 peak (int)."),
]
validators = {"validate_hb_7_29": validate_hb_7_29}
