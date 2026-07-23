"""Neuro-Air HB 7-13 (verbatim) — a steel plant's afternoon emissions and its neighbourhood.

Original query analyzes how Shougang Jingtang Steel (company_id 2444) emissions on
2025-06-06 between 14:00-18:00 affected surrounding air quality. The validator recomputes
the source's total and peak flue-gas volume over that window, the number of air-quality
stations within 10km, and the mean PM2.5 across those nearby stations over the window. GT
is recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

COMPANY_ID = 2444
WIN_START = "2025-06-06 14:00:00"
WIN_END = "2025-06-06 18:00:00"


def validate_hb_7_13(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    em = pd.read_sql(
        text(
            f"SELECT SUM(exhaust_gas) AS total_flue_gas, MAX(exhaust_gas) AS peak_flue_gas "
            f"FROM hourly_polluting_company_emission WHERE company_id = {COMPANY_ID} "
            f"AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}'"
        ),
        engine,
    ).iloc[0]
    n10 = int(
        pd.read_sql(
            text(
                f"SELECT COUNT(*) AS c FROM air_quality_station s, polluting_company p "
                f"WHERE p.id = {COMPANY_ID} AND ST_DWithin(s.coordinate, p.coordinate, 10000)"
            ),
            engine,
        ).iloc[0]["c"]
    )
    nearby = pd.read_sql(
        text(
            f"SELECT AVG(a.pm2_5) AS v FROM hourly_station_air_quality a "
            f"JOIN air_quality_station s ON a.station_id = s.id, polluting_company p "
            f"WHERE p.id = {COMPANY_ID} AND ST_DWithin(s.coordinate, p.coordinate, 10000) "
            f"AND a.timestamp >= '{WIN_START}' AND a.timestamp < '{WIN_END}'"
        ),
        engine,
    ).iloc[0]["v"]

    exp = {
        "total_flue_gas": float(em["total_flue_gas"]),
        "peak_flue_gas": float(em["peak_flue_gas"]),
        "stations_within_10km": n10,
        "nearby_mean_pm25": float(nearby),
    }
    checks = [
        ("total_flue_gas", "num", max(1.0, exp["total_flue_gas"] * 0.005)),
        ("peak_flue_gas", "num", max(1.0, exp["peak_flue_gas"] * 0.005)),
        ("stations_within_10km", "int", 0),
        ("nearby_mean_pm25", "num", 2.0),
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
                return ValidatorResult(False, f"{var}={val!r}, expected ~{round(e,1)} (tol {round(tol,1)})")
    return ValidatorResult(True, f"Correct: total flue gas={round(exp['total_flue_gas'],0)}, {n10} stations within 10km, nearby PM2.5={round(exp['nearby_mean_pm25'],1)}")


tools = []
variables = [
    Variable("total_flue_gas", None, "Total flue-gas volume of company 2444 over 2025-06-06 14:00-18:00 (float)."),
    Variable("peak_flue_gas", None, "Peak hourly flue-gas volume over the window (float)."),
    Variable("stations_within_10km", None, "Number of air-quality stations within 10km of company 2444 (int)."),
    Variable("nearby_mean_pm25", None, "Mean PM2.5 across those nearby stations over the window (float)."),
]
validators = {"validate_hb_7_13": validate_hb_7_13}
