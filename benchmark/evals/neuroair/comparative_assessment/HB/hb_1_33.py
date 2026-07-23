"""Neuro-Air HB 1-33 (verbatim) — highest-emission district in Baoding (morning window).

Original query asks which of Lianchi (district_id 92), Jingxiu (91) or Mancheng (93)
had the highest emission intensity on 2025-06-05 during 06:00-10:00. Emission intensity
is fixed as the total exhaust_gas over all polluting companies in the district (the
requirements state this). A district with no companies contributes 0. The validator
recomputes each district's total and the district with the highest. GT recomputed from
the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

DISTRICTS = {92: "lianchi", 91: "jingxiu", 93: "mancheng"}
WIN_START = "2025-06-05 06:00:00"
WIN_END = "2025-06-05 10:00:00"


def _district_total(did):
    v = pd.read_sql(
        text(
            f"SELECT COALESCE(SUM(e.exhaust_gas), 0) AS v "
            f"FROM hourly_polluting_company_emission e JOIN polluting_company p ON e.company_id = p.id "
            f"WHERE p.district_id = {did} AND e.timestamp >= '{WIN_START}' AND e.timestamp < '{WIN_END}'"
        ),
        engine,
    ).iloc[0]["v"]
    return float(v)


def validate_hb_1_33(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    totals = {did: _district_total(did) for did in DISTRICTS}
    highest = max(totals, key=lambda d: totals[d])

    exp = {
        "total_exhaust_lianchi": totals[92],
        "total_exhaust_jingxiu": totals[91],
        "total_exhaust_mancheng": totals[93],
        "highest_intensity_district_id": highest,
    }
    checks = [
        ("total_exhaust_lianchi", "num", max(1.0, totals[92] * 0.005)),
        ("total_exhaust_jingxiu", "num", max(1.0, totals[91] * 0.005)),
        ("total_exhaust_mancheng", "num", max(1.0, totals[93] * 0.005)),
        ("highest_intensity_district_id", "int", 0),
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
    return ValidatorResult(True, f"Correct: highest = district {highest} (Mancheng {round(totals[93],0)} > Jingxiu {round(totals[91],0)}; Lianchi {round(totals[92],0)})")


tools = []
variables = [
    Variable("total_exhaust_lianchi", None, "Total flue-gas volume of companies in Lianchi, 2025-06-05 06:00-10:00 (float; 0 if none)."),
    Variable("total_exhaust_jingxiu", None, "Total flue-gas volume of companies in Jingxiu, same window (float)."),
    Variable("total_exhaust_mancheng", None, "Total flue-gas volume of companies in Mancheng, same window (float)."),
    Variable("highest_intensity_district_id", None, "the district_id of the district with the highest total flue-gas volume (int)."),
]
validators = {"validate_hb_1_33": validate_hb_1_33}
