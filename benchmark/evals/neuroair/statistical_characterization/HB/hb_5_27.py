"""Neuro-Air HB 5-27 (verbatim) — plant production vs district air quality in Qian'an.

Original query analyzes how production at Shougang Qian'an Steel (company_id 2452)
correlates with hourly air quality in Qian'an City (district_id 41) over 2025-06-22 to
2025-06-28. The validator recomputes the objective source and receptor aggregates over
that window: the company's total exhaust_gas, and the district's mean and peak AQI. GT
is recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

COMPANY_ID = 2452
DISTRICT_ID = 41
WIN_START = "2025-06-22 00:00:00"
WIN_END = "2025-06-29 00:00:00"


def validate_hb_5_27(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    teg = float(
        pd.read_sql(
            text(
                f"SELECT SUM(exhaust_gas) AS v FROM hourly_polluting_company_emission "
                f"WHERE company_id = {COMPANY_ID} AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}'"
            ),
            engine,
        ).iloc[0]["v"]
    )
    d = pd.read_sql(
        text(
            f"SELECT AVG(aqi) AS mean_aqi, MAX(aqi) AS max_aqi FROM hourly_district_air_quality "
            f"WHERE district_id = {DISTRICT_ID} AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}'"
        ),
        engine,
    ).iloc[0]

    exp = {
        "company_total_exhaust": teg,
        "district_mean_aqi": float(d["mean_aqi"]),
        "district_max_aqi": float(d["max_aqi"]),
    }
    checks = [
        ("company_total_exhaust", "num", max(1.0, teg * 0.005)),
        ("district_mean_aqi", "num", 2.0),
        ("district_max_aqi", "num", 2.0),
    ]
    for var, kind, tol in checks:
        val = runtime.retrieve(var)
        if val is None:
            return ValidatorResult(False, f"{var} not set", variables_not_set=True)
        e = exp[var]
        if not is_finite_number(val) or not compare_numeric(float(val), float(e), tolerance=tol):
            return ValidatorResult(False, f"{var}={val!r}, expected ~{round(e,1)} (tol {round(tol,1)})")
    return ValidatorResult(True, f"Correct: company exhaust={round(teg,0)}, district mean AQI={round(exp['district_mean_aqi'],1)}")


tools = []
variables = [
    Variable("company_total_exhaust", None, "Total flue-gas volume of company 2452 over 2025-06-22 to 2025-06-28 (float)."),
    Variable("district_mean_aqi", None, "Mean AQI of Qian'an district (id 41) over the window (float)."),
    Variable("district_max_aqi", None, "Peak (max) hourly AQI of the district over the window (float)."),
]
validators = {"validate_hb_5_27": validate_hb_5_27}
