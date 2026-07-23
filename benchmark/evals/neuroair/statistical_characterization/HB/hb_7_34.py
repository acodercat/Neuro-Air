"""Neuro-Air HB 7-34 (verbatim) — high-production-period emission profile of a steel plant.

Original query analyzes emissions from Shougang Jingtang Steel (company_id 2444) during the
high production period 2025-06-15 to 2025-06-17. The validator recomputes that 3-day emission
profile: total / mean / peak flue-gas volume, total NOx, and active hours. GT recomputed from DB.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

COMPANY_ID = 2444
WIN_START = "2025-06-15 00:00:00"
WIN_END = "2025-06-18 00:00:00"


def validate_hb_7_34(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    r = pd.read_sql(
        text(
            f"SELECT SUM(exhaust_gas) AS total_flue_gas, AVG(exhaust_gas) AS mean_flue_gas, "
            f"MAX(exhaust_gas) AS peak_flue_gas, SUM(nox) AS total_nox, "
            f"COUNT(*) FILTER (WHERE exhaust_gas > 0) AS active_hours "
            f"FROM hourly_polluting_company_emission WHERE company_id = {COMPANY_ID} "
            f"AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}'"
        ),
        engine,
    ).iloc[0]
    exp = {
        "total_flue_gas": float(r["total_flue_gas"]),
        "mean_flue_gas": float(r["mean_flue_gas"]),
        "peak_flue_gas": float(r["peak_flue_gas"]),
        "total_nox": float(r["total_nox"]),
        "active_hours": int(r["active_hours"]),
    }
    checks = [
        ("total_flue_gas", "num", max(1.0, exp["total_flue_gas"] * 0.005)),
        ("mean_flue_gas", "num", max(1.0, exp["mean_flue_gas"] * 0.005)),
        ("peak_flue_gas", "num", max(1.0, exp["peak_flue_gas"] * 0.005)),
        ("total_nox", "num", max(1.0, exp["total_nox"] * 0.005)),
        ("active_hours", "int", 0),
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
    return ValidatorResult(True, f"Correct: 3-day total flue gas={round(exp['total_flue_gas'],0)}, {exp['active_hours']} active hours")


tools = []
variables = [
    Variable("total_flue_gas", None, "Total flue-gas volume of company 2444 over 2025-06-15 to 2025-06-17 (float)."),
    Variable("mean_flue_gas", None, "Mean hourly flue-gas volume over the window (float)."),
    Variable("peak_flue_gas", None, "Peak hourly flue-gas volume over the window (float)."),
    Variable("total_nox", None, "Total NOx over the window (float)."),
    Variable("active_hours", None, "Number of hours with positive flue-gas volume (int)."),
]
validators = {"validate_hb_7_34": validate_hb_7_34}
