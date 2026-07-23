"""Neuro-Air HB 5-29 (verbatim) — steel vs power industry emissions in Tangshan.

Original query analyzes the emission patterns of STEEL versus POWER industries in Tangshan
City (city_id 2) from 2025-06-01 to 2025-06-05. The validator recomputes each industry's total
flue-gas volume over the window and the number of companies of each type. GT recomputed from DB.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

CITY_ID = 2  # Tangshan
WIN_START = "2025-06-01 00:00:00"
WIN_END = "2025-06-06 00:00:00"


def _industry(ind):
    r = pd.read_sql(
        text(
            f"SELECT SUM(e.exhaust_gas) AS total, COUNT(DISTINCT e.company_id) AS ncomp "
            f"FROM hourly_polluting_company_emission e JOIN polluting_company p ON e.company_id = p.id "
            f"WHERE p.city_id = {CITY_ID} AND p.industry_type = '{ind}' "
            f"AND e.timestamp >= '{WIN_START}' AND e.timestamp < '{WIN_END}'"
        ),
        engine,
    ).iloc[0]
    return float(r["total"]), int(r["ncomp"])


def validate_hb_5_29(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    s_total, s_n = _industry("STEEL")
    p_total, p_n = _industry("POWER")
    exp = {
        "total_steel_flue_gas": s_total,
        "total_power_flue_gas": p_total,
        "steel_company_count": s_n,
        "power_company_count": p_n,
    }
    checks = [
        ("total_steel_flue_gas", "num", max(1.0, s_total * 0.005)),
        ("total_power_flue_gas", "num", max(1.0, p_total * 0.005)),
        ("steel_company_count", "int", 0),
        ("power_company_count", "int", 0),
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
    return ValidatorResult(True, f"Correct: STEEL total={round(s_total,0)} ({s_n} plants) vs POWER={round(p_total,0)} ({p_n} plants)")


tools = []
variables = [
    Variable("total_steel_flue_gas", None, "Total flue-gas volume of Tangshan STEEL enterprises, 2025-06-01 to 2025-06-05 (float)."),
    Variable("total_power_flue_gas", None, "Total flue-gas volume of Tangshan POWER enterprises over the window (float)."),
    Variable("steel_company_count", None, "Number of steel companies with emission data over the window (int)."),
    Variable("power_company_count", None, "Number of power companies with emission data over the window (int)."),
]
validators = {"validate_hb_5_29": validate_hb_5_29}
