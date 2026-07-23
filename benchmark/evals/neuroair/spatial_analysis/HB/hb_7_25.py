"""Neuro-Air HB 7-25 (verbatim) — single-hour emission impact on nearby stations.

Original query analyzes the impact of Hebei Zongheng Fengnan Steel (company_id 2467) emissions
on nearby air-quality monitoring stations on 2025-06-10 at 18:00. The validator recomputes that
single hour's exhaust_gas / NOx / SO2 / PM for the company and the number of air-quality stations
within 10km. GT recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

COMPANY_ID = 2467
TS = "2025-06-10 18:00:00"


def validate_hb_7_25(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    em = pd.read_sql(
        text(
            f"SELECT exhaust_gas, nox, so2, pm FROM hourly_polluting_company_emission "
            f"WHERE company_id = {COMPANY_ID} AND timestamp = '{TS}'"
        ),
        engine,
    )
    if em.empty:
        return ValidatorResult(False, "no emission row at the target hour")
    em = em.iloc[0]
    n10 = int(
        pd.read_sql(
            text(
                f"SELECT COUNT(*) AS c FROM air_quality_station s, polluting_company p "
                f"WHERE p.id = {COMPANY_ID} AND ST_DWithin(s.coordinate, p.coordinate, 10000)"
            ),
            engine,
        ).iloc[0]["c"]
    )
    exp = {
        "flue_gas_1800": float(em["exhaust_gas"]),
        "nox_1800": float(em["nox"]),
        "so2_1800": float(em["so2"]),
        "pm_1800": float(em["pm"]),
        "stations_within_10km": n10,
    }
    checks = [
        ("flue_gas_1800", "num", max(1.0, exp["flue_gas_1800"] * 0.005)),
        ("nox_1800", "num", max(0.5, exp["nox_1800"] * 0.01)),
        ("so2_1800", "num", max(0.5, exp["so2_1800"] * 0.01)),
        ("pm_1800", "num", max(0.5, exp["pm_1800"] * 0.01)),
        ("stations_within_10km", "int", 0),
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
                return ValidatorResult(False, f"{var}={val!r}, expected ~{round(e,2)} (tol {round(tol,2)})")
    return ValidatorResult(True, f"Correct: 18:00 flue gas={round(exp['flue_gas_1800'],0)}, {n10} stations within 10km")


tools = []
variables = [
    Variable("flue_gas_1800", None, "Flue-gas volume of company 2467 at 2025-06-10 18:00 (float)."),
    Variable("nox_1800", None, "NOx at that hour (float)."),
    Variable("so2_1800", None, "SO2 at that hour (float)."),
    Variable("pm_1800", None, "PM at that hour (float)."),
    Variable("stations_within_10km", None, "Number of air-quality monitoring stations whose location is within 10km of company 2467, by geographic distance, regardless of whether the station reported data at the target hour (int)."),
]
validators = {"validate_hb_7_25": validate_hb_7_25}
