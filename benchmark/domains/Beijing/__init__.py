import pandas as pd
from cave_agent import Variable

from config import PROJECT_ROOT
from core.system_instructions import COMMON_INSTRUCTIONS
from domains.Beijing.prompts import DATASET_SCHEMA, KNOWLEDGE_BASE, EXAMPLES

SYSTEM_INSTRUCTIONS = COMMON_INSTRUCTIONS + """
- The data is available as a pandas DataFrame named `df` — use pandas operations to analyze it.
- Do NOT use SQL or database queries — there is no database. Use pandas only.
- To create a datetime column: df['datetime'] = pd.to_datetime(df[['year','month','day','hour']])
- POI data (schools, hospitals, parks, etc.) is available as `poi_df` with columns: name, lon, lat, type.
- Population data (100m grid) is available as `pop_df` with columns: longitude, latitude, population.
- For spatial distance calculations, use the haversine formula with coordinates from these DataFrames.
- Must respond in the same language as the user's question.
"""

SYSTEM_PROMPT = SYSTEM_INSTRUCTIONS + DATASET_SCHEMA + KNOWLEDGE_BASE + EXAMPLES

EXTRA_FUNCTIONS = []

# The Beijing domain is not part of the Neuro-Air evaluation (HK and HB only);
# its data files are not shipped. Load if present, else expose empty frames so
# the package still imports.
def _csv_or_empty(name, cols):
    p = PROJECT_ROOT / "datasets" / name
    return pd.read_csv(p) if p.exists() else pd.DataFrame(columns=cols)

_df = _csv_or_empty("Beijing.csv", ["station", "datetime", "longitude", "latitude"])
_poi_df = _csv_or_empty("Beijing_POI.csv", ["name", "type", "longitude", "latitude"])
_pop_df = _csv_or_empty("Beijing_population_100m.csv", ["longitude", "latitude", "population"])

BASE_VARIABLES = [
    Variable("df", _df, "pandas DataFrame containing the Beijing air quality dataset. Columns: year, month, day, hour, PM2.5, PM10, SO2, NO2, CO, O3, TEMP, PRES, DEWP, RAIN, wd, WSPM, station, station_code, longitude, latitude."),
    Variable("poi_df", _poi_df, "pandas DataFrame (~720KB) containing Beijing POI data. Columns: name, lon, lat, type. Types include: school, residential, park, industrial, kindergarten, hospital, university, pharmacy, community_centre, playground, clinic, social_facility."),
    Variable("pop_df", _pop_df, "pandas DataFrame (~7MB) containing Beijing population data at 100m grid resolution. Columns: longitude, latitude, population. Each row represents a 100m×100m grid cell with population count. Use haversine distance for spatial queries."),
]