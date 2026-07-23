"""Neuro-Air HB 3-10 (verbatim) — Tangshan steel emissions vs city air quality.

Original query analyzes the emission patterns of all steel enterprises in Tangshan (city_id 2)
on 2025-06-15 and compares with the city's air quality index. The validator recomputes the
total STEEL-industry flue-gas volume that day, the number of steel companies with data, and the
city's mean and peak AQI that day. GT recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

CITY_ID = 2  # Tangshan
DAY = "2025-06-15"


def validate_hb_3_10(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    st = pd.read_sql(
        text(
            f"SELECT SUM(e.exhaust_gas) AS total, COUNT(DISTINCT e.company_id) AS ncomp "
            f"FROM hourly_polluting_company_emission e JOIN polluting_company p ON e.company_id = p.id "
            f"WHERE p.city_id = {CITY_ID} AND p.industry_type = 'STEEL' "
            f"AND e.timestamp >= '{DAY}' AND e.timestamp < '{DAY}'::date + 1"
        ),
        engine,
    ).iloc[0]
    ci = pd.read_sql(
        text(
            f"SELECT AVG(aqi) AS mean_aqi, MAX(aqi) AS max_aqi FROM hourly_city_air_quality "
            f"WHERE city_id = {CITY_ID} AND timestamp >= '{DAY}' AND timestamp < '{DAY}'::date + 1"
        ),
        engine,
    ).iloc[0]

    exp = {
        "total_steel_flue_gas": float(st["total"]),
        "steel_company_count": int(st["ncomp"]),
        "city_mean_aqi": float(ci["mean_aqi"]),
        "city_max_aqi": float(ci["max_aqi"]),
    }
    checks = [
        ("total_steel_flue_gas", "num", max(1.0, exp["total_steel_flue_gas"] * 0.005)),
        ("steel_company_count", "int", 0),
        ("city_mean_aqi", "num", 2.0),
        ("city_max_aqi", "num", 2.0),
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
    return ValidatorResult(True, f"Correct: steel total={round(exp['total_steel_flue_gas'],0)} ({exp['steel_company_count']} plants), city mean AQI={round(exp['city_mean_aqi'],1)}")


tools = []
variables = [
    Variable("total_steel_flue_gas", None, "Total flue-gas volume of all Tangshan steel enterprises on 2025-06-15 (float)."),
    Variable("steel_company_count", None, "Number of steel companies with emission data that day (int)."),
    Variable("city_mean_aqi", None, "Mean city AQI for Tangshan that day (float)."),
    Variable("city_max_aqi", None, "Maximum hourly city AQI that day (float)."),
]
validators = {"validate_hb_3_10": validate_hb_3_10}
