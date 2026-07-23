"""Neuro-Air HB 7-36 (verbatim) — cross-district transport from Caofeidian.

Original query analyzes cross-district pollution transport from Caofeidian District
(district_id 31), where Shougang Jingtang Steel (company_id 2444) operates, to neighbouring
districts over 2025-06-20 12:00 to 2025-06-22 12:00. The validator recomputes the source aggregate
(company total flue-gas volume) and the origin district's air quality (mean and peak AQI).
GT is recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

COMPANY_ID = 2444
DISTRICT_ID = 31  # Caofeidian
WIN_START = "2025-06-20 12:00:00"
WIN_END = "2025-06-22 12:00:00"


def validate_hb_7_36(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
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
        "company_total_flue_gas": teg,
        "origin_district_mean_aqi": float(d["mean_aqi"]),
        "origin_district_max_aqi": float(d["max_aqi"]),
    }
    checks = [
        ("company_total_flue_gas", "num", max(1.0, teg * 0.005)),
        ("origin_district_mean_aqi", "num", 2.0),
        ("origin_district_max_aqi", "num", 2.0),
    ]
    for var, kind, tol in checks:
        val = runtime.retrieve(var)
        if val is None:
            return ValidatorResult(False, f"{var} not set", variables_not_set=True)
        e = exp[var]
        if not is_finite_number(val) or not compare_numeric(float(val), float(e), tolerance=tol):
            return ValidatorResult(False, f"{var}={val!r}, expected ~{round(e,1)} (tol {round(tol,1)})")
    return ValidatorResult(True, f"Correct: company flue gas={round(teg,0)}, Caofeidian mean AQI={round(exp['origin_district_mean_aqi'],1)}")


tools = []
variables = [
    Variable("company_total_flue_gas", None, "Total flue-gas volume of company 2444 over 2025-06-20 12:00 to 2025-06-22 12:00 (float)."),
    Variable("origin_district_mean_aqi", None, "Mean AQI of Caofeidian district (id 31) over the window (float)."),
    Variable("origin_district_max_aqi", None, "Peak (max) hourly AQI of Caofeidian district over the window (float)."),
]
validators = {"validate_hb_7_36": validate_hb_7_36}
