"""Neuro-Air HB 3-21 (verbatim) — PM10 spike characterization at a school station.

Original query identifies emission sources for the PM10 spike at Luquan No.1 Middle
School (station_id 48) on 2025-04-09 23:00. The objective anchor the validator recomputes
is the spike itself: PM10 at 23:00, the daily maximum PM10, the daily mean, and the
hour-of-day of the peak. GT is recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

STATION_ID = 48
DAY = "2025-04-09"


def validate_hb_3_21(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    r = pd.read_sql(
        text(
            f"SELECT MAX(pm10) AS daily_max_pm10, AVG(pm10) AS mean_pm10 FROM hourly_station_air_quality "
            f"WHERE station_id = {STATION_ID} AND timestamp >= '{DAY}' AND timestamp < '{DAY}'::date + 1"
        ),
        engine,
    ).iloc[0]
    v23 = pd.read_sql(
        text(f"SELECT pm10 FROM hourly_station_air_quality WHERE station_id = {STATION_ID} AND timestamp = '{DAY} 23:00:00'"),
        engine,
    )
    # Accept ANY hour achieving the max pm10: on a tie there are several
    # legitimate "peak hours", so the validator must not demand one arbitrary pick.
    peak_hours = {
        int(h) for h in pd.read_sql(
            text(
                f"SELECT EXTRACT(HOUR FROM timestamp) AS hod FROM hourly_station_air_quality "
                f"WHERE station_id = {STATION_ID} AND timestamp >= '{DAY}' AND timestamp < '{DAY}'::date + 1 "
                f"AND pm10 = (SELECT MAX(pm10) FROM hourly_station_air_quality "
                f"WHERE station_id = {STATION_ID} AND timestamp >= '{DAY}' AND timestamp < '{DAY}'::date + 1)"
            ),
            engine,
        )["hod"]
    }
    if v23.empty:
        return ValidatorResult(False, "no PM10 reading at 23:00")

    exp = {
        "pm10_at_2300": float(v23["pm10"].iloc[0]),
        "daily_max_pm10": float(r["daily_max_pm10"]),
        "mean_pm10": float(r["mean_pm10"]),
    }
    checks = [
        ("pm10_at_2300", "num", 2.0), ("daily_max_pm10", "num", 2.0),
        ("mean_pm10", "num", 2.0),
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
    pk = runtime.retrieve("peak_pm10_hour_of_day")
    if pk is None:
        return ValidatorResult(False, "peak_pm10_hour_of_day not set", variables_not_set=True)
    if not is_finite_number(pk) or int(pk) not in peak_hours:
        return ValidatorResult(False, f"peak_pm10_hour_of_day={pk!r}, expected one of {sorted(peak_hours)}")
    return ValidatorResult(True, f"Correct: PM10 at 23:00={round(exp['pm10_at_2300'],0)}, daily max={round(exp['daily_max_pm10'],0)} at hour {sorted(peak_hours)}")


tools = []
variables = [
    Variable("pm10_at_2300", None, "PM10 at station 48 at 2025-04-09 23:00 (float)."),
    Variable("daily_max_pm10", None, "Daily maximum PM10 at station 48 on 2025-04-09 (float)."),
    Variable("mean_pm10", None, "Daily mean PM10 that day (float)."),
    Variable("peak_pm10_hour_of_day", None, "Hour-of-day (0-23) of the PM10 peak (int)."),
]
validators = {"validate_hb_3_21": validate_hb_3_21}
