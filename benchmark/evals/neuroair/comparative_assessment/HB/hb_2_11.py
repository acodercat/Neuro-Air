"""Neuro-Air HB 2-11 (verbatim) — pollution comparison between two stations.

Original query analyzes pollution levels between Ligong station (离宫, station_id 276) and
North Pump House station (北泵房, station_id 238) on 2025-06-25. The validator recomputes each
station's daily mean PM2.5 and mean AQI that day. GT recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

LIGONG = 276
PUMPHOUSE = 238
DAY = "2025-06-25"


def _means(sid):
    r = pd.read_sql(
        text(
            f"SELECT AVG(pm2_5) AS pm, AVG(aqi) AS aqi FROM hourly_station_air_quality "
            f"WHERE station_id = {sid} AND timestamp >= '{DAY}' AND timestamp < '{DAY}'::date + 1"
        ),
        engine,
    ).iloc[0]
    return float(r["pm"]), float(r["aqi"])


def validate_hb_2_11(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    l_pm, l_aqi = _means(LIGONG)
    p_pm, p_aqi = _means(PUMPHOUSE)
    exp = {
        "mean_pm25_ligong": l_pm, "mean_aqi_ligong": l_aqi,
        "mean_pm25_pumphouse": p_pm, "mean_aqi_pumphouse": p_aqi,
    }
    for var, tol in [("mean_pm25_ligong", 1.0), ("mean_aqi_ligong", 1.0), ("mean_pm25_pumphouse", 1.0), ("mean_aqi_pumphouse", 1.0)]:
        val = runtime.retrieve(var)
        if val is None:
            return ValidatorResult(False, f"{var} not set", variables_not_set=True)
        if not is_finite_number(val) or not compare_numeric(float(val), float(exp[var]), tolerance=tol):
            return ValidatorResult(False, f"{var}={val!r}, expected ~{round(exp[var],2)} (tol {tol})")
    return ValidatorResult(True, f"Correct: Ligong PM2.5={round(l_pm,1)}/AQI={round(l_aqi,1)}, North Pump House PM2.5={round(p_pm,1)}/AQI={round(p_aqi,1)}")


tools = []
variables = [
    Variable("mean_pm25_ligong", None, "Mean PM2.5 at Ligong station on 2025-06-25 (float)."),
    Variable("mean_aqi_ligong", None, "Mean AQI at Ligong station that day (float)."),
    Variable("mean_pm25_pumphouse", None, "Mean PM2.5 at North Pump House station that day (float)."),
    Variable("mean_aqi_pumphouse", None, "Mean AQI at North Pump House station that day (float)."),
]
validators = {"validate_hb_2_11": validate_hb_2_11}
