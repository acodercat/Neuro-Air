import pandas as pd
from cave_agent import Variable

from config import PROJECT_ROOT
from core.system_instructions import COMMON_INSTRUCTIONS
from domains.HB.db import engine
from domains.HB.prompts import DATABASE_SCHEMA, KNOWLEDGE_BASE, EXAMPLES

SYSTEM_INSTRUCTIONS = COMMON_INSTRUCTIONS + """
- Use the Python environment to perform database operations and data analysis.
- Write Python code to query the database and perform necessary data analysis if needed.
- Perform statistical analysis directly in the database using SQL aggregations (COUNT, AVG, SUM, GROUP BY) rather than returning raw data, to minimize data transfer and improve efficiency.
- LARGE TABLE WARNING:
    - MANDATORY: Before querying large tables:
      a) First run COUNT(*) with your WHERE conditions to check result size
      b) Always use LIMIT 10 for exploratory queries
      c) Use aggregations (AVG, COUNT, GROUP BY) instead of retrieving raw data
- The database supports PostGIS spatial functions for geographic coordinate columns.
- When you need to search the internet or look up location data, wait for the actual search results before proceeding with any analysis.
- Units for emissions: nh3, nox, so2, pm, hc, nmhc, co, hcl are in kg and exhaust_gas is in cubic meters.
- The primary_pollutants field is a PostgreSQL jsonb field that stores the primary pollutants. For example: ["PM10", "PM2_5"].
- Your analysis and recommendations are for environmental officials, not the general public. Be professional and scientific. Do NOT propose public-facing suggestions like "reduce outdoor activities" or "wear masks". Focus on regulatory measures, emission controls, monitoring strategies, and policy recommendations.
- Population data (100m grid) is available as `pop_df` with columns: longitude, latitude, population. Use haversine distance for spatial queries with population data.
- Always respond in Chinese.
"""

SYSTEM_PROMPT = SYSTEM_INSTRUCTIONS + DATABASE_SCHEMA + KNOWLEDGE_BASE + EXAMPLES

EXTRA_FUNCTIONS = []


ENGINE_DESCRIPTION = """
It's a SQLAlchemy engine for the postgres database with PostGIS.
If you need to query the database, you can use this SQLAlchemy engine. use text() to wrap the query.

Example 1:
timestamp = '2025-01-01 00:00:00'
query = text(f\"\"\"
SELECT hsaq.aqi, hsaq.timestamp, hsaq.pm2_5, hsaq.pm10, hsaq.o3, hsaq.so2, hsaq.no2, hsaq.co
FROM hourly_station_air_quality hsaq
JOIN air_quality_station aqs ON hsaq.station_id = aqs.id
WHERE timestamp = '{timestamp}'
limit 10
\"\"\")
df = pd.read_sql(query, engine)
print(df)

Example 2:
query = text("SELECT * FROM hourly_station_air_quality where timestamp = '2025-01-01 00:00:00'")
df = pd.read_sql(query, engine)
print(df)
"""


# Population grid is not used by the Neuro-Air evaluation (validators recompute
# ground truth from the database); the large grid file is therefore not shipped.
# Load it if present, otherwise expose an empty frame so the package still imports.
_pop_path = PROJECT_ROOT / "datasets" / "HB_population_100m.csv"
_pop_df = pd.read_csv(_pop_path) if _pop_path.exists() else pd.DataFrame(columns=["longitude", "latitude", "population"])

BASE_VARIABLES = [
    Variable("engine", engine, ENGINE_DESCRIPTION),
    Variable("pop_df", _pop_df, "pandas DataFrame (~256MB) containing Hebei population data at 100m grid resolution. Columns: longitude, latitude, population. Each row represents a 100m×100m grid cell with population count (2020 census). Use haversine distance for spatial queries."),
]
