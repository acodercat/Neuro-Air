"""Neuro-Air HB 1-16 (verbatim) — peak SO2 emission hours of a steel plant.

Original query asks to identify the peak SO2 emission hours of Shougang Qian'an Steel
(company_id 2452) over 2025-06-10 to 2025-06-12. The validator recomputes, over
2025-06-10 00:00 -> 2025-06-13 00:00, the peak (max) hourly SO2, the whole-hour offset
from the window start to that peak hour, and the total and mean SO2. GT recomputed from
the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

COMPANY_ID = 2452
WIN_START = "2025-06-10 00:00:00"
WIN_END = "2025-06-13 00:00:00"


def validate_hb_1_16(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    r = pd.read_sql(
        text(
            f"SELECT MAX(so2) AS peak_so2, SUM(so2) AS total_so2, AVG(so2) AS mean_so2 "
            f"FROM hourly_polluting_company_emission WHERE company_id = {COMPANY_ID} "
            f"AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}'"
        ),
        engine,
    ).iloc[0]
    # Accept ANY offset achieving the max so2: on a tie there are several
    # legitimate "peak" hours, so the validator must not demand one arbitrary pick.
    peak_offsets = {
        int(round(float(o))) for o in pd.read_sql(
            text(
                f"SELECT EXTRACT(EPOCH FROM (timestamp - TIMESTAMP '{WIN_START}'))/3600 AS off_h "
                f"FROM hourly_polluting_company_emission WHERE company_id = {COMPANY_ID} "
                f"AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}' "
                f"AND so2 = (SELECT MAX(so2) FROM hourly_polluting_company_emission "
                f"WHERE company_id = {COMPANY_ID} AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}')"
            ),
            engine,
        )["off_h"]
    }

    exp = {
        "peak_so2": float(r["peak_so2"]),
        "total_so2": float(r["total_so2"]),
        "mean_so2": float(r["mean_so2"]),
    }
    checks = [
        ("peak_so2", "num", max(1.0, exp["peak_so2"] * 0.005)),
        ("total_so2", "num", max(1.0, exp["total_so2"] * 0.005)),
        ("mean_so2", "num", max(0.5, exp["mean_so2"] * 0.005)),
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
    pk = runtime.retrieve("peak_so2_offset_hours")
    if pk is None:
        return ValidatorResult(False, "peak_so2_offset_hours not set", variables_not_set=True)
    if not is_finite_number(pk) or int(pk) not in peak_offsets:
        return ValidatorResult(False, f"peak_so2_offset_hours={pk!r}, expected one of {sorted(peak_offsets)}")
    return ValidatorResult(True, f"Correct: peak SO2 {round(exp['peak_so2'],1)} at +{min(peak_offsets)}h")


tools = []
variables = [
    Variable("peak_so2", None, "Peak (max) hourly SO2 emission over 2025-06-10 to 2025-06-12 (float)."),
    Variable("peak_so2_offset_hours", None, "Whole hours from 2025-06-10 00:00 to the peak SO2 hour (int)."),
    Variable("total_so2", None, "Total SO2 emitted over the window (float)."),
    Variable("mean_so2", None, "Mean hourly SO2 over the window (float)."),
]
validators = {"validate_hb_1_16": validate_hb_1_16}
