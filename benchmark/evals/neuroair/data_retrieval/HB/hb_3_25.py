"""Neuro-Air HB 3-25 (verbatim) — daily district air-quality profile for a county.

Original query examines the pollution causes affecting Jingxing County (district_id 9) on
2025-06-30. The objective anchor the validator recomputes is the county's district-level AQI
profile that day: mean/peak AQI, exceedance hours (AQI>100), and the hour-of-day of the AQI
peak. GT is recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

DISTRICT_ID = 9  # Jingxing County
DAY = "2025-06-30"


def validate_hb_3_25(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    r = pd.read_sql(
        text(
            f"SELECT AVG(aqi) AS mean_aqi, MAX(aqi) AS max_aqi, "
            f"COUNT(*) FILTER (WHERE aqi > 100) AS exceedance_hours FROM hourly_district_air_quality "
            f"WHERE district_id = {DISTRICT_ID} AND timestamp >= '{DAY}' AND timestamp < '{DAY}'::date + 1"
        ),
        engine,
    ).iloc[0]
    # Accept ANY hour achieving the max aqi: on a tie there are several
    # legitimate "peak hours", so the validator must not demand one arbitrary pick.
    peak_hours = {
        int(h) for h in pd.read_sql(
            text(
                f"SELECT EXTRACT(HOUR FROM timestamp) AS hod FROM hourly_district_air_quality "
                f"WHERE district_id = {DISTRICT_ID} AND timestamp >= '{DAY}' AND timestamp < '{DAY}'::date + 1 "
                f"AND aqi = (SELECT MAX(aqi) FROM hourly_district_air_quality "
                f"WHERE district_id = {DISTRICT_ID} AND timestamp >= '{DAY}' AND timestamp < '{DAY}'::date + 1)"
            ),
            engine,
        )["hod"]
    }
    exp = {
        "mean_aqi": float(r["mean_aqi"]),
        "max_aqi": float(r["max_aqi"]),
        "exceedance_hours": int(r["exceedance_hours"]),
    }
    checks = [("mean_aqi", "num", 2.0), ("max_aqi", "num", 2.0), ("exceedance_hours", "int", 0)]
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
    return ValidatorResult(True, f"Correct: mean AQI={round(exp['mean_aqi'],1)}, peak {round(exp['max_aqi'],0)} at hour {sorted(peak_hours)}, {exp['exceedance_hours']} exceedance hours")


tools = []
variables = [
    Variable("mean_aqi", None, "Mean district-level AQI for Jingxing County on 2025-06-30 (float)."),
    Variable("max_aqi", None, "Peak (max) hourly AQI that day (float)."),
    Variable("exceedance_hours", None, "Hours with AQI > 100 that day (int)."),
    Variable("peak_aqi_hour_of_day", None, "Hour-of-day (0-23) of the AQI peak (int)."),
]
validators = {"validate_hb_3_25": validate_hb_3_25}
