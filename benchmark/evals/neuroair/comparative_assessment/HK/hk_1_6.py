"""Neuro-Air HK 1-6 (verbatim) — air-quality comparison between two stations.
Compares station 16 (central) and station 5 (tuenmun) over 2025-06-01 to 2025-06-06: each station's mean PM2.5 and mean AQHI.
GT is recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HK.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

A_ID = 16
B_ID = 5
WIN_START = "2025-06-01 00:00:00"
WIN_END = "2025-06-07 00:00:00"


def _m(sid):
    r = pd.read_sql(text(f"SELECT AVG(pm2_5) AS pm, AVG(aqhi) AS aqhi FROM hourly_station_air_quality WHERE station_id = {sid} AND datetime >= '{WIN_START}' AND datetime < '{WIN_END}'"), engine).iloc[0]
    return float(r["pm"]), float(r["aqhi"])


def validate_hk_1_6(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    a_pm, a_q = _m(A_ID); b_pm, b_q = _m(B_ID)
    exp = {"mean_pm25_central": a_pm, "mean_aqhi_central": a_q, "mean_pm25_tuenmun": b_pm, "mean_aqhi_tuenmun": b_q}
    for var, tol in [("mean_pm25_central", 1.0), ("mean_aqhi_central", 0.2), ("mean_pm25_tuenmun", 1.0), ("mean_aqhi_tuenmun", 0.2)]:
        val = runtime.retrieve(var)
        if val is None:
            return ValidatorResult(False, f"{var} not set", variables_not_set=True)
        if not is_finite_number(val) or not compare_numeric(float(val), float(exp[var]), tolerance=tol):
            return ValidatorResult(False, f"{var}={val!r}, expected ~{round(exp[var],2)} (tol {tol})")
    return ValidatorResult(True, f"Correct: central PM2.5={round(a_pm,1)}/AQHI={round(a_q,2)}, tuenmun PM2.5={round(b_pm,1)}/AQHI={round(b_q,2)}")


tools = []
variables = [
    Variable("mean_pm25_central", None, "Mean PM2.5 at station 16 (central) over 2025-06-01 to 2025-06-06 (float)."),
    Variable("mean_aqhi_central", None, "Mean AQHI at station 16 over the window (float)."),
    Variable("mean_pm25_tuenmun", None, "Mean PM2.5 at station 5 (tuenmun) over the window (float)."),
    Variable("mean_aqhi_tuenmun", None, "Mean AQHI at station 5 over the window (float)."),
]
validators = {"validate_hk_1_6": validate_hk_1_6}
