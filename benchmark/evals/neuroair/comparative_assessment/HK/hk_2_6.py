"""Neuro-Air HK 2-6 (verbatim) — roadside NO2, morning vs evening rush.

Original query compares NO2 between 06:00-09:00 and 18:00-21:00 on 2025-01-20 across
roadside stations. The validator recomputes the mean NO2 across ROADSIDE stations over
each window, their difference, and which period is higher. GT recomputed from the DB.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HK.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

DAY = "2025-01-20"
ROADSIDE = "station_id IN (SELECT id FROM air_quality_station WHERE station_type = 'ROADSIDE')"


def _mean_no2(lo, hi):
    v = pd.read_sql(
        text(
            f"SELECT AVG(no2) AS v FROM hourly_station_air_quality WHERE {ROADSIDE} "
            f"AND datetime >= '{DAY}' AND datetime < '{DAY}'::date + 1 "
            f"AND EXTRACT(HOUR FROM datetime) >= {lo} AND EXTRACT(HOUR FROM datetime) < {hi}"
        ),
        engine,
    ).iloc[0]["v"]
    return float(v)


def validate_hk_2_6(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    am = _mean_no2(6, 9)
    pm = _mean_no2(18, 21)
    higher = "PM" if pm > am else "AM"
    exp = {"mean_no2_am": am, "mean_no2_pm": pm, "no2_difference": pm - am, "higher_no2_period": higher}
    for var, kind, tol in [("mean_no2_am", "num", 3.0), ("mean_no2_pm", "num", 3.0), ("no2_difference", "num", 5.0)]:
        val = runtime.retrieve(var)
        if val is None:
            return ValidatorResult(False, f"{var} not set", variables_not_set=True)
        e = exp[var]
        if not is_finite_number(val) or not compare_numeric(float(val), float(e), tolerance=tol):
            return ValidatorResult(False, f"{var}={val!r}, expected ~{round(e,1)} (tol {tol})")
    hp = runtime.retrieve("higher_no2_period")
    if hp is None:
        return ValidatorResult(False, "higher_no2_period not set", variables_not_set=True)
    if not (isinstance(hp, str) and hp.strip().upper() == higher):
        return ValidatorResult(False, f"higher_no2_period={hp!r}, expected {higher!r}")
    return ValidatorResult(True, f"Correct: NO2 AM={round(am,1)} vs PM={round(pm,1)}, higher = {higher}")


tools = []
variables = [
    Variable("mean_no2_am", None, "Mean NO2 across roadside stations 06:00-09:00 on 2025-01-20 (float)."),
    Variable("mean_no2_pm", None, "Mean NO2 across roadside stations 18:00-21:00 that day (float)."),
    Variable("no2_difference", None, "mean_no2_pm minus mean_no2_am (float)."),
    Variable("higher_no2_period", None, "Which period is higher, 'AM' or 'PM' (str)."),
]
validators = {"validate_hk_2_6": validate_hk_2_6}
