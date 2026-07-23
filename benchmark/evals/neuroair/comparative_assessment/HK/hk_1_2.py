"""Neuro-Air HK 1-2 (verbatim) — pre- vs post-typhoon network-wide air quality.

Original query analyzes pre-typhoon versus post-typhoon air-quality patterns over 2025-07-19
to 2025-07-21 and the pollution clearance effectiveness. The validator recomputes the
network-wide (all stations) mean PM2.5 and mean AQHI on the pre day (2025-07-19) and the post
day (2025-07-21), and the PM2.5 clearance (pre minus post). GT recomputed from the DB.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HK.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

PRE = "2025-07-19"
POST = "2025-07-21"


def _net(day):
    r = pd.read_sql(
        text(
            f"SELECT AVG(pm2_5) AS pm, AVG(aqhi) AS aqhi FROM hourly_station_air_quality "
            f"WHERE datetime >= '{day}' AND datetime < '{day}'::date + 1"
        ),
        engine,
    ).iloc[0]
    return float(r["pm"]), float(r["aqhi"])


def validate_hk_1_2(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    pre_pm, pre_q = _net(PRE)
    post_pm, post_q = _net(POST)
    exp = {
        "net_pm25_pre": pre_pm, "net_aqhi_pre": pre_q,
        "net_pm25_post": post_pm, "net_aqhi_post": post_q,
        "pm25_clearance": pre_pm - post_pm,
    }
    for var, tol in [("net_pm25_pre", 1.0), ("net_aqhi_pre", 0.2), ("net_pm25_post", 1.0), ("net_aqhi_post", 0.2), ("pm25_clearance", 1.5)]:
        val = runtime.retrieve(var)
        if val is None:
            return ValidatorResult(False, f"{var} not set", variables_not_set=True)
        if not is_finite_number(val) or not compare_numeric(float(val), float(exp[var]), tolerance=tol):
            return ValidatorResult(False, f"{var}={val!r}, expected ~{round(exp[var],2)} (tol {tol})")
    return ValidatorResult(True, f"Correct: pre PM2.5={round(pre_pm,1)} -> post PM2.5={round(post_pm,1)} (clearance {round(pre_pm-post_pm,1)})")


tools = []
variables = [
    Variable("net_pm25_pre", None, "Network-wide mean PM2.5 across all HK stations on 2025-07-19 (pre-typhoon) (float)."),
    Variable("net_aqhi_pre", None, "Network-wide mean AQHI on 2025-07-19 (float)."),
    Variable("net_pm25_post", None, "Network-wide mean PM2.5 on 2025-07-21 (post-typhoon) (float)."),
    Variable("net_aqhi_post", None, "Network-wide mean AQHI on 2025-07-21 (float)."),
    Variable("pm25_clearance", None, "PM2.5 clearance = pre minus post network mean PM2.5 (float)."),
]
validators = {"validate_hk_1_2": validate_hk_1_2}
