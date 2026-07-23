"""Neuro-Air HB 3-18 (verbatim) — PM10 profile at a thermal station over a daytime window.

Original query analyzes the combined impact of industrial emissions and meteorology on
PM10 at Zhengding Street Thermal Station (station_id 60) during 2025-06-08 08:00-18:00.
The objective PM10 anchor the validator recomputes over that window is: mean/peak PM10,
mean AQI, and the whole-hour offset from 08:00 to the PM10 peak. GT is recomputed from
the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

STATION_ID = 60
WIN_START = "2025-06-08 08:00:00"
WIN_END = "2025-06-08 18:00:00"


def validate_hb_3_18(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    r = pd.read_sql(
        text(
            f"SELECT AVG(pm10) AS mean_pm10, MAX(pm10) AS max_pm10, AVG(aqi) AS mean_aqi "
            f"FROM hourly_station_air_quality WHERE station_id = {STATION_ID} "
            f"AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}'"
        ),
        engine,
    ).iloc[0]
    # Accept ANY offset achieving the max pm10: on a tie there are several
    # legitimate "peak" hours, so the validator must not demand one arbitrary pick.
    peak_offsets = {
        int(round(float(o))) for o in pd.read_sql(
            text(
                f"SELECT EXTRACT(EPOCH FROM (timestamp - TIMESTAMP '{WIN_START}'))/3600 AS off_h "
                f"FROM hourly_station_air_quality WHERE station_id = {STATION_ID} "
                f"AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}' "
                f"AND pm10 = (SELECT MAX(pm10) FROM hourly_station_air_quality "
                f"WHERE station_id = {STATION_ID} AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}')"
            ),
            engine,
        )["off_h"]
    }

    exp = {
        "mean_pm10": float(r["mean_pm10"]),
        "max_pm10": float(r["max_pm10"]),
        "mean_aqi": float(r["mean_aqi"]),
    }
    checks = [
        ("mean_pm10", "num", 2.0), ("max_pm10", "num", 2.0), ("mean_aqi", "num", 2.0),
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
    pk = runtime.retrieve("peak_pm10_offset_hours")
    if pk is None:
        return ValidatorResult(False, "peak_pm10_offset_hours not set", variables_not_set=True)
    if not is_finite_number(pk) or int(pk) not in peak_offsets:
        return ValidatorResult(False, f"peak_pm10_offset_hours={pk!r}, expected one of {sorted(peak_offsets)}")
    return ValidatorResult(True, f"Correct: mean PM10={round(exp['mean_pm10'],1)}, peak at +{min(peak_offsets)}h")


tools = []
variables = [
    Variable("mean_pm10", None, "Mean PM10 at station 60 over 2025-06-08 08:00-18:00 (float)."),
    Variable("max_pm10", None, "Peak (max) hourly PM10 over the window (float)."),
    Variable("mean_aqi", None, "Mean AQI over the window (float)."),
    Variable("peak_pm10_offset_hours", None, "Whole hours from 08:00 to the PM10 peak (int)."),
]
validators = {"validate_hb_3_18": validate_hb_3_18}
