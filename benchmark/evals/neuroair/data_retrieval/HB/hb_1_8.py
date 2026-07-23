"""Neuro-Air HB 1-8 (verbatim) — ozone profile at East Sewage Treatment Plant station.

Original query analyzes ozone formation patterns at East Sewage Treatment Plant station
(name 东污水处理厂, station_id 99) over 2025-06-10 to 2025-06-12. The validator recomputes that
window's O3 profile: mean/peak O3 and the number of hours with O3 above 160 (the CN Grade-II
1-hour threshold). GT is recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

STATION_ID = 99
WIN_START = "2025-06-10 00:00:00"
WIN_END = "2025-06-13 00:00:00"


def validate_hb_1_8(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    r = pd.read_sql(
        text(
            f"SELECT AVG(o3) AS mean_o3, MAX(o3) AS max_o3, "
            f"COUNT(*) FILTER (WHERE o3 > 160) AS o3_exceedance_hours FROM hourly_station_air_quality "
            f"WHERE station_id = {STATION_ID} AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}'"
        ),
        engine,
    ).iloc[0]
    exp = {
        "mean_o3": float(r["mean_o3"]),
        "max_o3": float(r["max_o3"]),
        "o3_exceedance_hours": int(r["o3_exceedance_hours"]),
    }
    checks = [("mean_o3", "num", 2.0), ("max_o3", "num", 2.0), ("o3_exceedance_hours", "int", 0)]
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
                return ValidatorResult(False, f"{var}={val!r}, expected ~{round(e,1)} (tol {tol})")
    return ValidatorResult(True, f"Correct: mean O3={round(exp['mean_o3'],1)}, max O3={round(exp['max_o3'],0)}, {exp['o3_exceedance_hours']} hours > 160")


tools = []
variables = [
    Variable("mean_o3", None, "Mean O3 at East Sewage Treatment Plant station over 2025-06-10 to 2025-06-12 (float)."),
    Variable("max_o3", None, "Peak (max) hourly O3 over the window (float)."),
    Variable("o3_exceedance_hours", None, "Hours with O3 > 160 over the window (int)."),
]
validators = {"validate_hb_1_8": validate_hb_1_8}
