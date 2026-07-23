"""Neuro-Air HB 1-32 (verbatim) — industrial emission profile for a district.

Original query compares the industrial emission patterns in Congtai District (district_id 53)
on 2025-06-10. The validator recomputes that day's district-wide industrial emission profile:
total flue-gas volume across all companies in the district, the number of companies with data,
the single top-emitting company and its total. GT recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

DISTRICT_ID = 53  # Congtai District
DAY = "2025-06-10"


def validate_hb_1_32(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    agg = pd.read_sql(
        text(
            f"SELECT SUM(e.exhaust_gas) AS total, COUNT(DISTINCT e.company_id) AS ncomp "
            f"FROM hourly_polluting_company_emission e JOIN polluting_company p ON e.company_id = p.id "
            f"WHERE p.district_id = {DISTRICT_ID} AND e.timestamp >= '{DAY}' AND e.timestamp < '{DAY}'::date + 1"
        ),
        engine,
    ).iloc[0]
    # "companies with emission data that day" is genuinely ambiguous: some companies
    # have a daily-aggregate record but no hourly rows that day. Accept EITHER the count
    # of companies with HOURLY records or with DAILY records (both are defensible).
    ncomp_daily = int(
        pd.read_sql(
            text(
                f"SELECT COUNT(DISTINCT e.company_id) AS c FROM daily_polluting_company_emission e "
                f"JOIN polluting_company p ON e.company_id = p.id "
                f"WHERE p.district_id = {DISTRICT_ID} AND e.date = '{DAY}'"
            ),
            engine,
        ).iloc[0]["c"]
    )
    company_counts = {int(agg["ncomp"]), ncomp_daily}
    top = pd.read_sql(
        text(
            f"SELECT e.company_id, SUM(e.exhaust_gas) AS t FROM hourly_polluting_company_emission e "
            f"JOIN polluting_company p ON e.company_id = p.id "
            f"WHERE p.district_id = {DISTRICT_ID} AND e.timestamp >= '{DAY}' AND e.timestamp < '{DAY}'::date + 1 "
            f"GROUP BY e.company_id ORDER BY t DESC LIMIT 1"
        ),
        engine,
    ).iloc[0]

    exp = {
        "total_district_flue_gas": float(agg["total"]),
        "company_count": int(agg["ncomp"]),
        "top_emitter_company_id": int(top["company_id"]),
        "top_emitter_total": float(top["t"]),
    }
    checks = [
        ("total_district_flue_gas", "num", max(1.0, exp["total_district_flue_gas"] * 0.005)),
        ("top_emitter_company_id", "int", 0),
        ("top_emitter_total", "num", max(1.0, exp["top_emitter_total"] * 0.005)),
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
    cc = runtime.retrieve("company_count")
    if cc is None:
        return ValidatorResult(False, "company_count not set", variables_not_set=True)
    if not is_finite_number(cc) or int(cc) not in company_counts:
        return ValidatorResult(False, f"company_count={cc!r}, expected one of {sorted(company_counts)}")
    return ValidatorResult(True, f"Correct: district total={round(exp['total_district_flue_gas'],0)}, {exp['company_count']} companies, top emitter {exp['top_emitter_company_id']}")


tools = []
variables = [
    Variable("total_district_flue_gas", None, "Total flue-gas volume across all companies in Congtai District on 2025-06-10 (float)."),
    Variable("company_count", None, "Number of companies with emission data in the district that day (int)."),
    Variable("top_emitter_company_id", None, "The single highest-emitting company in the district that day (int)."),
    Variable("top_emitter_total", None, "That top emitter's total flue-gas volume that day (float)."),
]
validators = {"validate_hb_1_32": validate_hb_1_32}
