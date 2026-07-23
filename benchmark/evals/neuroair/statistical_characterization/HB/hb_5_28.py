"""Neuro-Air HB 5-28 (verbatim) — cross-industry emission comparison in Handan.

Original query compares emission characteristics across STEEL, POWER, CEMENT, CERAMICS,
GLASS and COKING enterprises in Handan (city_id 4) during June 2025 and asks which
industry contributes most to regional pollution. The validator recomputes the total
exhaust_gas per named industry over 2025-06-01 -> 2025-07-01 and the top-contributing
industry. GT is recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

CITY_ID = 4  # Handan
WIN_START = "2025-06-01 00:00:00"
WIN_END = "2025-07-01 00:00:00"
INDUSTRIES = ["STEEL", "POWER", "CEMENT", "CERAMICS", "GLASS", "COKING"]


def validate_hb_5_28(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    df = pd.read_sql(
        text(
            f"SELECT p.industry_type AS ind, SUM(e.exhaust_gas) AS teg "
            f"FROM hourly_polluting_company_emission e JOIN polluting_company p ON e.company_id = p.id "
            f"WHERE p.city_id = {CITY_ID} AND p.industry_type = ANY(:inds) "
            f"AND e.timestamp >= '{WIN_START}' AND e.timestamp < '{WIN_END}' GROUP BY p.industry_type"
        ),
        engine,
        params={"inds": INDUSTRIES},
    )
    totals = {ind: 0.0 for ind in INDUSTRIES}
    for _, r in df.iterrows():
        totals[r["ind"]] = float(r["teg"])
    top_industry = max(totals, key=lambda k: totals[k])

    exp = {f"total_exhaust_{ind.lower()}": totals[ind] for ind in INDUSTRIES}
    exp["top_contributing_industry"] = top_industry

    for ind in INDUSTRIES:
        var = f"total_exhaust_{ind.lower()}"
        val = runtime.retrieve(var)
        if val is None:
            return ValidatorResult(False, f"{var} not set", variables_not_set=True)
        e = exp[var]
        if not is_finite_number(val) or not compare_numeric(float(val), float(e), tolerance=max(1.0, e * 0.005)):
            return ValidatorResult(False, f"{var}={val!r}, expected ~{round(e,1)}")
    top = runtime.retrieve("top_contributing_industry")
    if top is None:
        return ValidatorResult(False, "top_contributing_industry not set", variables_not_set=True)
    if not (isinstance(top, str) and top.strip().upper() == top_industry):
        return ValidatorResult(False, f"top_contributing_industry={top!r}, expected {top_industry!r}")
    return ValidatorResult(True, f"Correct: top industry = {top_industry} (exhaust {round(totals[top_industry],0)})")


tools = []
variables = [
    Variable("total_exhaust_steel", None, "Total flue-gas volume from steel enterprises in Handan, June 2025 (float)."),
    Variable("total_exhaust_power", None, "Total flue-gas volume from power enterprises (float)."),
    Variable("total_exhaust_cement", None, "Total flue-gas volume from cement enterprises (float)."),
    Variable("total_exhaust_ceramics", None, "Total flue-gas volume from ceramics enterprises (float)."),
    Variable("total_exhaust_glass", None, "Total flue-gas volume from glass enterprises (float)."),
    Variable("total_exhaust_coking", None, "Total flue-gas volume from coking enterprises (float)."),
    Variable("top_contributing_industry", None, "Industry type (one of the six, uppercase) with the highest total flue-gas volume (str)."),
]
validators = {"validate_hb_5_28": validate_hb_5_28}
