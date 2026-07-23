"""Neuro-Air HK 1-11 (verbatim) — roadside CO, peak (08:00) vs off-peak (14:00).

Original query compares CO at roadside stations during peak (08:00) vs off-peak (14:00)
on 2025-01-22. The validator recomputes the mean CO across all ROADSIDE stations at
hour 08 and at hour 14 that day, their difference, and the number of roadside stations.
GT is recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HK.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

DAY = "2025-01-22"
ROADSIDE = "station_id IN (SELECT id FROM air_quality_station WHERE station_type = 'ROADSIDE')"


def _mean_co(hour):
    r = pd.read_sql(
        text(
            f"SELECT AVG(co) AS v, COUNT(DISTINCT station_id) AS ns FROM hourly_station_air_quality "
            f"WHERE {ROADSIDE} AND datetime >= '{DAY}' AND datetime < '{DAY}'::date + 1 "
            f"AND EXTRACT(HOUR FROM datetime) = {hour}"
        ),
        engine,
    ).iloc[0]
    return float(r["v"]), int(r["ns"])


def validate_hk_1_11(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    co8, ns = _mean_co(8)
    co14, _ = _mean_co(14)
    exp = {
        "mean_co_0800": co8,
        "mean_co_1400": co14,
        "co_difference": co8 - co14,
        "n_roadside_stations": ns,
    }
    checks = [
        ("mean_co_0800", "num", 5.0), ("mean_co_1400", "num", 5.0),
        ("co_difference", "num", 8.0), ("n_roadside_stations", "int", 0),
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
                return ValidatorResult(False, f"{var}={val!r}, expected ~{round(e,1)} (tol {tol})")
    return ValidatorResult(True, f"Correct: CO 08:00={round(co8,1)} vs 14:00={round(co14,1)} over {ns} roadside stations")


tools = []
variables = [
    Variable("mean_co_0800", None, "Mean CO across roadside stations at 08:00 on 2025-01-22 (float)."),
    Variable("mean_co_1400", None, "Mean CO across roadside stations at 14:00 that day (float)."),
    Variable("co_difference", None, "mean_co_0800 minus mean_co_1400 (float)."),
    Variable("n_roadside_stations", None, "Number of roadside stations included (int)."),
]
validators = {"validate_hk_1_11": validate_hk_1_11}
