"""Fire-case groundwork (R1-5): matched-hour baseline, event-aligned series, directional contrast.
Read-only queries. Fire: Wang Fuk Court, Tai Po, ignition 2025-11-26 14:52 HKT."""
import pandas as pd
from sqlalchemy import text
from domains.HK.db import engine

# ------- 0. Locate Tai Po station (paper: station 13, ~1.2 km from fire) -------
st = pd.read_sql(text("""
    SELECT id, name_en, ST_Y(coordinate::geometry) lat, ST_X(coordinate::geometry) lon, station_type
    FROM air_quality_station ORDER BY id"""), engine)
print("=== stations ===")
print(st.to_string(index=False))

# Wang Fuk Court approx coordinates (Tai Po): 22.4509 N, 114.1655 E
FIRE_LAT, FIRE_LON = 22.4509, 114.1655
d = pd.read_sql(text(f"""
    SELECT id, name_en,
           ST_Distance(coordinate, ST_GeogFromText('POINT({FIRE_LON} {FIRE_LAT})'))/1000.0 AS dist_km,
           degrees(ST_Azimuth(ST_GeogFromText('POINT({FIRE_LON} {FIRE_LAT})'), coordinate)) AS bearing_from_fire
    FROM air_quality_station ORDER BY dist_km"""), engine)
print("\n=== distance/bearing from fire site ===")
print(d.to_string(index=False))
