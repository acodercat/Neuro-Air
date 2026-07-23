"""Neuro-Air HB 2-12 (verbatim) — Fengnan Steel's peak-hour emission and 15km neighbourhood.

Original query analyzes the differential impact of Hebei Zongheng Fengnan Steel (company_id
2467) on air-quality stations within a 15km radius during 2025-06-15 peak emission hours. The
validator recomputes the number of stations within 15km, the plant's peak and total flue-gas
volume that day, and the hour-of-day of the emission peak. GT recomputed from the DB.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

COMPANY_ID = 2467
DAY = "2025-06-15"


def validate_hb_2_12(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    n15 = int(
        pd.read_sql(
            text(
                f"SELECT COUNT(*) AS c FROM air_quality_station s, polluting_company p "
                f"WHERE p.id = {COMPANY_ID} AND ST_DWithin(s.coordinate, p.coordinate, 15000)"
            ),
            engine,
        ).iloc[0]["c"]
    )
    r = pd.read_sql(
        text(
            f"SELECT MAX(exhaust_gas) AS peak_flue_gas, SUM(exhaust_gas) AS total_flue_gas "
            f"FROM hourly_polluting_company_emission WHERE company_id = {COMPANY_ID} "
            f"AND timestamp >= '{DAY}' AND timestamp < '{DAY}'::date + 1"
        ),
        engine,
    ).iloc[0]
    # Accept ANY hour achieving the max exhaust_gas: on a tie there are several
    # legitimate "peak hours", so the validator must not demand one arbitrary pick.
    peak_hours = {
        int(h) for h in pd.read_sql(
            text(
                f"SELECT EXTRACT(HOUR FROM timestamp) AS hod FROM hourly_polluting_company_emission "
                f"WHERE company_id = {COMPANY_ID} AND timestamp >= '{DAY}' AND timestamp < '{DAY}'::date + 1 "
                f"AND exhaust_gas = (SELECT MAX(exhaust_gas) FROM hourly_polluting_company_emission "
                f"WHERE company_id = {COMPANY_ID} AND timestamp >= '{DAY}' AND timestamp < '{DAY}'::date + 1)"
            ),
            engine,
        )["hod"]
    }
    exp = {
        "stations_within_15km": n15,
        "peak_flue_gas": float(r["peak_flue_gas"]),
        "total_flue_gas": float(r["total_flue_gas"]),
    }
    checks = [
        ("stations_within_15km", "int", 0),
        ("peak_flue_gas", "num", max(1.0, exp["peak_flue_gas"] * 0.005)),
        ("total_flue_gas", "num", max(1.0, exp["total_flue_gas"] * 0.005)),
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
    pk = runtime.retrieve("peak_flue_gas_hour_of_day")
    if pk is None:
        return ValidatorResult(False, "peak_flue_gas_hour_of_day not set", variables_not_set=True)
    if not is_finite_number(pk) or int(pk) not in peak_hours:
        return ValidatorResult(False, f"peak_flue_gas_hour_of_day={pk!r}, expected one of {sorted(peak_hours)}")
    return ValidatorResult(True, f"Correct: {n15} stations within 15km, peak flue gas {round(exp['peak_flue_gas'],0)} at hour {sorted(peak_hours)}")


tools = []
variables = [
    Variable("stations_within_15km", None, "Number of air-quality stations within 15km of Hebei Zongheng Fengnan Steel (int)."),
    Variable("peak_flue_gas", None, "Peak hourly flue-gas volume of Hebei Zongheng Fengnan Steel on 2025-06-15 (float)."),
    Variable("total_flue_gas", None, "Total flue-gas volume that day (float)."),
    Variable("peak_flue_gas_hour_of_day", None, "Hour-of-day (0-23) of the emission peak (int)."),
]
validators = {"validate_hb_2_12": validate_hb_2_12}
