"""Neuro-Air HB 1-4 (verbatim) — city-wide enterprise emission profile for Tangshan.

Original query analyzes the emission patterns of enterprises in Tangshan City (city_id 2) on
2025-06-08. The validator recomputes that day's city-wide emission profile: total flue-gas
volume across all Tangshan companies, the number of companies with emission data, the single
top-emitting company and its total. GT is recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

CITY_ID = 2  # Tangshan
DAY = "2025-06-08"


def validate_hb_1_4(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    agg = pd.read_sql(
        text(
            f"SELECT SUM(e.exhaust_gas) AS total, COUNT(DISTINCT e.company_id) AS ncomp "
            f"FROM hourly_polluting_company_emission e JOIN polluting_company p ON e.company_id = p.id "
            f"WHERE p.city_id = {CITY_ID} AND e.timestamp >= '{DAY}' AND e.timestamp < '{DAY}'::date + 1"
        ),
        engine,
    ).iloc[0]
    top = pd.read_sql(
        text(
            f"SELECT e.company_id, SUM(e.exhaust_gas) AS t FROM hourly_polluting_company_emission e "
            f"JOIN polluting_company p ON e.company_id = p.id "
            f"WHERE p.city_id = {CITY_ID} AND e.timestamp >= '{DAY}' AND e.timestamp < '{DAY}'::date + 1 "
            f"GROUP BY e.company_id ORDER BY t DESC LIMIT 1"
        ),
        engine,
    ).iloc[0]

    exp = {
        "total_city_flue_gas": float(agg["total"]),
        "active_company_count": int(agg["ncomp"]),
        "top_emitter_company_id": int(top["company_id"]),
        "top_emitter_total": float(top["t"]),
    }
    checks = [
        ("total_city_flue_gas", "num", max(1.0, exp["total_city_flue_gas"] * 0.005)),
        ("active_company_count", "int", 0),
        ("top_emitter_company_id", "int", 0),
        ("top_emitter_total", "num", max(1.0, exp["top_emitter_total"] * 0.005)),
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
    return ValidatorResult(True, f"Correct: city total={round(exp['total_city_flue_gas'],0)}, {exp['active_company_count']} companies, top emitter {exp['top_emitter_company_id']}")


tools = []
variables = [
    Variable("total_city_flue_gas", None, "Total flue-gas volume across all 唐山市 (Tangshan) companies on 2025-06-08 (float)."),
    Variable("active_company_count", None, "Number of companies with emission data that day (int)."),
    Variable("top_emitter_company_id", None, "The single highest-emitting company that day (int)."),
    Variable("top_emitter_total", None, "That top emitter's total flue-gas volume that day (float)."),
]
validators = {"validate_hb_1_4": validate_hb_1_4}
