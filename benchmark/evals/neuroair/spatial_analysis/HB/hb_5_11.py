"""Neuro-Air HB 5-11 (verbatim) — source-receptor impact of Tangshan Donghua Steel on station 98.

Original query asks how emissions from Tangshan Donghua Steel (company_id 2419) affect the receptor
monitoring station 98 over the full day 2025-06-10. The validator recomputes the deterministic
source-receptor facts: company->station distance and compass bearing, the receptor
station's PM2.5 mean / peak / exceedance-hours over the window, and the source's total
exhaust_gas over the same window. GT is recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

COMPANY_ID = 2419
STATION_ID = 98
WIN_START = "2025-06-10 00:00:00"
WIN_END = "2025-06-11 00:00:00"


def validate_hb_5_11(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    g = pd.read_sql(
        text(
            f"SELECT ST_Distance(s.coordinate, pc.coordinate)/1000.0 AS distance_km, "
            f"degrees(ST_Azimuth(pc.coordinate, s.coordinate)) AS bearing_deg "
            f"FROM air_quality_station s, polluting_company pc WHERE pc.id = {COMPANY_ID} AND s.id = {STATION_ID}"
        ),
        engine,
    ).iloc[0]
    st = pd.read_sql(
        text(
            f"SELECT AVG(pm2_5) AS station_mean_pm25, MAX(pm2_5) AS station_max_pm25, "
            f"COUNT(*) FILTER (WHERE pm2_5 > 75) AS station_exceedance_hours "
            f"FROM hourly_station_air_quality WHERE station_id = {STATION_ID} "
            f"AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}'"
        ),
        engine,
    ).iloc[0]
    em = pd.read_sql(
        text(
            f"SELECT SUM(exhaust_gas) AS company_total_exhaust FROM hourly_polluting_company_emission "
            f"WHERE company_id = {COMPANY_ID} AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}'"
        ),
        engine,
    ).iloc[0]

    exp = {
        "distance_km": float(g["distance_km"]),
        "bearing_deg": float(g["bearing_deg"]),
        "station_mean_pm25": float(st["station_mean_pm25"]),
        "station_max_pm25": float(st["station_max_pm25"]),
        "station_exceedance_hours": int(st["station_exceedance_hours"]),
        "company_total_exhaust": float(em["company_total_exhaust"]),
    }
    checks = [
        ("distance_km", "num", max(0.2, exp["distance_km"] * 0.005)),
        ("bearing_deg", "num", 3.0),
        ("station_mean_pm25", "num", 2.0),
        ("station_max_pm25", "num", 2.0),
        ("station_exceedance_hours", "int", 0),
        ("company_total_exhaust", "num", max(1.0, exp["company_total_exhaust"] * 0.005)),
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
                return ValidatorResult(False, f"{var}={val!r}, expected ~{round(e,2)} (tol {round(tol,2)})")
    return ValidatorResult(True, f"Correct: distance={round(exp['distance_km'],2)}km bearing={round(exp['bearing_deg'],0)} station mean PM2.5={round(exp['station_mean_pm25'],1)}")


tools = []
variables = [
    Variable("distance_km", None, "Straight-line distance from company 2419 to station 98 in km (float)."),
    Variable("bearing_deg", None, "Compass bearing from the company to the station in degrees (float)."),
    Variable("station_mean_pm25", None, "Mean PM2.5 at the receptor station over the window (float)."),
    Variable("station_max_pm25", None, "Peak (max) hourly PM2.5 at the receptor station over the window (float)."),
    Variable("station_exceedance_hours", None, "Hours with station PM2.5 > 75 over the window (int)."),
    Variable("company_total_exhaust", None, "Total flue-gas volume emitted by the company over the window (float)."),
]
validators = {"validate_hb_5_11": validate_hb_5_11}
