"""Fire-case core analyses. Ignition 2025-11-26 14:52; ~43h burn -> event window 26th 15:00 through 28th 10:00.
Baseline: 14 prior days (Nov 12-25). All read-only."""
import pandas as pd
from sqlalchemy import text
from domains.HK.db import engine

TAI_PO = 13
EVENT_START = '2025-11-26 15:00'
EVENT_END   = '2025-11-28 10:00'
BASE_START  = '2025-11-12 00:00'
BASE_END    = '2025-11-26 00:00'

# ---------- 1. Matched-hour baseline at Tai Po ----------
q = text("""
    SELECT datetime, no2, pm2_5, pm10, aqhi
    FROM hourly_station_air_quality
    WHERE station_id = :sid AND datetime >= :a AND datetime <= :b
    ORDER BY datetime""")
base = pd.read_sql(q, engine, params={'sid': TAI_PO, 'a': BASE_START, 'b': BASE_END})
ev   = pd.read_sql(q, engine, params={'sid': TAI_PO, 'a': '2025-11-26 00:00', 'b': EVENT_END})
base['hour'] = pd.to_datetime(base['datetime']).dt.hour
ev['dt'] = pd.to_datetime(ev['datetime'])

print('=== 1a. Tai Po NO2: historical distribution at 20:00 (Nov 12-25) vs fire-day value ===')
h20 = base[base['hour'] == 20]['no2'].dropna()
fire20 = ev[(ev['dt'].dt.day == 26) & (ev['dt'].dt.hour == 20)]['no2'].iloc[0]
print(f'historical 20:00 NO2 (n={len(h20)}): mean={h20.mean():.1f} median={h20.median():.1f} '
      f'max={h20.max():.1f} p95={h20.quantile(.95):.1f} std={h20.std():.1f}')
print(f'fire-day 20:00 NO2 = {fire20:.1f}  -> z={(fire20-h20.mean())/h20.std():.2f} sd; '
      f'exceeds historical max by {fire20-h20.max():+.1f}')

print('\n=== 1b. same for PM2.5 and PM10 at 20:00 ===')
for c in ['pm2_5', 'pm10']:
    h = base[base['hour'] == 20][c].dropna()
    f = ev[(ev['dt'].dt.day == 26) & (ev['dt'].dt.hour == 20)][c].iloc[0]
    print(f'{c:6}: hist mean={h.mean():.1f} max={h.max():.1f} | fire-day={f:.1f} (z={(f-h.mean())/h.std():+.2f})')

print('\n=== 1c. peak-vs-matched-peak (the fair version of the paper claim) ===')
daily_peaks = base.assign(d=pd.to_datetime(base['datetime']).dt.date).groupby('d')['no2'].max()
print(f'historical DAILY NO2 PEAKS at Tai Po (14 days): mean={daily_peaks.mean():.1f} '
      f'max={daily_peaks.max():.1f} p95={daily_peaks.quantile(.95):.1f}')
ev26 = ev[ev['dt'].dt.day == 26]
print(f'fire-day (26th) daily peak = {ev26["no2"].max():.1f} at '
      f'{ev26.loc[ev26["no2"].idxmax(), "datetime"]}')

# ---------- 2. Event-aligned hourly series (26th) vs same-hour historical median ----------
print('\n=== 2. Nov 26 hourly NO2 vs same-hour median of prior 14 days (deviation aligned to 14:52 ignition) ===')
med = base.groupby('hour')['no2'].median()
p95h = base.groupby('hour')['no2'].quantile(.95)
rows = []
for _, r in ev26.iterrows():
    h = r['dt'].hour
    rows.append((r['dt'].strftime('%H:%M'), r['no2'], med[h], r['no2']-med[h], '*' if r['no2'] > p95h[h] else ''))
print(f'{"hour":>6} {"NO2":>7} {"histMed":>8} {"dev":>7}  >p95?')
for t, v, m, dv, star in rows:
    print(f'{t:>6} {v:>7.1f} {m:>8.1f} {dv:>+7.1f}  {star}')

# ---------- 3. Network contrast: Tai Po vs all other stations, event evening ----------
print('\n=== 3. DiD-style network contrast: evening rise (18:00-23:00 Nov 26) vs same hours prior 14 days ===')
q3 = text("""
    WITH ev AS (
      SELECT station_id, AVG(no2) evno2 FROM hourly_station_air_quality
      WHERE datetime >= '2025-11-26 18:00' AND datetime <= '2025-11-26 23:00'
      GROUP BY station_id),
    hist AS (
      SELECT station_id, AVG(no2) hno2 FROM hourly_station_air_quality
      WHERE datetime >= :a AND datetime < :b
        AND EXTRACT(hour FROM datetime) BETWEEN 18 AND 23
      GROUP BY station_id)
    SELECT s.id, s.name_en, ev.evno2, hist.hno2, ev.evno2 - hist.hno2 AS rise
    FROM air_quality_station s JOIN ev ON ev.station_id = s.id JOIN hist ON hist.station_id = s.id
    ORDER BY rise DESC""")
net = pd.read_sql(q3, engine, params={'a': BASE_START, 'b': BASE_END})
print(net.to_string(index=False))
tp = net[net['id'] == TAI_PO]['rise'].iloc[0]
others = net[net['id'] != TAI_PO]['rise']
print(f'\nTai Po rise = {tp:+.1f}; other 17 stations: mean {others.mean():+.1f}, max {others.max():+.1f}')
print(f'-> Tai Po-specific excess over network mean = {tp - others.mean():+.1f} ug/m3')

# ---------- 4. Wind during the event (verify westerly / plume direction) ----------
print('\n=== 4. wind near Tai Po during event evening ===')
try:
    w = pd.read_sql(text("""
        SELECT ws.name_en, h.datetime, h.wind_direction, h.wind_speed
        FROM hourly_weather h JOIN weather_station ws ON ws.id = h.station_id
        WHERE h.datetime >= '2025-11-26 14:00' AND h.datetime <= '2025-11-27 00:00'
          AND ST_DWithin(ws.coordinate, ST_GeogFromText('POINT(114.1655 22.4509)'), 10000)
        ORDER BY h.datetime"""), engine)
    print(w.to_string(index=False) if len(w) else '(no wind rows within 10 km)')
except Exception as e:
    print('wind query failed:', str(e)[:200])
