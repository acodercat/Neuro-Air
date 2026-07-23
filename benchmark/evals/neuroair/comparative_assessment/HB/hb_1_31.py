"""Neuro-Air HB 1-31 (verbatim) — district emission comparison in Shijiazhuang.

Original query compares the emission levels between Chang'an District (district_id 1)
and Jingxing Mining District (district_id 4) on 2025-06-15 from 08:00 to 18:00.
District emission is the sum of exhaust_gas over all polluting companies located in
that district. The validator recomputes each district's total, which district is higher,
and the ratio. GT recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

CHANGAN = 1
JINGXING = 4
WIN_START = "2025-06-15 08:00:00"
WIN_END = "2025-06-15 18:00:00"


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


def validate_hb_1_31(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    changan = _district_total(CHANGAN)
    jingxing = _district_total(JINGXING)
    higher = CHANGAN if changan > jingxing else JINGXING
    ratio = (max(changan, jingxing) / min(changan, jingxing)) if min(changan, jingxing) > 0 else float("inf")

    exp = {
        "total_exhaust_changan": changan,
        "total_exhaust_jingxing": jingxing,
        "higher_emission_district_id": higher,
        "emission_ratio": round(ratio, 2),
    }
    checks = [
        ("total_exhaust_changan", "num", max(1.0, changan * 0.005)),
        ("total_exhaust_jingxing", "num", max(1.0, jingxing * 0.005)),
        ("higher_emission_district_id", "int", 0),
        ("emission_ratio", "num", 0.2),
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
    return ValidatorResult(True, f"Correct: Jingxing={round(jingxing,0)} vs Chang'an={round(changan,0)}, higher=district {higher} (x{exp['emission_ratio']})")


tools = []
variables = [
    Variable("total_exhaust_changan", None, "Total flue-gas volume of companies in Chang'an District, 2025-06-15 08:00-18:00 (float)."),
    Variable("total_exhaust_jingxing", None, "Total flue-gas volume of companies in Jingxing Mining District, same window (float)."),
    Variable("higher_emission_district_id", None, "the district_id of the district with the higher total emission (int)."),
    Variable("emission_ratio", None, "Higher total divided by lower total (float, 2dp)."),
]
validators = {"validate_hb_1_31": validate_hb_1_31}
