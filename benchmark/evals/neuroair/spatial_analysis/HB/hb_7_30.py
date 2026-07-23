"""Neuro-Air HB 7-30 (verbatim) — single-hour transport from a cement plant to a school station.

Original query analyzes pollution transport affecting Luquan No.1 Middle School station
(station_id 48) on 2025-07-10 14:00, considering emissions from Shijiazhuang Quzhai Cement
(company_id 2427). The validator recomputes the source→receptor geometry (distance, bearing),
the company's flue-gas volume at 14:00, and the station's PM2.5 at 14:00. GT recomputed from DB.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

COMPANY_ID = 2427
STATION_ID = 48
TS = "2025-07-10 14:00:00"


def validate_hb_7_30(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    g = pd.read_sql(
        text(
            f"SELECT ST_Distance(s.coordinate, pc.coordinate)/1000.0 AS distance_km, "
            f"degrees(ST_Azimuth(pc.coordinate, s.coordinate)) AS bearing_deg "
            f"FROM air_quality_station s, polluting_company pc WHERE pc.id = {COMPANY_ID} AND s.id = {STATION_ID}"
        ),
        engine,
    ).iloc[0]
    em = pd.read_sql(
        text(f"SELECT exhaust_gas FROM hourly_polluting_company_emission WHERE company_id = {COMPANY_ID} AND timestamp = '{TS}'"),
        engine,
    )
    sv = pd.read_sql(
        text(f"SELECT pm2_5 FROM hourly_station_air_quality WHERE station_id = {STATION_ID} AND timestamp = '{TS}'"),
        engine,
    )
    if em.empty or sv.empty:
        return ValidatorResult(False, "no emission or station row at the target hour")

    exp = {
        "distance_km": float(g["distance_km"]),
        "bearing_deg": float(g["bearing_deg"]),
        "company_flue_gas_1400": float(em["exhaust_gas"].iloc[0]),
        "station_pm25_1400": float(sv["pm2_5"].iloc[0]),
    }
    checks = [
        ("distance_km", "num", max(0.2, exp["distance_km"] * 0.005)), ("bearing_deg", "num", 3.0),
        ("company_flue_gas_1400", "num", max(1.0, exp["company_flue_gas_1400"] * 0.005)),
        ("station_pm25_1400", "num", 2.0),
    ]
    for var, kind, tol in checks:
        val = runtime.retrieve(var)
        if val is None:
            return ValidatorResult(False, f"{var} not set", variables_not_set=True)
        e = exp[var]
        if not is_finite_number(val) or not compare_numeric(float(val), float(e), tolerance=tol):
            return ValidatorResult(False, f"{var}={val!r}, expected ~{round(e,2)} (tol {round(tol,2)})")
    return ValidatorResult(True, f"Correct: distance={round(exp['distance_km'],2)}km bearing={round(exp['bearing_deg'],0)}, station PM2.5@14:00={round(exp['station_pm25_1400'],0)}")


tools = []
variables = [
    Variable("distance_km", None, "Distance from company 2427 to station 48 in km (float)."),
    Variable("bearing_deg", None, "Compass bearing from company 2427 to station 48 in degrees (float)."),
    Variable("company_flue_gas_1400", None, "Flue-gas volume of company 2427 at 2025-07-10 14:00 (float)."),
    Variable("station_pm25_1400", None, "PM2.5 at station 48 at 2025-07-10 14:00 (float)."),
]
validators = {"validate_hb_7_30": validate_hb_7_30}
