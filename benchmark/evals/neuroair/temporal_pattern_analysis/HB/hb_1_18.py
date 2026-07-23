"""Neuro-Air HB 1-18 (verbatim) — emission surge periods and their frequency.

Original query analyzes the emission surge periods of Tianjin Iron Works Co., Ltd.
(company_id 2564) and their frequency patterns over 2025-06-10 to 2025-06-12. The validator
recomputes the peak (max) hourly exhaust_gas and its whole-hour offset from 2025-06-10 00:00,
the mean and population std, and — operationalising "surge frequency" — the number of hours
whose exhaust_gas exceeds mean + 1 std (a surge). GT recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

COMPANY_ID = 2564
WIN_START = "2025-06-10 00:00:00"
WIN_END = "2025-06-13 00:00:00"


def validate_hb_1_18(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    r = pd.read_sql(
        text(
            f"SELECT MAX(exhaust_gas) AS peak, AVG(exhaust_gas) AS mean, STDDEV_POP(exhaust_gas) AS sd "
            f"FROM hourly_polluting_company_emission WHERE company_id = {COMPANY_ID} "
            f"AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}'"
        ),
        engine,
    ).iloc[0]
    mean, sd = float(r["mean"]), float(r["sd"])
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
    surge = int(
        pd.read_sql(
            text(
                f"SELECT COUNT(*) AS c FROM hourly_polluting_company_emission WHERE company_id = {COMPANY_ID} "
                f"AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}' AND exhaust_gas > {mean + sd}"
            ),
            engine,
        ).iloc[0]["c"]
    )
    exp = {
        "peak_flue_gas": float(r["peak"]),
        "mean_flue_gas": mean,
        "std_flue_gas": sd,
        "surge_hours": surge,
    }
    checks = [
        ("peak_flue_gas", "num", max(1.0, exp["peak_flue_gas"] * 0.005)),
        ("mean_flue_gas", "num", max(1.0, exp["mean_flue_gas"] * 0.005)),
        ("std_flue_gas", "num", max(1.0, exp["std_flue_gas"] * 0.02)),
        ("surge_hours", "int", 0),
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
    pk = runtime.retrieve("peak_flue_gas_offset_hours")
    if pk is None:
        return ValidatorResult(False, "peak_flue_gas_offset_hours not set", variables_not_set=True)
    if not is_finite_number(pk) or int(pk) not in peak_offsets:
        return ValidatorResult(False, f"peak_flue_gas_offset_hours={pk!r}, expected one of {sorted(peak_offsets)}")
    return ValidatorResult(True, f"Correct: peak {round(exp['peak_flue_gas'],0)} at +{min(peak_offsets)}h, {surge} surge hours (>mean+std)")


tools = []
variables = [
    Variable("peak_flue_gas", None, "Peak (max) hourly flue-gas volume of Tianjin Iron Works over 2025-06-10 to 2025-06-12 (float)."),
    Variable("peak_flue_gas_offset_hours", None, "Whole hours from 2025-06-10 00:00 to the emission peak (int)."),
    Variable("mean_flue_gas", None, "Mean hourly flue-gas volume over the window (float)."),
    Variable("std_flue_gas", None, "Population standard deviation of hourly flue-gas over the window (float)."),
    Variable("surge_hours", None, "Number of hours whose flue-gas exceeds mean + 1 std = surge frequency (int)."),
]
validators = {"validate_hb_1_18": validate_hb_1_18}
