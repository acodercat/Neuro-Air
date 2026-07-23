"""Neuro-Air HK 3-11 (verbatim) — roadside NO2 across morning/lunch/evening windows.

Original query compares NO2 during morning rush (7-9 AM), lunch (12-2 PM) and evening rush
(6-8 PM) at roadside stations on 2025-06-10. The validator recomputes the mean NO2 across
ROADSIDE stations in each window and the highest-NO2 window. GT recomputed from the DB.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HK.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

DAY = "2025-06-10"
ROADSIDE = "station_id IN (SELECT id FROM air_quality_station WHERE station_type = 'ROADSIDE')"
WINDOWS = {"am": (7, 9), "lunch": (12, 14), "pm": (18, 20)}


def _mean(lo, hi):
    v = pd.read_sql(
        text(
            f"SELECT AVG(no2) AS v FROM hourly_station_air_quality WHERE {ROADSIDE} "
            f"AND datetime >= '{DAY}' AND datetime < '{DAY}'::date + 1 "
            f"AND EXTRACT(HOUR FROM datetime) >= {lo} AND EXTRACT(HOUR FROM datetime) < {hi}"
        ),
        engine,
    ).iloc[0]["v"]
    return float(v)


def validate_hk_3_11(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    means = {k: _mean(*w) for k, w in WINDOWS.items()}
    highest = max(means, key=lambda k: means[k]).upper()
    exp = {
        "mean_no2_am": means["am"], "mean_no2_lunch": means["lunch"], "mean_no2_pm": means["pm"],
        "highest_no2_window": highest,
    }
    for var, tol in [("mean_no2_am", 2.0), ("mean_no2_lunch", 2.0), ("mean_no2_pm", 2.0)]:
        val = runtime.retrieve(var)
        if val is None:
            return ValidatorResult(False, f"{var} not set", variables_not_set=True)
        if not is_finite_number(val) or not compare_numeric(float(val), float(exp[var]), tolerance=tol):
            return ValidatorResult(False, f"{var}={val!r}, expected ~{round(exp[var],1)} (tol {tol})")
    hw = runtime.retrieve("highest_no2_window")
    if hw is None:
        return ValidatorResult(False, "highest_no2_window not set", variables_not_set=True)
    if not (isinstance(hw, str) and hw.strip().upper() == highest):
        return ValidatorResult(False, f"highest_no2_window={hw!r}, expected {highest!r}")
    return ValidatorResult(True, f"Correct: NO2 AM={round(means['am'],1)}/lunch={round(means['lunch'],1)}/PM={round(means['pm'],1)}, highest={highest}")


tools = []
variables = [
    Variable("mean_no2_am", None, "Mean NO2 across roadside stations 07:00-09:00 on 2025-06-10 (float)."),
    Variable("mean_no2_lunch", None, "Mean NO2 across roadside stations 12:00-14:00 that day (float)."),
    Variable("mean_no2_pm", None, "Mean NO2 across roadside stations 18:00-20:00 that day (float)."),
    Variable("highest_no2_window", None, "Which window has the highest NO2: 'AM', 'LUNCH' or 'PM' (str)."),
]
validators = {"validate_hk_3_11": validate_hk_3_11}
