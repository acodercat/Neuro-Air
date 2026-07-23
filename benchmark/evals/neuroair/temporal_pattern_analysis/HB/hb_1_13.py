"""Neuro-Air HB 1-13 (verbatim) — when a steel plant's NOx emissions peak.

Original query analyzes when Jingye Metallurgical Technology (company_id 2417) has the
highest NOx emissions over 2025-06-10 to 2025-06-12. The validator recomputes the peak
(max) hourly NOx, the whole-hour offset from 2025-06-10 00:00 to that peak, and the total
and mean NOx over the window. GT is recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

COMPANY_ID = 2417
WIN_START = "2025-06-10 00:00:00"
WIN_END = "2025-06-13 00:00:00"


def validate_hb_1_13(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    r = pd.read_sql(
        text(
            f"SELECT MAX(nox) AS peak_nox, SUM(nox) AS total_nox, AVG(nox) AS mean_nox "
            f"FROM hourly_polluting_company_emission WHERE company_id = {COMPANY_ID} "
            f"AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}'"
        ),
        engine,
    ).iloc[0]
    # Accept ANY offset achieving the max nox: on a tie there are several
    # legitimate "peak" hours, so the validator must not demand one arbitrary pick.
    peak_offsets = {
        int(round(float(o))) for o in pd.read_sql(
            text(
                f"SELECT EXTRACT(EPOCH FROM (timestamp - TIMESTAMP '{WIN_START}'))/3600 AS off_h "
                f"FROM hourly_polluting_company_emission WHERE company_id = {COMPANY_ID} "
                f"AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}' "
                f"AND nox = (SELECT MAX(nox) FROM hourly_polluting_company_emission "
                f"WHERE company_id = {COMPANY_ID} AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}')"
            ),
            engine,
        )["off_h"]
    }

    exp = {
        "peak_nox": float(r["peak_nox"]),
        "total_nox": float(r["total_nox"]),
        "mean_nox": float(r["mean_nox"]),
    }
    checks = [
        ("peak_nox", "num", max(0.5, exp["peak_nox"] * 0.005)),
        ("total_nox", "num", max(1.0, exp["total_nox"] * 0.005)),
        ("mean_nox", "num", max(0.5, exp["mean_nox"] * 0.005)),
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
    pk = runtime.retrieve("peak_nox_offset_hours")
    if pk is None:
        return ValidatorResult(False, "peak_nox_offset_hours not set", variables_not_set=True)
    if not is_finite_number(pk) or int(pk) not in peak_offsets:
        return ValidatorResult(False, f"peak_nox_offset_hours={pk!r}, expected one of {sorted(peak_offsets)}")
    return ValidatorResult(True, f"Correct: peak NOx {round(exp['peak_nox'],1)} at +{min(peak_offsets)}h")


tools = []
variables = [
    Variable("peak_nox", None, "Peak (max) hourly NOx of Jingye Metallurgical Technology over 2025-06-10 to 2025-06-12 (float)."),
    Variable("peak_nox_offset_hours", None, "Whole hours from 2025-06-10 00:00 to the NOx peak (int)."),
    Variable("total_nox", None, "Total NOx over the window (float)."),
    Variable("mean_nox", None, "Mean hourly NOx over the window (float)."),
]
validators = {"validate_hb_1_13": validate_hb_1_13}
