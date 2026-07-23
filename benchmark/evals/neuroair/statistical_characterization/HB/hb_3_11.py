"""Neuro-Air HB 3-11 (verbatim) — the five most polluted stations in Shijiazhuang.

Original query analyzes the hourly pollution trends of the 5 most polluted stations in
Shijiazhuang (city_id 1) on 2025-06-20 and cross-station transport. The validator
recomputes each city-1 station's daily mean AQI on 2025-06-20, ranks them, and checks
the set of the top-5 station ids, the single most-polluted station, and its mean AQI.
GT is recomputed from the DB on every call. (Rank-5 vs rank-6 differ by ~1.2 AQI, so
the top-5 set is well-defined.)
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

CITY_ID = 1  # Shijiazhuang
DAY_START = "2025-06-20 00:00:00"
DAY_END = "2025-06-21 00:00:00"


def validate_hb_3_11(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    df = pd.read_sql(
        text(
            f"SELECT station_id, AVG(aqi) AS mean_aqi FROM hourly_station_air_quality "
            f"WHERE station_id IN (SELECT id FROM air_quality_station WHERE city_id = {CITY_ID}) "
            f"AND timestamp >= '{DAY_START}' AND timestamp < '{DAY_END}' "
            f"GROUP BY station_id ORDER BY mean_aqi DESC"
        ),
        engine,
    )
    top5 = [int(x) for x in df["station_id"].head(5)]
    most_polluted = int(df["station_id"].iloc[0])
    most_mean = float(df["mean_aqi"].iloc[0])

    # top-5 set
    val = runtime.retrieve("top5_station_ids")
    if val is None:
        return ValidatorResult(False, "top5_station_ids not set", variables_not_set=True)
    try:
        got = set(int(x) for x in val)
    except (TypeError, ValueError):
        return ValidatorResult(False, f"top5_station_ids not a list of ids: {val!r}")
    if got != set(top5):
        return ValidatorResult(False, f"top5_station_ids={sorted(got)}, expected {sorted(top5)}")

    mp = runtime.retrieve("most_polluted_station_id")
    if mp is None:
        return ValidatorResult(False, "most_polluted_station_id not set", variables_not_set=True)
    if not is_finite_number(mp) or int(mp) != most_polluted:
        return ValidatorResult(False, f"most_polluted_station_id={mp!r}, expected {most_polluted}")

    mm = runtime.retrieve("most_polluted_mean_aqi")
    if mm is None:
        return ValidatorResult(False, "most_polluted_mean_aqi not set", variables_not_set=True)
    if not is_finite_number(mm) or not compare_numeric(float(mm), most_mean, tolerance=2.0):
        return ValidatorResult(False, f"most_polluted_mean_aqi={mm!r}, expected ~{round(most_mean,1)}")

    return ValidatorResult(True, f"Correct: top5={sorted(top5)}, most polluted station {most_polluted} (mean AQI {round(most_mean,1)})")


tools = []
variables = [
    Variable("top5_station_ids", None, "List/set of the 5 station numbers with the highest daily mean AQI on 2025-06-20 (list of int)."),
    Variable("most_polluted_station_id", None, "The single most polluted station number (highest mean AQI) (int)."),
    Variable("most_polluted_mean_aqi", None, "Daily mean AQI of that most-polluted station (float)."),
]
validators = {"validate_hb_3_11": validate_hb_3_11}
