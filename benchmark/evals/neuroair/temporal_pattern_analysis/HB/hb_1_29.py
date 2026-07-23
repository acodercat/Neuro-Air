"""Neuro-Air HB 1-29 (verbatim) — April vs May steel-industry emissions in Wu'an.

Original query compares steel-industry emissions AND air quality between April and May 2025
in Wu'an City (a county-level city = district_id 71 under Handan). The validator recomputes
both dimensions: the STEEL-industry total flue-gas volume for each month (over all steel
companies in Wu'an) plus which month is higher and the month-over-month percent change, and
the district's mean AQI for each month. GT recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

DISTRICT_ID = 71  # Wu'an


def _steel_total(lo, hi):
    v = pd.read_sql(
        text(
            f"SELECT COALESCE(SUM(e.exhaust_gas), 0) AS v FROM hourly_polluting_company_emission e "
            f"JOIN polluting_company p ON e.company_id = p.id "
            f"WHERE p.district_id = {DISTRICT_ID} AND p.industry_type = 'STEEL' "
            f"AND e.timestamp >= '{lo}' AND e.timestamp < '{hi}'"
        ),
        engine,
    ).iloc[0]["v"]
    return float(v)


def _district_mean_aqi(lo, hi):
    v = pd.read_sql(
        text(
            f"SELECT AVG(aqi) AS v FROM hourly_district_air_quality "
            f"WHERE district_id = {DISTRICT_ID} AND timestamp >= '{lo}' AND timestamp < '{hi}'"
        ),
        engine,
    ).iloc[0]["v"]
    return float(v)


def validate_hb_1_29(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    apr = _steel_total("2025-04-01", "2025-05-01")
    may = _steel_total("2025-05-01", "2025-06-01")
    higher = "April" if apr > may else "May"
    change_pct = round((may - apr) / apr * 100, 2)
    aqi_apr = _district_mean_aqi("2025-04-01", "2025-05-01")
    aqi_may = _district_mean_aqi("2025-05-01", "2025-06-01")

    exp = {"total_steel_apr": apr, "total_steel_may": may, "higher_emission_month": higher,
           "emission_change_pct": change_pct, "mean_aqi_apr": aqi_apr, "mean_aqi_may": aqi_may}
    for var, tol in [("total_steel_apr", max(1.0, apr * 0.005)), ("total_steel_may", max(1.0, may * 0.005)),
                     ("emission_change_pct", 1.0), ("mean_aqi_apr", 2.0), ("mean_aqi_may", 2.0)]:
        val = runtime.retrieve(var)
        if val is None:
            return ValidatorResult(False, f"{var} not set", variables_not_set=True)
        if not is_finite_number(val) or not compare_numeric(float(val), float(exp[var]), tolerance=tol):
            return ValidatorResult(False, f"{var}={val!r}, expected ~{round(exp[var],2)} (tol {round(tol,2)})")
    hm = runtime.retrieve("higher_emission_month")
    if hm is None:
        return ValidatorResult(False, "higher_emission_month not set", variables_not_set=True)
    if not (isinstance(hm, str) and hm.strip().lower() == higher.lower()):
        return ValidatorResult(False, f"higher_emission_month={hm!r}, expected {higher!r}")
    return ValidatorResult(True, f"Correct: April={round(apr,0)} vs May={round(may,0)}, higher={higher} ({change_pct}% change)")


tools = []
variables = [
    Variable("total_steel_apr", None, "Total steel-industry flue-gas volume in Wu'an City, April 2025 (float)."),
    Variable("total_steel_may", None, "Total steel-industry flue-gas volume in Wu'an, May 2025 (float)."),
    Variable("higher_emission_month", None, "Which month had higher steel emission, 'April' or 'May' (str)."),
    Variable("emission_change_pct", None, "Percent change from April to May, (May-April)/April*100 (float)."),
    Variable("mean_aqi_apr", None, "Mean district AQI of Wu'an City for April 2025 (float)."),
    Variable("mean_aqi_may", None, "Mean district AQI of Wu'an City for May 2025 (float)."),
]
validators = {"validate_hb_1_29": validate_hb_1_29}
