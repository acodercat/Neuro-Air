"""Neuro-Air HB 2-16 (verbatim) — spatial air-quality heterogeneity within a district.

Original query analyzes air-quality spatial heterogeneity within Yuhua District (district_id 5)
over 2025-06-25 12:00 to 2025-06-26 12:00. Heterogeneity is operationalised as the population
standard deviation of the per-station mean AQI across all stations in the district over the
window. The validator recomputes the station count, that spatial std, the district-wide mean
AQI, and the highest single-station mean AQI. GT recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

DISTRICT_ID = 5  # Yuhua
WIN_START = "2025-06-25 12:00:00"
WIN_END = "2025-06-26 12:00:00"


def validate_hb_2_16(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    df = pd.read_sql(
        text(
            f"SELECT station_id, AVG(aqi) AS m FROM hourly_station_air_quality "
            f"WHERE station_id IN (SELECT id FROM air_quality_station WHERE district_id = {DISTRICT_ID}) "
            f"AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}' GROUP BY station_id"
        ),
        engine,
    )
    means = df["m"].astype(float)
    exp = {
        "n_stations": int(len(df)),
        "spatial_std_aqi": float(means.std(ddof=0)),
        "district_mean_aqi": float(means.mean()),
        "max_station_mean_aqi": float(means.max()),
    }
    checks = [
        ("n_stations", "int", 0),
        ("spatial_std_aqi", "num", 0.5),
        ("district_mean_aqi", "num", 2.0),
        ("max_station_mean_aqi", "num", 2.0),
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
    return ValidatorResult(True, f"Correct: {exp['n_stations']} stations, spatial std AQI={round(exp['spatial_std_aqi'],2)}, district mean={round(exp['district_mean_aqi'],1)}")


tools = []
variables = [
    Variable("n_stations", None, "Number of air-quality stations in Yuhua District with data over the window (int)."),
    Variable("spatial_std_aqi", None, "Population std of per-station mean AQI across the district's stations (float)."),
    Variable("district_mean_aqi", None, "Mean of the per-station mean AQI across the district (float)."),
    Variable("max_station_mean_aqi", None, "Highest single-station mean AQI in the district over the window (float)."),
]
validators = {"validate_hb_2_16": validate_hb_2_16}
