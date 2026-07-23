"""Neuro-Air HK 1-9 (verbatim) — station-specific PM2.5 peak timing across all stations.

Original query identifies PM2.5 peak timing across all 18 monitoring stations on
2025-06-10 and the station-specific peak hours. The validator recomputes, per station,
the hour-of-day of that station's maximum PM2.5 (every station's peak is unique on this
day), the most-polluted station (highest PM2.5), and the station count. The agent must
provide station_peak_hours as a dict {station_id: hour}. GT recomputed from the DB.
"""
import pandas as pd
from sqlalchemy import text

from cave_agent.runtime import IPythonRuntime, Variable
from domains.HK.db import engine
from core.types import Turn
from core.validation import ValidatorResult, is_finite_number

DAY_START = "2025-06-10 00:00:00"
DAY_END = "2025-06-11 00:00:00"


def _station_peak_hours():
    """Per station, the SET of hour-of-day values at which it hits its max PM2.5.

    On a tie a station's daily max is shared by several hours; each is a legitimate
    "peak hour", so every station maps to a set and the agent may report any member.
    """
    df = pd.read_sql(
        text(
            f"SELECT station_id, EXTRACT(HOUR FROM datetime) AS hod FROM hourly_station_air_quality h "
            f"WHERE datetime >= '{DAY_START}' AND datetime < '{DAY_END}' "
            f"AND pm2_5 = (SELECT MAX(pm2_5) FROM hourly_station_air_quality "
            f"WHERE station_id = h.station_id AND datetime >= '{DAY_START}' AND datetime < '{DAY_END}')"
        ),
        engine,
    )
    out = {}
    for _, r in df.iterrows():
        out.setdefault(int(r["station_id"]), set()).add(int(r["hod"]))
    return out


def validate_hk_1_9(response: str, runtime: IPythonRuntime, turn: Turn) -> ValidatorResult:
    peaks = _station_peak_hours()
    # Accept ANY station achieving the global max PM2.5 (ties are legitimate).
    most_polluted = {
        int(s) for s in pd.read_sql(
            text(
                f"SELECT station_id FROM hourly_station_air_quality "
                f"WHERE datetime >= '{DAY_START}' AND datetime < '{DAY_END}' "
                f"AND pm2_5 = (SELECT MAX(pm2_5) FROM hourly_station_air_quality "
                f"WHERE datetime >= '{DAY_START}' AND datetime < '{DAY_END}')"
            ),
            engine,
        )["station_id"]
    }

    sph = runtime.retrieve("station_peak_hours")
    if sph is None:
        return ValidatorResult(False, "station_peak_hours not set", variables_not_set=True)
    if not isinstance(sph, dict):
        return ValidatorResult(False, f"station_peak_hours must be a dict, got {type(sph).__name__}")
    try:
        got = {int(k): int(v) for k, v in sph.items()}
    except (TypeError, ValueError):
        return ValidatorResult(False, f"station_peak_hours has non-integer keys/values: {sph!r}")
    wrong = [s for s, hset in peaks.items() if got.get(s) not in hset]
    if wrong:
        return ValidatorResult(False, f"station_peak_hours wrong/missing for stations {wrong[:6]} (expected e.g. one of {sorted(peaks[wrong[0]])} for {wrong[0]})")

    mp = runtime.retrieve("most_polluted_station_id")
    if mp is None:
        return ValidatorResult(False, "most_polluted_station_id not set", variables_not_set=True)
    if not is_finite_number(mp) or int(mp) not in most_polluted:
        return ValidatorResult(False, f"most_polluted_station_id={mp!r}, expected one of {sorted(most_polluted)}")

    ns = runtime.retrieve("n_stations")
    if ns is None:
        return ValidatorResult(False, "n_stations not set", variables_not_set=True)
    if not is_finite_number(ns) or int(ns) != len(peaks):
        return ValidatorResult(False, f"n_stations={ns!r}, expected {len(peaks)}")

    return ValidatorResult(True, f"Correct: {len(peaks)} station peak hours matched, most polluted = station {int(mp)}")


tools = []
variables = [
    Variable("station_peak_hours", None, "Dict {station number: hour_of_day 0-23} of each station's PM2.5 peak on 2025-06-10 (dict)."),
    Variable("most_polluted_station_id", None, "station number with the highest PM2.5 that day (int)."),
    Variable("n_stations", None, "Number of stations with PM2.5 data that day (int)."),
]
validators = {"validate_hk_1_9": validate_hk_1_9}
