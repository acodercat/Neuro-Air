"""Neuro-Air HB 6-13 (verbatim) — rapid PM2.5 spike window at a school station.

Original query analyzes the rapid PM2.5 spike at Yongnian District Experimental High School
station (station_id 123) during 2025-06-12 10:00-16:00. The validator recomputes, over
[10:00, 16:00), that station's mean/max/min PM2.5 and the hour-of-day of the PM2.5 peak.
GT is recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

STATION_ID = 123
WIN_START = "2025-06-12 10:00:00"
WIN_END = "2025-06-12 16:00:00"


def validate_hb_6_13(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    r = pd.read_sql(
        text(
            f"SELECT AVG(pm2_5) AS mean_pm25, MAX(pm2_5) AS max_pm25, MIN(pm2_5) AS min_pm25 "
            f"FROM hourly_station_air_quality WHERE station_id = {STATION_ID} "
            f"AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}'"
        ),
        engine,
    ).iloc[0]
    # Accept ANY hour achieving the max pm2_5: on a tie there are several
    # legitimate "peak hours", so the validator must not demand one arbitrary pick.
    peak_hours = {
        int(h) for h in pd.read_sql(
            text(
                f"SELECT EXTRACT(HOUR FROM timestamp) AS hod FROM hourly_station_air_quality "
                f"WHERE station_id = {STATION_ID} AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}' "
                f"AND pm2_5 = (SELECT MAX(pm2_5) FROM hourly_station_air_quality "
                f"WHERE station_id = {STATION_ID} AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}')"
            ),
            engine,
        )["hod"]
    }
    exp = {
        "mean_pm25": float(r["mean_pm25"]),
        "max_pm25": float(r["max_pm25"]),
        "min_pm25": float(r["min_pm25"]),
    }
    checks = [
        ("mean_pm25", "num", 2.0), ("max_pm25", "num", 2.0), ("min_pm25", "num", 2.0),
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
    return ValidatorResult(True, f"Correct: PM2.5 spike mean={round(exp['mean_pm25'],1)} (min {round(exp['min_pm25'],0)}, max {round(exp['max_pm25'],0)}), peak hour in {sorted(peak_hours)}")


tools = []
variables = [
    Variable("mean_pm25", None, "Mean PM2.5 at station 123 over 2025-06-12 10:00-16:00 (float)."),
    Variable("max_pm25", None, "Peak (max) hourly PM2.5 over the window (float)."),
    Variable("min_pm25", None, "Minimum hourly PM2.5 over the window (float)."),
    Variable("peak_pm25_hour_of_day", None, "Hour-of-day (0-23) of the PM2.5 peak over the window (int)."),
]
validators = {"validate_hb_6_13": validate_hb_6_13}
