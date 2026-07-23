"""Neuro-Air HB 3-14 (verbatim) — air-quality profile at station 65 on a single day.

Original query analyzes the multi-variate relationship between OSM features, enterprise
emissions and air quality at coastal Oilfield Employee Hospital station (station_id 65)
on 2025-07-03. The objective air-quality anchor the validator recomputes is that
station's daily profile: mean/peak PM2.5, mean AQI, exceedance hours (PM2.5>75) and the
hour-of-day of the PM2.5 peak. GT is recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

STATION_ID = 65
DAY_START = "2025-07-03 00:00:00"
DAY_END = "2025-07-04 00:00:00"


def validate_hb_3_14(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    r = pd.read_sql(
        text(
            f"SELECT AVG(pm2_5) AS mean_pm25, MAX(pm2_5) AS max_pm25, AVG(aqi) AS mean_aqi, "
            f"COUNT(*) FILTER (WHERE pm2_5 > 75) AS exceedance_hours "
            f"FROM hourly_station_air_quality WHERE station_id = {STATION_ID} "
            f"AND timestamp >= '{DAY_START}' AND timestamp < '{DAY_END}'"
        ),
        engine,
    ).iloc[0]
    # Accept ANY hour achieving the max pm2_5: on a tie there are several
    # legitimate "peak hours", so the validator must not demand one arbitrary pick.
    peak_hours = {
        int(h) for h in pd.read_sql(
            text(
                f"SELECT EXTRACT(HOUR FROM timestamp) AS hod FROM hourly_station_air_quality "
                f"WHERE station_id = {STATION_ID} AND timestamp >= '{DAY_START}' AND timestamp < '{DAY_END}' "
                f"AND pm2_5 = (SELECT MAX(pm2_5) FROM hourly_station_air_quality "
                f"WHERE station_id = {STATION_ID} AND timestamp >= '{DAY_START}' AND timestamp < '{DAY_END}')"
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
    return ValidatorResult(True, f"Correct: mean PM2.5={round(exp['mean_pm25'],1)}, peak at hour {sorted(peak_hours)}")


tools = []
variables = [
    Variable("mean_pm25", None, "Mean PM2.5 at station 65 on 2025-07-03 (float)."),
    Variable("max_pm25", None, "Peak (max) hourly PM2.5 at station 65 that day (float)."),
    Variable("mean_aqi", None, "Mean AQI at station 65 that day (float)."),
    Variable("exceedance_hours", None, "Hours with PM2.5 > 75 at station 65 that day (int)."),
    Variable("peak_pm25_hour_of_day", None, "Hour-of-day (0-23) of the PM2.5 peak (int)."),
]
validators = {"validate_hb_3_14": validate_hb_3_14}
