"""Neuro-Air HB 7-16 (verbatim) — morning-peak emission window and neighbourhood.

Original query assesses pollution dispersion from Qian'an Jiujiang Wire Rod (company_id 2426)
on 2025-06-10 during the morning production peak (06:00-10:00). The validator recomputes, over
the window 06:00-10:00, the company's total/peak flue-gas volume, total NOx, and the
number of air-quality stations within 10km. GT recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

COMPANY_ID = 2426
WIN_START = "2025-06-10 06:00:00"
WIN_END = "2025-06-10 10:00:00"  # window end (end-EXCLUSIVE per shared window convention)


def validate_hb_7_16(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    # Explicit short clock range: whether the end hour is included is a genuine
    # convention ambiguity, so accept EITHER the end-exclusive or the end-inclusive
    # window for the boundary-sensitive sums.
    _sel = (
        "SELECT SUM(exhaust_gas) AS total_flue_gas, MAX(exhaust_gas) AS peak_flue_gas, SUM(nox) AS total_nox "
        f"FROM hourly_polluting_company_emission WHERE company_id = {COMPANY_ID} "
        f"AND timestamp >= '{WIN_START}' AND timestamp {{op}} '{WIN_END}'"
    )
    em = pd.read_sql(text(_sel.format(op="<")), engine).iloc[0]
    em_incl = pd.read_sql(text(_sel.format(op="<=")), engine).iloc[0]
    n10 = int(
        pd.read_sql(
            text(
                f"SELECT COUNT(*) AS c FROM air_quality_station s, polluting_company p "
                f"WHERE p.id = {COMPANY_ID} AND ST_DWithin(s.coordinate, p.coordinate, 10000)"
            ),
            engine,
        ).iloc[0]["c"]
    )
    exp = {
        "total_flue_gas": float(em["total_flue_gas"]),
        "peak_flue_gas": float(em["peak_flue_gas"]),
        "total_nox": float(em["total_nox"]),
        "stations_within_10km": n10,
    }
    exp_incl = {
        "total_flue_gas": float(em_incl["total_flue_gas"]),
        "peak_flue_gas": float(em_incl["peak_flue_gas"]),
        "total_nox": float(em_incl["total_nox"]),
    }
    checks = [
        ("total_flue_gas", "num", max(1.0, exp["total_flue_gas"] * 0.005)),
        ("peak_flue_gas", "num", max(1.0, exp["peak_flue_gas"] * 0.005)),
        ("total_nox", "num", max(0.5, exp["total_nox"] * 0.005)),
        ("stations_within_10km", "int", 0),
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
            alts = [e] + ([exp_incl[var]] if var in exp_incl else [])
            if not is_finite_number(val) or not any(compare_numeric(float(val), float(a), tolerance=tol) for a in alts):
                return ValidatorResult(False, f"{var}={val!r}, expected ~{round(e,1)} (tol {round(tol,1)})")
    return ValidatorResult(True, f"Correct: morning-peak total flue gas={round(exp['total_flue_gas'],0)}, {n10} stations within 10km")


tools = []
variables = [
    Variable("total_flue_gas", None, "Total flue-gas volume of company 2426 over 2025-06-10 06:00-10:00 (float)."),
    Variable("peak_flue_gas", None, "Peak hourly flue-gas volume over that window (float)."),
    Variable("total_nox", None, "Total NOx over that window (float)."),
    Variable("stations_within_10km", None, "Number of air-quality stations within 10km of company 2426 (int)."),
]
validators = {"validate_hb_7_16": validate_hb_7_16}
