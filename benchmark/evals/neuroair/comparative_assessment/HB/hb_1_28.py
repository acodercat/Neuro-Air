"""Neuro-Air HB 1-28 (verbatim) — environmental quality: mountain vs plain county.

Original query evaluates environmental quality differences between mountainous Zanhuang
County (district_id 15) and plain-area Zhao County (district_id 19) on 2025-06-26. The
validator recomputes each county's daily mean PM2.5 and mean AQI that day. GT recomputed from DB.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

ZANHUANG = 15
ZHAO = 19
DAY = "2025-06-26"


def _means(did):
    r = pd.read_sql(
        text(
            f"SELECT AVG(pm2_5) AS pm, AVG(aqi) AS aqi FROM hourly_district_air_quality "
            f"WHERE district_id = {did} AND timestamp >= '{DAY}' AND timestamp < '{DAY}'::date + 1"
        ),
        engine,
    ).iloc[0]
    return float(r["pm"]), float(r["aqi"])


def validate_hb_1_28(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    z_pm, z_aqi = _means(ZANHUANG)
    h_pm, h_aqi = _means(ZHAO)
    exp = {
        "mean_pm25_zanhuang": z_pm, "mean_aqi_zanhuang": z_aqi,
        "mean_pm25_zhao": h_pm, "mean_aqi_zhao": h_aqi,
    }
    for var, tol in [("mean_pm25_zanhuang", 1.0), ("mean_aqi_zanhuang", 1.0), ("mean_pm25_zhao", 1.0), ("mean_aqi_zhao", 1.0)]:
        val = runtime.retrieve(var)
        if val is None:
            return ValidatorResult(False, f"{var} not set", variables_not_set=True)
        if not is_finite_number(val) or not compare_numeric(float(val), float(exp[var]), tolerance=tol):
            return ValidatorResult(False, f"{var}={val!r}, expected ~{round(exp[var],2)} (tol {tol})")
    return ValidatorResult(True, f"Correct: Zanhuang PM2.5={round(z_pm,1)}/AQI={round(z_aqi,1)}, Zhao PM2.5={round(h_pm,1)}/AQI={round(h_aqi,1)}")


tools = []
variables = [
    Variable("mean_pm25_zanhuang", None, "Mean PM2.5 in Zanhuang County on 2025-06-26 (float)."),
    Variable("mean_aqi_zanhuang", None, "Mean AQI in Zanhuang County that day (float)."),
    Variable("mean_pm25_zhao", None, "Mean PM2.5 in Zhao County that day (float)."),
    Variable("mean_aqi_zhao", None, "Mean AQI in Zhao County that day (float)."),
]
validators = {"validate_hb_1_28": validate_hb_1_28}
