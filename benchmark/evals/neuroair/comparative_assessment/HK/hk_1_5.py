"""Neuro-Air HK 1-5 (verbatim) — air-quality comparison between two stations.
Compares station 6 (tungchung) and station 8 (tapmun) over 2025-06-15: each station's mean PM2.5 and mean AQHI.
GT is recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HK.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

A_ID = 6
B_ID = 8
WIN_START = "2025-06-15 00:00:00"
WIN_END = "2025-06-16 00:00:00"


def _m(sid):
    r = pd.read_sql(text(f"SELECT AVG(pm2_5) AS pm, AVG(aqhi) AS aqhi FROM hourly_station_air_quality WHERE station_id = {sid} AND datetime >= '{WIN_START}' AND datetime < '{WIN_END}'"), engine).iloc[0]
    return float(r["pm"]), float(r["aqhi"])


def validate_hk_1_5(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    a_pm, a_q = _m(A_ID); b_pm, b_q = _m(B_ID)
    exp = {"mean_pm25_tungchung": a_pm, "mean_aqhi_tungchung": a_q, "mean_pm25_tapmun": b_pm, "mean_aqhi_tapmun": b_q}
    for var, tol in [("mean_pm25_tungchung", 1.0), ("mean_aqhi_tungchung", 0.2), ("mean_pm25_tapmun", 1.0), ("mean_aqhi_tapmun", 0.2)]:
        val = runtime.retrieve(var)
        if val is None:
            return ValidatorResult(False, f"{var} not set", variables_not_set=True)
        if not is_finite_number(val) or not compare_numeric(float(val), float(exp[var]), tolerance=tol):
            return ValidatorResult(False, f"{var}={val!r}, expected ~{round(exp[var],2)} (tol {tol})")
    return ValidatorResult(True, f"Correct: tungchung PM2.5={round(a_pm,1)}/AQHI={round(a_q,2)}, tapmun PM2.5={round(b_pm,1)}/AQHI={round(b_q,2)}")


tools = []
variables = [
    Variable("mean_pm25_tungchung", None, "Mean PM2.5 at station 6 (tungchung) over 2025-06-15 (float)."),
    Variable("mean_aqhi_tungchung", None, "Mean AQHI at station 6 over the window (float)."),
    Variable("mean_pm25_tapmun", None, "Mean PM2.5 at station 8 (tapmun) over the window (float)."),
    Variable("mean_aqhi_tapmun", None, "Mean AQHI at station 8 over the window (float)."),
]
validators = {"validate_hk_1_5": validate_hk_1_5}
