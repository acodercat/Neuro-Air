"""Neuro-Air HB 1-41 (verbatim) — weekend unauthorized-operation detection.

Original query monitors Hebei Donghai Special Steel (company_id 2446) over the weekend
2025-06-07 -> 2025-06-08 to detect illegal production during reduced oversight. The
validator recomputes the weekend emission profile (2025-06-07 00:00 -> 2025-06-09 00:00):
total exhaust_gas / NOx / SO2 / PM, the number of active hours (positive exhaust_gas —
the operating-hours signal), and the peak hourly exhaust_gas. GT recomputed from the DB.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

COMPANY_ID = 2446
WIN_START = "2025-06-07 00:00:00"
WIN_END = "2025-06-09 00:00:00"


def validate_hb_1_41(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    r = pd.read_sql(
        text(
            f"SELECT SUM(exhaust_gas) AS total_flue_gas, SUM(nox) AS total_nox, "
            f"SUM(so2) AS total_so2, SUM(pm) AS total_pm, "
            f"COUNT(*) FILTER (WHERE exhaust_gas > 0) AS active_hours, MAX(exhaust_gas) AS peak_exhaust "
            f"FROM hourly_polluting_company_emission WHERE company_id = {COMPANY_ID} "
            f"AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}'"
        ),
        engine,
    ).iloc[0]

    exp = {
        "total_flue_gas": float(r["total_flue_gas"]),
        "total_nox": float(r["total_nox"]),
        "total_so2": float(r["total_so2"]),
        "total_pm": float(r["total_pm"]),
        "active_hours": int(r["active_hours"]),
        "peak_exhaust": float(r["peak_exhaust"]),
    }
    checks = [
        ("total_flue_gas", "num", max(1.0, exp["total_flue_gas"] * 0.005)),
        ("total_nox", "num", max(1.0, exp["total_nox"] * 0.005)),
        ("total_so2", "num", max(1.0, exp["total_so2"] * 0.005)),
        ("total_pm", "num", max(1.0, exp["total_pm"] * 0.005)),
        ("active_hours", "int", 0),
        ("peak_exhaust", "num", max(1.0, exp["peak_exhaust"] * 0.005)),
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
    return ValidatorResult(True, f"Correct: {exp['active_hours']} active hours, total exhaust_gas={round(exp['total_flue_gas'],0)}")


tools = []
variables = [
    Variable("total_flue_gas", None, "Total flue-gas volume emitted over the weekend 2025-06-07 to 2025-06-08 (float)."),
    Variable("total_nox", None, "Total NOx emitted over the weekend (float)."),
    Variable("total_so2", None, "Total SO2 emitted over the weekend (float)."),
    Variable("total_pm", None, "Total PM emitted over the weekend (float)."),
    Variable("active_hours", None, "Number of hours with positive flue-gas volume = operating hours (int)."),
    Variable("peak_exhaust", None, "Peak hourly flue-gas volume over the weekend (float)."),
]
validators = {"validate_hb_1_41": validate_hb_1_41}
