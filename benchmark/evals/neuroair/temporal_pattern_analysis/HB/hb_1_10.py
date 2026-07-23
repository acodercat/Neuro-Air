"""Neuro-Air HB 1-10 (verbatim) — hourly emission variation of Jinan Steel.

Original query analyzes the hourly emission variations of Jinan Steel Group (company_id 2581)
during 2025-06-10 to 2025-06-11. The validator recomputes that 2-day window's total / mean /
peak flue-gas volume and the coefficient of variation (population std / mean) of hourly
emission. GT recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

COMPANY_ID = 2581
WIN_START = "2025-06-10 00:00:00"
WIN_END = "2025-06-12 00:00:00"


def validate_hb_1_10(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    r = pd.read_sql(
        text(
            f"SELECT SUM(exhaust_gas) AS total, AVG(exhaust_gas) AS mean, MAX(exhaust_gas) AS peak, "
            f"STDDEV_POP(exhaust_gas) AS sd FROM hourly_polluting_company_emission "
            f"WHERE company_id = {COMPANY_ID} AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}'"
        ),
        engine,
    ).iloc[0]
    exp = {
        "total_flue_gas": float(r["total"]),
        "mean_flue_gas": float(r["mean"]),
        "peak_flue_gas": float(r["peak"]),
        "cv_flue_gas": float(r["sd"]) / float(r["mean"]),
    }
    checks = [
        ("total_flue_gas", max(1.0, exp["total_flue_gas"] * 0.005)),
        ("mean_flue_gas", max(1.0, exp["mean_flue_gas"] * 0.005)),
        ("peak_flue_gas", max(1.0, exp["peak_flue_gas"] * 0.005)),
        ("cv_flue_gas", 0.005),
    ]
    for var, tol in checks:
        val = runtime.retrieve(var)
        if val is None:
            return ValidatorResult(False, f"{var} not set", variables_not_set=True)
        if not is_finite_number(val) or not compare_numeric(float(val), float(exp[var]), tolerance=tol):
            return ValidatorResult(False, f"{var}={val!r}, expected ~{round(exp[var],4)} (tol {tol})")
    return ValidatorResult(True, f"Correct: total={round(exp['total_flue_gas'],0)}, CV={round(exp['cv_flue_gas'],4)}")


tools = []
variables = [
    Variable("total_flue_gas", None, "Total flue-gas volume of Jinan Steel Group over 2025-06-10 to 2025-06-11 (float)."),
    Variable("mean_flue_gas", None, "Mean hourly flue-gas volume over the window (float)."),
    Variable("peak_flue_gas", None, "Peak hourly flue-gas volume over the window (float)."),
    Variable("cv_flue_gas", None, "Coefficient of variation (population std / mean) of hourly flue-gas (float)."),
]
validators = {"validate_hb_1_10": validate_hb_1_10}
