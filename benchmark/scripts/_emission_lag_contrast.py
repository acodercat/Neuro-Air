"""Lag-consistency reanalysis for the Handan industrial CO case (company 2564, station 1014).

Reproduces the published contemporaneous (zero-lag) high/low emission contrast and
recomputes it under the 3-hour lag identified by the correlation scan, addressing the
alignment inconsistency flagged in the manuscript. Window: 2026-01-06 00:00 to
2026-01-08 23:00 (72 h). Verified reproduction of published values before extension:
r(0)=0.773, r(3)=0.833 (argmax over lags 0-6), thresholds 14,288/11,858 kg/h,
hi/lo CO 0.775/0.337 mg/m3 (+130%), dAQI +16.1; 18 of 19 geometric 20-km stations
carry CO data in the window.

Results (2026-07-21):
  lag=0: dCO=+0.438 (+130%), dAQI=+16.1, n=72
  lag=3, original thresholds: dCO=+0.462 (+139%), dAQI=+18.0, n=69 (hi 21 / lo 24)
  lag=3, thresholds recomputed on lag-aligned pairs (14,123/11,743): dCO=+0.443
         (+134%), dAQI=+16.9 (hi 23 / lo 23)
  Moving-block bootstrap (12-h blocks, B=10,000, seed 20260721), thresholds
  re-estimated per replicate; 95% CI for dCO: lag0 [+0.199,+0.587], lag3 [+0.235,+0.573].
  Block-length sensitivity (same seed): lag0 L=6h [+0.231,+0.584], L=24h [+0.171,+0.542];
  lag3 L=6h [+0.265,+0.583], L=24h [+0.211,+0.542] -- all exclude zero.
  Multiplicity: BH over the full search space (18 data-bearing stations x lags 0-6,
  126 combos, n>=30 pairs each): Guxin lag-3 survives at q=0.01 (p=7.3e-19); 48 combos
  across 9 stations also pass the paper's r>0.5 & p<0.01 screening rule (spatially
  diffuse correlation field, consistent with the regional-confounding caveat).
"""

import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy import text

from domains.HB.db import engine

COMPANY_ID = 2564
STATION_ID = 1014  # She County Guxin Town, 12.199 km, bearing 178 deg
WIN = ("2026-01-06", "2026-01-09")
SEED, B, BLOCK = 20260721, 10_000, 12


def load():
    with engine.connect() as c:
        em = pd.read_sql(text(
            "SELECT timestamp, co AS e_co FROM hourly_polluting_company_emission "
            f"WHERE company_id={COMPANY_ID} AND timestamp>='{WIN[0]}' AND timestamp<'{WIN[1]}' "
            "ORDER BY timestamp"), c)
        aq = pd.read_sql(text(
            "SELECT timestamp, co AS c_co, aqi FROM hourly_station_air_quality "
            f"WHERE station_id={STATION_ID} AND timestamp>='{WIN[0]}' AND timestamp<'{WIN[1]}' "
            "ORDER BY timestamp"), c)
    return em, aq


def aligned(em, aq, lag):
    d = em.copy()
    d["timestamp"] += pd.Timedelta(hours=lag)
    return d.merge(aq, on="timestamp").dropna(subset=["e_co", "c_co"]).reset_index(drop=True)


def contrast(m, th_hi, th_lo):
    hi, lo = m[m.e_co >= th_hi], m[m.e_co <= th_lo]
    return hi.c_co.mean() - lo.c_co.mean(), hi.aqi.mean() - lo.aqi.mean(), len(hi), len(lo)


def block_boot(m):
    rng = np.random.default_rng(SEED)
    n, diffs = len(m), []
    for _ in range(B):
        starts = rng.integers(0, n, int(np.ceil(n / BLOCK)))
        idx = np.concatenate([np.arange(s, s + BLOCK) % n for s in starts])[:n]
        b = m.iloc[idx]
        th_h, th_l = np.percentile(b.e_co, 67), np.percentile(b.e_co, 33)
        hi, lo = b[b.e_co >= th_h], b[b.e_co <= th_l]
        if len(hi) > 2 and len(lo) > 2:
            diffs.append(hi.c_co.mean() - lo.c_co.mean())
    return np.percentile(diffs, [2.5, 97.5])


def main():
    em, aq = load()
    for lag in range(7):
        m = aligned(em, aq, lag)
        r, p = stats.pearsonr(m.e_co, m.c_co)
        print(f"lag={lag}h r={r:+.3f} p={p:.2e} n={len(m)}")
    th0 = (np.percentile(em.e_co, 67), np.percentile(em.e_co, 33))
    for lag in (0, 3):
        m = aligned(em, aq, lag)
        for label, th in (("orig", th0),
                          ("recomp", (np.percentile(m.e_co, 67), np.percentile(m.e_co, 33)))):
            dC, dA, nh, nl = contrast(m, *th)
            print(f"lag={lag} {label} th=({th[0]:,.0f}/{th[1]:,.0f}) "
                  f"dCO={dC:+.3f} dAQI={dA:+.1f} (hi {nh}/lo {nl})")
        lo95, hi95 = block_boot(m)
        print(f"lag={lag} block-bootstrap 95% CI dCO: [{lo95:+.3f}, {hi95:+.3f}]")


if __name__ == "__main__":
    main()
