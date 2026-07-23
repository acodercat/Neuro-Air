"""Neuro-Air HB 6-16 (verbatim) — plant emissions vs nearby recreational spaces.

Original query assesses how Shougang Jingtang Steel (company_id 2444) emissions affect
public recreational spaces (OSM leisure/public) over the weekend 2025-06-19 to 2025-06-21.
The validator recomputes the count of OSM leisure+public features within 5km of the plant
and the plant's total/peak/active flue-gas emission over the weekend. GT recomputed from DB.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

COMPANY_ID = 2444
WIN_START = "2025-06-19 00:00:00"
WIN_END = "2025-06-22 00:00:00"


def validate_hb_6_16(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    cnt = int(
        pd.read_sql(
            text(
                f"SELECT COUNT(*) AS c FROM osm_feature o, polluting_company p "
                f"WHERE p.id = {COMPANY_ID} AND o.main_type IN ('LEISURE', 'PUBLIC') "
                f"AND ST_DWithin(o.geometry, p.coordinate, 5000)"
            ),
            engine,
        ).iloc[0]["c"]
    )
    em = pd.read_sql(
        text(
            f"SELECT SUM(exhaust_gas) AS total_flue_gas, MAX(exhaust_gas) AS peak_flue_gas, "
            f"COUNT(*) FILTER (WHERE exhaust_gas > 0) AS active_hours "
            f"FROM hourly_polluting_company_emission WHERE company_id = {COMPANY_ID} "
            f"AND timestamp >= '{WIN_START}' AND timestamp < '{WIN_END}'"
        ),
        engine,
    ).iloc[0]
    exp = {
        "recreational_count_within_5km": cnt,
        "total_flue_gas": float(em["total_flue_gas"]),
        "peak_flue_gas": float(em["peak_flue_gas"]),
        "active_hours": int(em["active_hours"]),
    }
    checks = [
        ("recreational_count_within_5km", "int", 0),
        ("total_flue_gas", "num", max(1.0, exp["total_flue_gas"] * 0.005)),
        ("peak_flue_gas", "num", max(1.0, exp["peak_flue_gas"] * 0.005)),
        ("active_hours", "int", 0),
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
                return ValidatorResult(False, f"{var}={val!r}, expected ~{round(e,1)} (tol {round(tol,1)})")
    return ValidatorResult(True, f"Correct: {cnt} recreational features within 5km, weekend flue gas={round(exp['total_flue_gas'],0)}")


tools = []
variables = [
    Variable("recreational_count_within_5km", None, "Count of OSM leisure/public features within 5km of company 2444 (int)."),
    Variable("total_flue_gas", None, "Total weekend flue-gas volume (2025-06-19 to 2025-06-21) (float)."),
    Variable("peak_flue_gas", None, "Peak hourly flue-gas volume over the weekend (float)."),
    Variable("active_hours", None, "Number of hours with positive flue-gas volume over the weekend (int)."),
]
validators = {"validate_hb_6_16": validate_hb_6_16}
