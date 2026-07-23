"""Neuro-Air HK 1-13 (verbatim) — Central vs Tuen Mun AQHI over a week.

Original query compares AQHI between Central (station_id 16) and Tuen Mun (station_id 5)
from 2025-01-20 to 2025-01-26 and identifies peak pollution periods. The mean AQHI of
the two stations is nearly equal, so the validator grades the two means (by value) plus
the two peak (max) AQHI, and the station with the higher peak (robust: 7 vs 6). GT is
recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HK.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

CENTRAL = 16
TUEN_MUN = 5
WIN_START = "2025-01-20 00:00:00"
WIN_END = "2025-01-27 00:00:00"


def _aqhi(sid):
    r = pd.read_sql(
        text(
            f"SELECT AVG(aqhi) AS mean_aqhi, MAX(aqhi) AS max_aqhi FROM hourly_station_air_quality "
            f"WHERE station_id = {sid} AND datetime >= '{WIN_START}' AND datetime < '{WIN_END}'"
        ),
        engine,
    ).iloc[0]
    return float(r["mean_aqhi"]), float(r["max_aqhi"])


def validate_hk_1_13(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    mc, xc = _aqhi(CENTRAL)
    mt, xt = _aqhi(TUEN_MUN)
    higher_peak = CENTRAL if xc > xt else TUEN_MUN
    exp = {
        "mean_aqhi_central": mc, "mean_aqhi_tuenmun": mt,
        "max_aqhi_central": xc, "max_aqhi_tuenmun": xt,
        "higher_peak_station_id": higher_peak,
    }
    checks = [
        ("mean_aqhi_central", "num", 0.2), ("mean_aqhi_tuenmun", "num", 0.2),
        ("max_aqhi_central", "num", 0.5), ("max_aqhi_tuenmun", "num", 0.5),
        ("higher_peak_station_id", "int", 0),
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
                return ValidatorResult(False, f"{var}={val!r}, expected ~{round(e,2)} (tol {tol})")
    return ValidatorResult(True, f"Correct: mean AQHI Central={round(mc,2)}/Tuen Mun={round(mt,2)}, higher peak = station {higher_peak}")


tools = []
variables = [
    Variable("mean_aqhi_central", None, "Mean AQHI at Central (station 16), 2025-01-20 to 2025-01-26 (float)."),
    Variable("mean_aqhi_tuenmun", None, "Mean AQHI at Tuen Mun (station 5), same window (float)."),
    Variable("max_aqhi_central", None, "Peak (max) AQHI at Central over the window (float)."),
    Variable("max_aqhi_tuenmun", None, "Peak (max) AQHI at Tuen Mun over the window (float)."),
    Variable("higher_peak_station_id", None, "station number (16 or 5) with the higher peak AQHI (int)."),
]
validators = {"validate_hk_1_13": validate_hk_1_13}
