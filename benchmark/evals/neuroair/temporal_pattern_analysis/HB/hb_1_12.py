"""Neuro-Air HB 1-12 (verbatim) — high-emission periods & peak pattern of a steel plant.

Original query asks to identify the high-emission periods and analyze the emission
peak patterns of Shougang Jingtang Steel (company_id 2444) over 2025-06-10 to
2025-06-12. The validator recomputes the exhaust_gas profile over
2025-06-10 00:00 -> 2025-06-13 00:00: total, mean, peak hourly value, the whole-hour
offset from the window start to that peak, and the number of active hours. GT is
recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

COMPANY_ID = 2444
WIN_START = "2025-06-10 00:00:00"
WIN_END = "2025-06-13 00:00:00"


def validate_hb_1_12(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    r = pd.read_sql(
        text(
            f"SELECT SUM(exhaust_gas) AS total_flue_gas, AVG(exhaust_gas) AS mean_exhaust, "
            f"MAX(exhaust_gas) AS peak_exhaust, COUNT(*) FILTER (WHERE exhaust_gas > 0) AS active_hours "
            f"FROM hourly_polluting_company_emission WHERE company_id = {COMPANY_ID} "
            f"AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}'"
        ),
        engine,
    ).iloc[0]
    # Accept ANY offset achieving the max exhaust_gas: on a tie there are several
    # legitimate "peak" hours, so the validator must not demand one arbitrary pick.
    peak_offsets = {
        int(round(float(o))) for o in pd.read_sql(
            text(
                f"SELECT EXTRACT(EPOCH FROM (timestamp - TIMESTAMP '{WIN_START}'))/3600 AS off_h "
                f"FROM hourly_polluting_company_emission WHERE company_id = {COMPANY_ID} "
                f"AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}' "
                f"AND exhaust_gas = (SELECT MAX(exhaust_gas) FROM hourly_polluting_company_emission "
                f"WHERE company_id = {COMPANY_ID} AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}')"
            ),
            engine,
        )["off_h"]
    }

    exp = {
        "total_flue_gas": float(r["total_flue_gas"]),
        "mean_exhaust": float(r["mean_exhaust"]),
        "peak_exhaust": float(r["peak_exhaust"]),
        "active_hours": int(r["active_hours"]),
    }
    checks = [
        ("total_flue_gas", "num", max(1.0, exp["total_flue_gas"] * 0.005)),
        ("mean_exhaust", "num", max(1.0, exp["mean_exhaust"] * 0.005)),
        ("peak_exhaust", "num", max(1.0, exp["peak_exhaust"] * 0.005)),
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
    pk = runtime.retrieve("peak_offset_hours")
    if pk is None:
        return ValidatorResult(False, "peak_offset_hours not set", variables_not_set=True)
    if not is_finite_number(pk) or int(pk) not in peak_offsets:
        return ValidatorResult(False, f"peak_offset_hours={pk!r}, expected one of {sorted(peak_offsets)}")
    return ValidatorResult(True, f"Correct: peak exhaust {round(exp['peak_exhaust'],0)} at +{min(peak_offsets)}h, {exp['active_hours']} active hours")


tools = []
variables = [
    Variable("total_flue_gas", None, "Total flue-gas volume over 2025-06-10 to 2025-06-12 (float)."),
    Variable("mean_exhaust", None, "Mean hourly flue-gas volume over the window (float)."),
    Variable("peak_exhaust", None, "Peak (max) hourly flue-gas volume over the window (float)."),
    Variable("peak_offset_hours", None, "Whole hours from 2025-06-10 00:00 to the flue-gas volume peak (int)."),
    Variable("active_hours", None, "Number of hours with positive flue-gas volume (int)."),
]
validators = {"validate_hb_1_12": validate_hb_1_12}
