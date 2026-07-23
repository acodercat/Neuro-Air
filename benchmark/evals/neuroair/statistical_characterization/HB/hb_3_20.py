"""Neuro-Air HB 3-20 (verbatim) — five most polluted stations province-wide at a given hour.

Original query analyzes the 5 most severely polluted stations province-wide at 2025-06-11
09:00. The validator recomputes, across ALL Hebei stations at that single hour, the set of the
5 stations with the highest AQI, the single most-polluted station and its AQI. (Rank-5 vs rank-6
differ by ~9 AQI, so the top-5 set is well-defined.) GT recomputed from the DB on every call.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HB.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number, compare_numeric

TS = "2025-06-11 09:00:00"


def validate_hb_3_20(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    df = pd.read_sql(
        text(
            f"SELECT station_id, aqi FROM hourly_station_air_quality "
            f"WHERE timestamp = '{TS}' AND aqi IS NOT NULL ORDER BY aqi DESC"
        ),
        engine,
    )
    top5 = [int(x) for x in df["station_id"].head(5)]
    most = int(df["station_id"].iloc[0])
    most_aqi = float(df["aqi"].iloc[0])

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
    if not is_finite_number(mp) or int(mp) != most:
        return ValidatorResult(False, f"most_polluted_station_id={mp!r}, expected {most}")

    ma = runtime.retrieve("most_polluted_aqi")
    if ma is None:
        return ValidatorResult(False, "most_polluted_aqi not set", variables_not_set=True)
    if not is_finite_number(ma) or not compare_numeric(float(ma), most_aqi, tolerance=2.0):
        return ValidatorResult(False, f"most_polluted_aqi={ma!r}, expected ~{round(most_aqi,0)}")

    return ValidatorResult(True, f"Correct: top5={sorted(top5)}, most polluted station {most} (AQI {round(most_aqi,0)})")


tools = []
variables = [
    Variable("top5_station_ids", None, "List/set of the 5 station_ids with the highest AQI province-wide at 2025-06-11 09:00 (list of int)."),
    Variable("most_polluted_station_id", None, "The single most polluted station_id at that hour (int)."),
    Variable("most_polluted_aqi", None, "AQI of that most-polluted station (float)."),
]
validators = {"validate_hb_3_20": validate_hb_3_20}
