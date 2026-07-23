"""Neuro-Air HB 7-24 (verbatim) — full-day emission of Hanbao Steel and its neighbourhood.

Original query analyzes how Hangang Group Hanbao Steel (company_id 2611) emissions on
2025-06-10 affected urban air quality. The validator recomputes that day's total/peak flue-gas
volume, total NOx, and the number of air-quality stations within 10km. GT recomputed from DB.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

COMPANY_ID = 2611
DAY = "2025-06-10"


def validate_hb_7_24(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    em = pd.read_sql(
        text(
            f"SELECT SUM(exhaust_gas) AS total_flue_gas, MAX(exhaust_gas) AS peak_flue_gas, SUM(nox) AS total_nox "
            f"FROM hourly_polluting_company_emission WHERE company_id = {COMPANY_ID} "
            f"AND timestamp >= '{DAY}' AND timestamp < '{DAY}'::date + 1"
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
    exp = {
        "total_flue_gas": float(em["total_flue_gas"]),
        "peak_flue_gas": float(em["peak_flue_gas"]),
        "total_nox": float(em["total_nox"]),
        "stations_within_10km": n10,
    }
    checks = [
        ("total_flue_gas", "num", max(1.0, exp["total_flue_gas"] * 0.005)),
        ("peak_flue_gas", "num", max(1.0, exp["peak_flue_gas"] * 0.005)),
        ("total_nox", "num", max(1.0, exp["total_nox"] * 0.005)),
        ("stations_within_10km", "int", 0),
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
    return ValidatorResult(True, f"Correct: day total flue gas={round(exp['total_flue_gas'],0)}, {n10} stations within 10km")


tools = []
variables = [
    Variable("total_flue_gas", None, "Total flue-gas volume of company 2611 on 2025-06-10 (float)."),
    Variable("peak_flue_gas", None, "Peak hourly flue-gas volume that day (float)."),
    Variable("total_nox", None, "Total NOx that day (float)."),
    Variable("stations_within_10km", None, "Number of air-quality stations within 10km of company 2611 (int)."),
]
validators = {"validate_hb_7_24": validate_hb_7_24}
