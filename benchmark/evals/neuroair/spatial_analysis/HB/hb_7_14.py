"""Neuro-Air HB 7-14 (verbatim) — single-hour emission of a steel plant and its neighbourhood.

Original query evaluates how Jingye Metallurgical Technology (company_id 2417) emissions
affected nearby residential areas on 2025-06-10 at 08:00. The validator recomputes that
single hour's exhaust_gas / NOx / SO2 / PM for the company and the number of air-quality
stations within 10km of it. GT is recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

COMPANY_ID = 2417
TS = "2025-06-10 08:00:00"


def validate_hb_7_14(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
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
        "flue_gas_0800": float(em["exhaust_gas"]),
        "nox_0800": float(em["nox"]),
        "so2_0800": float(em["so2"]),
        "pm_0800": float(em["pm"]),
        "stations_within_10km": n10,
    }
    checks = [
        ("flue_gas_0800", "num", max(1.0, exp["flue_gas_0800"] * 0.005)),
        ("nox_0800", "num", max(0.5, exp["nox_0800"] * 0.01)),
        ("so2_0800", "num", max(0.5, exp["so2_0800"] * 0.01)),
        ("pm_0800", "num", max(0.5, exp["pm_0800"] * 0.01)),
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
    return ValidatorResult(True, f"Correct: 08:00 flue gas={round(exp['flue_gas_0800'],0)}, {n10} stations within 10km")


tools = []
variables = [
    Variable("flue_gas_0800", None, "Flue-gas volume of company 2417 at 2025-06-10 08:00 (float)."),
    Variable("nox_0800", None, "NOx at that hour (float)."),
    Variable("so2_0800", None, "SO2 at that hour (float)."),
    Variable("pm_0800", None, "PM at that hour (float)."),
    Variable("stations_within_10km", None, "Number of air-quality stations within 10km of company 2417 (int)."),
]
validators = {"validate_hb_7_14": validate_hb_7_14}
