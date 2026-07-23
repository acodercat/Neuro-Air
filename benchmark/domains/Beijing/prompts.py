# Domain-specific prompt content: schema, knowledge base, and examples.

from domains.Beijing.stations import (
    URBAN_STATIONS,
    SUBURBAN_STATIONS,
    WESTERN_URBAN_STATIONS,
)

DATASET_SCHEMA = """
<dataset_schema>
The dataset is a pandas DataFrame named `df` containing hourly air quality and meteorological observations
from 12 monitoring stations in Beijing, China. Time range: March 2013 to February 2017 (4 years).

Columns:
  No        int     — Row index number
  year      int     — Year (2013-2017)
  month     int     — Month (1-12)
  day       int     — Day of month (1-31)
  hour      int     — Hour of day (0-23)
  PM2.5     float   — PM2.5 concentration (ug/m3)
  PM10      float   — PM10 concentration (ug/m3)
  SO2       float   — SO2 concentration (ug/m3)
  NO2       float   — NO2 concentration (ug/m3)
  CO        float   — CO concentration (ug/m3)
  O3        float   — O3 concentration (ug/m3)
  TEMP      float   — Temperature (Celsius)
  PRES      float   — Atmospheric pressure (hPa)
  DEWP      float   — Dew point temperature (Celsius)
  RAIN      float   — Precipitation (mm)
  wd        str     — Wind direction (16-point compass: N, NNE, NE, ENE, E, ESE, SE, SSE, S, SSW, SW, WSW, W, WNW, NW, NNW)
  WSPM      float   — Wind speed (m/s)

  station   str     — Station name
  station_code str   — Station code (e.g. '1001A')
  longitude float    — Station longitude (°E)
  latitude  float    — Station latitude (°N)

Two auxiliary DataFrames are also pre-registered in the runtime:

`pop_df` — pandas DataFrame (~7MB) of Beijing population at 100 m grid resolution.
  Columns:
    longitude  float — Grid cell centre longitude (°E)
    latitude   float — Grid cell centre latitude (°N)
    population float — People per 100×100 m cell
  Use haversine distance for spatial queries; ~89k rows covering the Beijing area.

`poi_df` — pandas DataFrame (~720KB) of Beijing points of interest from OpenStreetMap.
  Columns:
    name  str — POI name
    lon   float — Longitude (°E)
    lat   float — Latitude (°N)
    type  str — POI type; one of: school, residential, park, industrial,
                kindergarten, hospital, university, pharmacy, community_centre,
                playground, clinic, social_facility
</dataset_schema>
"""

KNOWLEDGE_BASE = f"""
<knowledge_base>
Beijing Air Quality Monitoring Network:
- 12 national air quality monitoring stations across Beijing
- Data period: March 2013 to February 2017
- Station classification by location type:
  - Urban core ({len(URBAN_STATIONS)}): {", ".join(URBAN_STATIONS)}
  - Suburban/rural ({len(SUBURBAN_STATIONS)}): {", ".join(SUBURBAN_STATIONS)}
  - Western urban ({len(WESTERN_URBAN_STATIONS)}): {", ".join(WESTERN_URBAN_STATIONS)}
</knowledge_base>
"""

EXAMPLES = """
<examples>
Example 1 - Filter and aggregate:
```python
# Monthly average PM2.5 across all stations
monthly_pm25 = df.groupby('month')['PM2.5'].mean()
print(monthly_pm25.round(1))
```

Example 2 - Station comparison:
```python
# Compare urban vs suburban PM2.5
urban = ['Dongsi', 'Guanyuan', 'Wanshouxigong', 'Tiantan', 'Nongzhanguan', 'Aotizhongxin']
suburban = ['Changping', 'Dingling', 'Huairou', 'Shunyi']
urban_avg = df[df['station'].isin(urban)]['PM2.5'].mean()
suburban_avg = df[df['station'].isin(suburban)]['PM2.5'].mean()
print(f"Urban: {{urban_avg:.1f}}, Suburban: {{suburban_avg:.1f}}")
```

Example 3 - Time series with datetime:
```python
df['datetime'] = pd.to_datetime(df[['year','month','day','hour']])
daily = df.groupby([df['datetime'].dt.date, 'station'])['PM2.5'].mean().reset_index()
daily.columns = ['date', 'station', 'daily_pm25']
print(daily.head(10))
```
</examples>
"""
