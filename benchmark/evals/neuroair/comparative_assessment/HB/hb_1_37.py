"""Neuro-Air HB 1-37 (verbatim) — three-zone Spring-Festival fireworks impact.

Original query compares PM2.5/PM10/AQI across coastal Wenmingli (station 87),
mountainous Pingquan (station 284) and urban Southwest Higher Education (station 1)
over the fireworks window 2025-01-28 18:00 -> 2025-01-29 06:00, and asks which zone
suffers the strongest impact. The validator recomputes, per station, the peak (max)
PM2.5 and the mean AQI over that window, and the station with the highest peak PM2.5
(the "strongest impact" answer). GT is recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

WIN_START = "2025-01-28 18:00:00"
WIN_END = "2025-01-29 06:00:00"
STATIONS = {87: "coastal", 284: "mountain", 1: "urban"}


def _per_station():
    rows = {}
    for sid in STATIONS:
        r = pd.read_sql(
            text(
                f"SELECT MAX(pm2_5) AS max_pm25, AVG(aqi) AS mean_aqi "
                f"FROM hourly_station_air_quality WHERE station_id = {sid} "
                f"AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}'"
            ),
            engine,
        ).iloc[0]
        rows[sid] = (float(r["max_pm25"]), float(r["mean_aqi"]))
    return rows


def validate_hb_1_37(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    rows = _per_station()
    strongest = max(rows, key=lambda s: rows[s][0])  # highest peak PM2.5

    exp = {"strongest_impact_station_id": strongest}
    for sid in STATIONS:
        exp[f"max_pm25_s{sid}"] = rows[sid][0]
        exp[f"mean_aqi_s{sid}"] = rows[sid][1]

    checks = [
        ("max_pm25_s87", "num", 2.0), ("max_pm25_s284", "num", 2.0), ("max_pm25_s1", "num", 2.0),
        ("mean_aqi_s87", "num", 2.0), ("mean_aqi_s284", "num", 2.0), ("mean_aqi_s1", "num", 2.0),
        ("strongest_impact_station_id", "int", 0),
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
    return ValidatorResult(True, f"Correct: strongest impact = station {strongest} (peak PM2.5={round(exp['max_pm25_s'+str(strongest)],1)})")


tools = []
variables = [
    Variable("max_pm25_s87", None, "Peak (max) hourly PM2.5 at coastal Wenmingli station 87 over the fireworks window (float)."),
    Variable("max_pm25_s284", None, "Peak (max) hourly PM2.5 at mountainous Pingquan station 284 over the window (float)."),
    Variable("max_pm25_s1", None, "Peak (max) hourly PM2.5 at urban Southwest Higher Education station 1 over the window (float)."),
    Variable("mean_aqi_s87", None, "Mean AQI at station 87 over the window (float)."),
    Variable("mean_aqi_s284", None, "Mean AQI at station 284 over the window (float)."),
    Variable("mean_aqi_s1", None, "Mean AQI at station 1 over the window (float)."),
    Variable("strongest_impact_station_id", None, "station number (87/284/1) with the highest peak PM2.5 = strongest fireworks impact (int)."),
]
validators = {"validate_hb_1_37": validate_hb_1_37}
