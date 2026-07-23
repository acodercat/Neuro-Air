"""Neuro-Air HB 7-35 (verbatim) — multi-source impact on Congtai Park station.

Original query investigates multi-source pollution impact on Congtai Park station
(station_id 98) over 2025-06-05 06:00 to 2025-06-06 18:00, considering emissions from
Hebei Puyang Steel (company_id 2495) among others. The validator recomputes the
source→receptor geometry (distance, bearing from 2495 to station 98), the receptor's PM2.5
(mean, peak) over the window, and the source's total flue-gas volume. GT recomputed from DB.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

COMPANY_ID = 2495
STATION_ID = 98
WIN_START = "2025-06-05 06:00:00"
WIN_END = "2025-06-06 18:00:00"


def validate_hb_7_35(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
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
            f"SELECT AVG(pm2_5) AS station_mean_pm25, MAX(pm2_5) AS station_max_pm25 "
            f"FROM hourly_station_air_quality WHERE station_id = {STATION_ID} "
            f"AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}'"
        ),
        engine,
    ).iloc[0]
    teg = float(
        pd.read_sql(
            text(
                f"SELECT SUM(exhaust_gas) AS v FROM hourly_polluting_company_emission "
                f"WHERE company_id = {COMPANY_ID} AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}'"
            ),
            engine,
        ).iloc[0]["v"]
    )
    exp = {
        "distance_km": float(g["distance_km"]),
        "bearing_deg": float(g["bearing_deg"]),
        "station_mean_pm25": float(st["station_mean_pm25"]),
        "station_max_pm25": float(st["station_max_pm25"]),
        "company_total_flue_gas": teg,
    }
    checks = [
        ("distance_km", "num", max(0.2, exp["distance_km"] * 0.005)), ("bearing_deg", "num", 3.0),
        ("station_mean_pm25", "num", 2.0), ("station_max_pm25", "num", 2.0),
        ("company_total_flue_gas", "num", max(1.0, teg * 0.005)),
    ]
    for var, kind, tol in checks:
        val = runtime.retrieve(var)
        if val is None:
            return ValidatorResult(False, f"{var} not set", variables_not_set=True)
        e = exp[var]
        if not is_finite_number(val) or not compare_numeric(float(val), float(e), tolerance=tol):
            return ValidatorResult(False, f"{var}={val!r}, expected ~{round(e,2)} (tol {round(tol,2)})")
    return ValidatorResult(True, f"Correct: distance={round(exp['distance_km'],2)}km bearing={round(exp['bearing_deg'],0)}, station mean PM2.5={round(exp['station_mean_pm25'],1)}")


tools = []
variables = [
    Variable("distance_km", None, "Distance from company 2495 to station 98 in km (float)."),
    Variable("bearing_deg", None, "Compass bearing from company 2495 to station 98 in degrees (float)."),
    Variable("station_mean_pm25", None, "Mean PM2.5 at station 98 over 2025-06-05 06:00 to 2025-06-06 18:00 (float)."),
    Variable("station_max_pm25", None, "Peak (max) hourly PM2.5 at station 98 over the window (float)."),
    Variable("company_total_flue_gas", None, "Total flue-gas volume of company 2495 over the window (float)."),
]
validators = {"validate_hb_7_35": validate_hb_7_35}
