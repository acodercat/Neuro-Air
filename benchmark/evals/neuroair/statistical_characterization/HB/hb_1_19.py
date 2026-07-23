"""Neuro-Air HB 1-19 (verbatim) — multi-pollutant emission profile of a steel plant.

Original query analyzes when Hebei Jinxi Steel West Plant (company_id 2569) shows coordinated
high emissions across multiple pollutants over 2025-06-10 to 2025-06-12. The validator
recomputes the window totals of NOx / SO2 / PM and the peak hourly exhaust_gas. GT recomputed
from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

COMPANY_ID = 2569
WIN_START = "2025-06-10 00:00:00"
WIN_END = "2025-06-13 00:00:00"


def validate_hb_1_19(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    r = pd.read_sql(
        text(
            f"SELECT SUM(nox) AS total_nox, SUM(so2) AS total_so2, SUM(pm) AS total_pm, "
            f"MAX(exhaust_gas) AS peak_flue_gas FROM hourly_polluting_company_emission "
            f"WHERE company_id = {COMPANY_ID} AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}'"
        ),
        engine,
    ).iloc[0]
    exp = {
        "total_nox": float(r["total_nox"]),
        "total_so2": float(r["total_so2"]),
        "total_pm": float(r["total_pm"]),
        "peak_flue_gas": float(r["peak_flue_gas"]),
    }
    checks = [
        ("total_nox", max(1.0, exp["total_nox"] * 0.005)),
        ("total_so2", max(1.0, exp["total_so2"] * 0.005)),
        ("total_pm", max(1.0, exp["total_pm"] * 0.005)),
        ("peak_flue_gas", max(1.0, exp["peak_flue_gas"] * 0.005)),
    ]
    for var, tol in checks:
        val = runtime.retrieve(var)
        if val is None:
            return ValidatorResult(False, f"{var} not set", variables_not_set=True)
        if not is_finite_number(val) or not compare_numeric(float(val), float(exp[var]), tolerance=tol):
            return ValidatorResult(False, f"{var}={val!r}, expected ~{round(exp[var],1)} (tol {round(tol,1)})")
    return ValidatorResult(True, f"Correct: NOx={round(exp['total_nox'],0)}, SO2={round(exp['total_so2'],0)}, PM={round(exp['total_pm'],0)}, peak flue gas={round(exp['peak_flue_gas'],0)}")


tools = []
variables = [
    Variable("total_nox", None, "Total NOx of Hebei Jinxi Steel West Plant over 2025-06-10 to 2025-06-12 (float)."),
    Variable("total_so2", None, "Total SO2 over the window (float)."),
    Variable("total_pm", None, "Total PM over the window (float)."),
    Variable("peak_flue_gas", None, "Peak hourly flue-gas volume over the window (float)."),
]
validators = {"validate_hb_1_19": validate_hb_1_19}
