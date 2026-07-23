"""Neuro-Air HB 2-2 (verbatim) — weekly county air quality and spatial consistency.

Original query evaluates weekly air-quality trends in Zanhuang County (district_id 15) from
2025-06-01 to 2025-06-07, analyzing spatial consistency across monitoring points. The validator
recomputes both dimensions: the county's district-level AQI over the week (mean/peak, exceedance
hours) AND the spatial consistency across the county's stations (station count and the population
std of per-station mean AQI). GT is recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

DISTRICT_ID = 15  # Zanhuang County
WIN_START = "2025-06-01 00:00:00"
WIN_END = "2025-06-08 00:00:00"


def validate_hb_2_2(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    r = pd.read_sql(
        text(
            f"SELECT AVG(aqi) AS mean_aqi, MAX(aqi) AS max_aqi, "
            f"COUNT(*) FILTER (WHERE aqi > 100) AS exceedance_hours FROM hourly_district_air_quality "
            f"WHERE district_id = {DISTRICT_ID} AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}'"
        ),
        engine,
    ).iloc[0]
    stn = pd.read_sql(
        text(
            f"SELECT station_id, AVG(aqi) AS m FROM hourly_station_air_quality "
            f"WHERE station_id IN (SELECT id FROM air_quality_station WHERE district_id = {DISTRICT_ID}) "
            f"AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}' GROUP BY station_id"
        ),
        engine,
    )
    means = stn["m"].astype(float)
    exp = {
        "mean_aqi": float(r["mean_aqi"]),
        "max_aqi": float(r["max_aqi"]),
        "exceedance_hours": int(r["exceedance_hours"]),
        "n_stations": int(len(stn)),
        "spatial_std_aqi": float(means.std(ddof=0)),
    }
    checks = [
        ("mean_aqi", "num", 2.0), ("max_aqi", "num", 2.0), ("exceedance_hours", "int", 0),
        ("n_stations", "int", 0), ("spatial_std_aqi", "num", 0.5),
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
                return ValidatorResult(False, f"{var}={val!r}, expected ~{round(e,2)} (tol {tol})")
    return ValidatorResult(True, f"Correct: weekly mean AQI={round(exp['mean_aqi'],1)}, {exp['n_stations']} stations, spatial std={round(exp['spatial_std_aqi'],2)}")


tools = []
variables = [
    Variable("mean_aqi", None, "Mean district-level AQI for Zanhuang County over 2025-06-01 to 2025-06-07 (float)."),
    Variable("max_aqi", None, "Peak (max) hourly AQI over the week (float)."),
    Variable("exceedance_hours", None, "Hours with AQI > 100 over the week (int)."),
    Variable("n_stations", None, "Number of monitoring points (stations) in Zanhuang County with data (int)."),
    Variable("spatial_std_aqi", None, "Spatial consistency: population std of per-station mean AQI across the county's stations (float)."),
]
validators = {"validate_hb_2_2": validate_hb_2_2}
