# Domain-specific prompt content: schema, knowledge base, and examples.

DATABASE_SCHEMA = """
<database_schema>
This is the database schema of the air quality monitoring data in Hong Kong:
--This table stores information about air quality monitoring stations.It has columns for station details like name (in English and Traditional Chinese), address, geographic coordinates, altitude, station type, creation timestamp, and area type:
create type air_quality_station_type_enum as enum ('GENERAL', 'ROADSIDE');
create type air_quality_station_area_type_enum as enum ('URBAN', 'RURAL', 'NEW_TOWN');
--This table stores hourly air quality measurements from the monitoring stations.It includes columns for various air quality metrics like AQHI (Air Quality Health Index), PM2.5, PM10, O3, SO2, NO2, CO, and their corresponding "AR" (Added Health Risk) values. All concentrations are in microgram per cubic metre (µg/m3):
create table air_quality_station( id serial primary key, name_en varchar(200), address_en varchar(500), coordinate geography(Point, 4326), altitude double precision, station_type air_quality_station_type_enum, created_at timestamp default now(), area_type air_quality_station_area_type_enum);
create type pm_ar_source_enum as enum ('PM10', 'PM2_5');
--This air_quality_health_index_level(aqhi_level) maps AQHI into 5 risk levels: LOW (1-3), MODERATE (4-6), HIGH (7), VERY HIGH (8-10), and SERIOUS (>10).
create type air_quality_health_index_level_enum as enum ('LOW', 'MODERATE', 'HIGH', 'VERY HIGH', 'SERIOUS');
create table hourly_station_air_quality( id serial primary key, station_id integer references air_quality_station, aqhi integer, pm2_5 double precision, pm10 double precision, o3 double precision, so2 double precision, no2 double precision, co double precision, no2_ar double precision, o3_ar double precision, pm_ar double precision, so2_ar double precision, pm_ar_source pm_ar_source_enum, datetime timestamp, aqhi_level air_quality_health_index_level_enum, unique (station_id, datetime));
--This table stores information about streets:
create type street_type as enum ('secondary', 'primary', 'highway', 'track', 'tunnel', 'unknown', 'restricted');
create table street( id serial primary key, street_type street_type, name_en varchar(100), street_code varchar(20) unique, created_at timestamp default now());
--This table stores information about road segments:
create table road_segment( id serial primary key, street_id integer references street, road_segment_code varchar(20) unique, length smallint, road_level smallint, direction road_segment_direction, geometry geometry(MultiLineString, 4326), free_flow_speed real, created_at timestamp default now());
--This table stores hourly traffic data for road segments with speed, congestion status( 0: smooth flow, 1: slight congestion, 2: moderate congestion, 3: heavy congestion) and congestion index( ≤1.0: smooth, 1.0-1.5: slight, 1.5-2.0: moderate, >2.0: heavy):
create table hourly_road_segment_traffic( id serial primary key, road_segment_id integer references road_segment, speed real, congestion_status smallint, congestion_index real, datetime timestamp, unique (road_segment_id, datetime));
--This table stores information about weather monitoring stations:
create type weather_station_type_enum as enum ('MANNED_WEATHER_STATION', 'AUTOMATIC_WEATHER_STATION');
create table weather_station( id serial primary key, name_en varchar(200), station_code varchar(50) unique, address_en varchar(500), coordinate geography(Point, 4326), altitude double precision, station_type weather_station_type_enum, created_at timestamp default now());
--This table stores hourly weather measurements from the weather stations:
create type wind_direction_enum as enum ('N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW');
create table hourly_station_weather( id serial primary key, station_id integer references weather_station, temperature double precision, visibility double precision, pressure double precision, humidity double precision, wind_degree double precision, wind_speed double precision, wind_gust double precision, wind_direction wind_direction_enum, datetime timestamp, unique (station_id, datetime));
--This table stores information about geographic features from OpenStreetMap in Hong Kong. It contains huge amount of data, so you need to be careful when querying this table:
CREATE TYPE geometry_type_enum AS ENUM('LINESTRING', 'POLYGON', 'POINT', 'MULTIPOLYGON');
CREATE TYPE osm_feature_main_type_enum AS ENUM( 'BUILDING', 'TRANSPORT', 'ROAD', 'NATURAL', 'COMMERCIAL', 'PUBLIC', 'RELIGIOUS', 'LEISURE', 'PLACE', 'INDUSTRIAL', 'HISTORIC', 'AGRICULTURAL', 'CEMETERY', 'WATER', 'SERVICE', 'ACCOMMODATION', 'GENERAL');
CREATE TABLE osm_feature( id SERIAL PRIMARY KEY, name VARCHAR(255), sub_type VARCHAR(100), geometry GEOMETRY(Geometry, 4326), geometry_type geometry_type_enum, main_type osm_feature_main_type_enum);
--This table stores information about EIA habitat and EIA project:
create type district_enum as enum('Islands', 'Kwai Tsing', 'North', 'Sai Kung', 'Sha Tin', 'Tai Po', 'Tsuen Wan', 'Tuen Mun', 'Kowloon City', 'Kwun Tong', 'Sham Shui Po', 'Wong Tai Sin', 'Yau Tsim Mong', 'Central and Western', 'Eastern', 'Southern', 'Wan Chai', 'Yuen Long');
create type eia_habitat_type_enum as enum('AGRICULTURAL_LAND', 'DEVELOPED_AREA', 'GRASSLAND', 'GRASSLAND_SHRUBLAND', 'MARSH', 'PLANTATION', 'POND', 'SEASONAL_WATERCOURSE', 'SHRUBLAND', 'SPECIAL_SCIENTIFIC_SITE', 'UPLAND_GRASSLAND', 'VILLAGE_AREA', 'WASTELAND', 'WATERCOURSE', 'WETLAND', 'WOODLAND');
create table eia_habitat( id serial primary key, geometry geometry(Geometry, 4326), district district_enum, eia_project_id integer references eia_project, area double precision, habitat_type eia_habitat_type_enum);
create type eia_application_status_enum as enum('APPROVED_UNCONDITIONAL', 'APPROVED_CONDITIONAL', 'PROCESSING', 'QUASHED_FROM_CONDITIONAL');
create table eia_project( id serial primary key, name varchar(300), eid varchar(10) unique, application_number varchar(100), register_number varchar(100), applicant varchar(200), project_website varchar(300), application_status eia_application_status_enum, coordinate geography(Point, 4326), year smallint);
create table traffic_camera(code varchar(20) unique, description varchar(500), district district_enum, coordinate geography(Point, 4326), created_at timestamp default now());

--Geographic and Planning Data Tables:
-- Sensitive Areas: Protected or regulated zones in Hong Kong requiring special consideration in planning
create type sensitive_area_category_enum AS enum('CONSERVATION_AREA', 'COASTAL_PROTECTION_AREA', 'SSSI', 'COUNTRY_PARK', 'MARINE_PARK', 'DECLARED_MONUMENT', 'FISH_CULTURE_ZONE', 'BATHING_BEACH', 'EDUCATIONAL_INSTITUTION', 'HEALTH_CARE_INSTITUTION', 'PLACE_OF_WORSHIP', 'RESIDENTIAL_AREA'); 
create table sensitive_area( id serial primary key, category sensitive_area_category_enum NOT null, name varchar(255), area integer -- square meter, geometry geometry(Geometry, 4326) NOT null, geometry_type geometry_type_enum NOT NULL);

-- Land Use Zones: Statutory planning zones defining permitted land uses
-- Each zone specifies what types of development are allowed in that area
create type land_category AS enum( 'Agriculture', 'Coastal Protection', 'Commercial', 'Mixed Use', 'CDA', -- Comprehensive Development Area 'Conservation', 'Country Park', 'Drainage', 'GIC', -- Government, Institution OR Community 'Green Belt', 'Industrial', 'Inlet', 'LDC Dev Scheme', -- Land Development Corporation Development Scheme 'Major Road', 'Marine Basin', 'Nullah', 'Open Space', 'Open Storage', 'Other Specified Uses', 'Pedestrian Precinct', 'Pedestrian Street', 'Railway', 'Recreation', 'Recreation Priority', 'Residential', 'River', 'Sea', 'SSSI', -- Site of Special Scientific Interest 'Typhoon Shelter', 'Undetermined', 'URA Dev Scheme', -- Urban Renewal Authority Development Scheme 'Vessel Anchorage', 'Village', 'WKCD' -- West Kowloon Cultural District);
create table land_use_zone( id serial primary key, zone_label varchar(50) NOT null, land_category land_category NOT null, specified_use varchar(255), description varchar(255), geometry geometry(MultiPolygon, 4326) NOT null, area integer -- square meter);

-- Building Height Controls: Maximum building height restrictions for different zones
create type building_height_control_type AS enum( 'BHCB', -- Building Height Control IN metres(above principal datum) 'BHCS', -- Building Height Control IN Storeys 'BHCN', -- Building Height Control specified IN Notes 'NBA' -- Non-Building Area(no structures permitted));
create table building_height_control( id serial primary key, control_type building_height_control_type NOT null, height_value smallint, geometry geometry(MultiPolygon, 4326) NOT null, area integer -- square meter);

-- Auxiliary pandas DataFrame `pop_df` (~33KB) is pre-registered in the runtime.
-- Columns: longitude (float, °E), latitude (float, °N), population (float, people per ~1 km² cell, WorldPop 2020).
-- Use haversine distance for spatial queries against station coordinates.
</database_schema>
"""

KNOWLEDGE_BASE = """
<knowledge_base>
<air_quality_station_list>
There are 18 air quality monitoring stations in Hong Kong:
station_id,name_en
5,Tuen Mun
12,Sham Shui Po
15,Central/Western
2,North
1,Southern
17,Causeway Bay
16,Central
3,Kwun Tong
9,Kwai Chung
8,Tap Mun
14,Mong Kok
13,Tai Po
10,Yuen Long
18,Tsuen Wan
11,Sha Tin
6,Tung Chung
4,Tseung Kwan O
7,Eastern
</air_quality_station_list>
</knowledge_base>
"""

EXAMPLES = """
<examples>
Example 1: Temporal Analysis
User: How has the air quality in Central changed over the past week?
Assistant: To analyze the weekly trend, I'll query hourly measurements from Central station, convert them to daily averages, and examine the patterns across key pollutants
```python
import pandas as pd
from sqlalchemy import text
import datetime as dt

# Query data for Central station directly using station_id = 16
query = \"\"\"
SELECT datetime, aqhi, pm2_5, no2
FROM hourly_station_air_quality
WHERE station_id = 16
AND datetime >= NOW() - INTERVAL '7 days'
ORDER BY datetime
\"\"\"
df = pd.read_sql(query, engine)
df['datetime'] = pd.to_datetime(df['datetime'])
df['date'] = df['datetime'].dt.date
daily_avg = df.groupby('date').agg({{'aqhi': 'mean', 'pm2_5': 'mean', 'no2': 'mean'}}).reset_index()
daily_avg = daily_avg.round(0)
print(daily_avg)
```

Example 2: Air Quality Near Specific Address
User: What is the air quality near Hong Kong University?
Assistant: I'll need to find the coordinates of the university, locate the nearest monitoring station, and retrieve recent air quality data
```python
import pandas as pd
from sqlalchemy import text
import numpy as np
from datetime import datetime, timedelta

# Get coordinates for the address
coordinates = search_hk_location("Hong Kong University")

# Parse the coordinates
lat, lng = coordinates['latitude'], coordinates['longitude']

# Find the nearest air quality monitoring station
query = \"\"\"
SELECT id, name_en, ST_Distance(
    coordinate::geography,
    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
) as distance
FROM air_quality_station
ORDER BY distance
LIMIT 1
\"\"\" % (lng, lat)

nearest_station = pd.read_sql(query, engine)
print(f"Nearest monitoring station: {{nearest_station['name_en'].values[0]}}")

# Get recent air quality data for the nearest station
station_id = nearest_station['id'].values[0]
query = \"\"\"
SELECT datetime, aqhi, aqhi_level, pm2_5, no2
FROM hourly_station_air_quality
WHERE station_id = %d
AND datetime >= NOW() - INTERVAL '24 hours'
ORDER BY datetime DESC
LIMIT 24
\"\"\" % station_id

air_quality = pd.read_sql(query, engine)
# Calculate averages
avg_data = air_quality.mean(numeric_only=True).round(0)
print(f"Average AQHI: {{avg_data['aqhi']}}")
print(f"Average PM2.5: {{avg_data['pm2_5']}} μg/m³")
print(f"Average NO2: {{avg_data['no2']}} μg/m³")
```
</examples>
"""
