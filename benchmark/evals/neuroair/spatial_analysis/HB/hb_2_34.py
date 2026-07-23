"""Neuro-Air HB 2-34 (verbatim) — schools (OSM education) within 2km of Congtai Park.

Original query analyzes air quality around EDUCATION facilities within 2km of Congtai
Park monitoring station (station_id 98) in Handan on 2025-06-15, mapping schools via OSM
education features. The validator recomputes the count of OSM EDUCATION features within
2km of station 98 and the station's air quality that day (mean AQI, peak PM2.5). GT is
recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

STATION_ID = 98
DAY = "2025-06-15"


def validate_hb_2_34(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    cnt = int(
        pd.read_sql(
            text(
                f"SELECT COUNT(*) AS c FROM osm_feature o, air_quality_station s "
                f"WHERE s.id = {STATION_ID} AND o.main_type = 'EDUCATION' "
                f"AND ST_DWithin(o.geometry, s.coordinate, 2000)"
            ),
            engine,
        ).iloc[0]["c"]
    )
    aq = pd.read_sql(
        text(
            f"SELECT AVG(aqi) AS mean_aqi, MAX(pm2_5) AS max_pm25 FROM hourly_station_air_quality "
            f"WHERE station_id = {STATION_ID} AND timestamp >= '{DAY}' AND timestamp < '{DAY}'::date + 1"
        ),
        engine,
    ).iloc[0]

    exp = {
        "education_count_within_2km": cnt,
        "station_mean_aqi": float(aq["mean_aqi"]),
        "station_max_pm25": float(aq["max_pm25"]),
    }
    checks = [("education_count_within_2km", "int", 0), ("station_mean_aqi", "num", 2.0), ("station_max_pm25", "num", 2.0)]
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
    return ValidatorResult(True, f"Correct: {cnt} schools within 2km, station mean AQI={round(exp['station_mean_aqi'],1)}")


tools = []
variables = [
    Variable("education_count_within_2km", None, "Count of OSM education features within 2km of Congtai Park station (int)."),
    Variable("station_mean_aqi", None, "Mean AQI at Congtai Park station on 2025-06-15 (float)."),
    Variable("station_max_pm25", None, "Peak (max) hourly PM2.5 at Congtai Park station that day (float)."),
]
validators = {"validate_hb_2_34": validate_hb_2_34}
