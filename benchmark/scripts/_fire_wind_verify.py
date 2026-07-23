"""Reproduce the agent's 24h wind aggregation at Tai Po Kau and get the hour-resolved truth."""
import pandas as pd
from sqlalchemy import text
from domains.HK.db import engine

# Agent's window: first 24 h after fire report (2025-11-26 14:51 -> 11-27 14:51)
w = pd.read_sql(text("""
    SELECT h.datetime, h.wind_direction, h.wind_degree, h.wind_speed
    FROM hourly_station_weather h JOIN weather_station ws ON ws.id = h.station_id
    WHERE ws.name_en = 'Tai Po Kau'
      AND h.datetime >= '2025-11-26 15:00' AND h.datetime <= '2025-11-27 15:00'
    ORDER BY h.datetime"""), engine)
print(f'n={len(w)}  avg wind_speed = {w.wind_speed.mean():.2f}')
print('direction mode:', w.wind_direction.mode().tolist())
print('direction counts:', w.wind_direction.value_counts().to_dict())
print('\nhour-resolved (evening 26th + morning 27th):')
print(w.to_string(index=False))
