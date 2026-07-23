"""Fire follow-ups: wind verification + PM network contrast (fire-signature pollutant)."""
import pandas as pd
from sqlalchemy import text
from domains.HK.db import engine

print('=== 4. wind near Tai Po, 26 Nov 14:00 - 27 Nov 00:00 ===')
w = pd.read_sql(text("""
    SELECT ws.name_en, h.datetime, h.wind_direction, h.wind_degree, h.wind_speed
    FROM hourly_station_weather h JOIN weather_station ws ON ws.id = h.station_id
    WHERE h.datetime >= '2025-11-26 14:00' AND h.datetime <= '2025-11-27 00:00'
      AND ST_DWithin(ws.coordinate, ST_GeogFromText('POINT(114.1655 22.4509)'), 12000)
    ORDER BY h.datetime, ws.name_en"""), engine)
print(w.to_string(index=False) if len(w) else '(none within 12 km)')

print('\n=== 5. PM10 / PM2.5 network contrast, evening 18:00-23:00 Nov 26 vs prior 14 days ===')
for col in ['pm10', 'pm2_5']:
    net = pd.read_sql(text(f"""
        WITH ev AS (
          SELECT station_id, AVG({col}) e FROM hourly_station_air_quality
          WHERE datetime >= '2025-11-26 18:00' AND datetime <= '2025-11-26 23:00' GROUP BY station_id),
        hist AS (
          SELECT station_id, AVG({col}) h FROM hourly_station_air_quality
          WHERE datetime >= '2025-11-12' AND datetime < '2025-11-26'
            AND EXTRACT(hour FROM datetime) BETWEEN 18 AND 23 GROUP BY station_id)
        SELECT s.id, s.name_en, ev.e, hist.h, ev.e - hist.h AS rise
        FROM air_quality_station s JOIN ev ON ev.station_id=s.id JOIN hist ON hist.station_id=s.id
        ORDER BY rise DESC"""), engine)
    tp = net[net['id'] == 13]['rise'].iloc[0]
    others = net[net['id'] != 13]['rise']
    print(f'{col:6}: Tai Po rise {tp:+.1f} | network mean {others.mean():+.1f} max {others.max():+.1f} '
          f'({net.iloc[0]["name_en"]}) | Tai Po rank = {(net["rise"]>=tp).sum()}/18 '
          f'| Tai Po excess over mean = {tp-others.mean():+.1f}')

print('\n=== 6. was Nov-26 already elevated BEFORE ignition (regional episode check) ===')
q = text("""
    SELECT AVG(no2) FROM hourly_station_air_quality
    WHERE station_id != 13 AND datetime >= :a AND datetime <= :b""")
pre_ev  = pd.read_sql(q, engine, params={'a': '2025-11-26 08:00', 'b': '2025-11-26 14:00'}).iloc[0,0]
pre_hist = pd.read_sql(text("""
    SELECT AVG(no2) FROM hourly_station_air_quality
    WHERE station_id != 13 AND datetime >= '2025-11-12' AND datetime < '2025-11-26'
      AND EXTRACT(hour FROM datetime) BETWEEN 8 AND 14"""), engine).iloc[0,0]
print(f'network (excl Tai Po) NO2 08:00-14:00 on Nov 26 (PRE-ignition): {pre_ev:.1f} '
      f'vs 14-day same-hours mean {pre_hist:.1f} -> {pre_ev-pre_hist:+.1f}')

print('\n=== 7. Tai Po AQHI during event window (did official index flag it?) ===')
a = pd.read_sql(text("""
    SELECT datetime, aqhi, aqhi_level FROM hourly_station_air_quality
    WHERE station_id = 13 AND datetime >= '2025-11-26 12:00' AND datetime <= '2025-11-27 12:00'
    ORDER BY datetime"""), engine)
print(a.to_string(index=False))
