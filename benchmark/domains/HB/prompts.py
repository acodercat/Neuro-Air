# Domain-specific prompt content: schema, knowledge base, and examples.

DATABASE_SCHEMA = """
<database_schema>
create table district( id serial primary key, name varchar(200), code varchar(50) coordinate geography(Point, 4326), city_id integer references city);
create table city( id serial primary key, name varchar(200), coordinate geography(Point, 4326));
create type air_quality_station_type_enum as enum('NATIONAL', 'PROVINCIAL', 'INDUSTRIAL');
create table air_quality_station( id serial primary key, name varchar(200), coordinate geography(Point, 4326), station_type air_quality_station_type_enum, district_id integer references district, city_id integer references city);
create type air_quality_level_enum as enum ('EXCELLENT', 'GOOD', 'LIGHTLY_POLLUTED', 'MODERATELY_POLLUTED', 'HEAVILY_POLLUTED', 'SEVERELY_POLLUTED');
create table daily_city_air_quality( id serial primary key, city_id integer references city, date date, aqi smallint, air_quality_level air_quality_level_enum, pm2_5 real, pm10 real, so2 real, no2 real, o3_8h real, co real, primary_pollutants jsonb, composite_index real);
create table daily_city_emission( id serial primary key, city_id integer references city, exhaust_gas real, nox real, so2 real, pm real, hc real, nmhc real, co real, hcl real, date date);
create table daily_district_air_quality( id serial primary key, district_id integer references district, date date, aqi smallint, air_quality_level air_quality_level_enum, pm2_5 real, pm10 real, so2 real, no2 real, o3_8h real, co real, primary_pollutants jsonb, composite_index real);
create table daily_district_emission( id serial primary key, district_id integer references district, city_id integer references city, exhaust_gas real, nox real, so2 real, pm real, hc real, nmhc real, co real, hcl real, date date);
create type industry_type_enum as enum('STEEL', 'POWER', 'CEMENT', 'CERAMICS', 'GLASS', 'COKING');
create table polluting_company( id serial primary key, city_id integer references city, district_id integer references district, name varchar(200), address varchar(500), emissions_permit_code varchar(50), industry_type industry_type_enum, coordinate geography(Point, 4326));
create table daily_polluting_company_emission( id serial primary key, company_id integer references polluting_company, exhaust_gas real, nox real, so2 real, pm real, hc real, nmhc real, co real, hcl real, date date);
create table hourly_city_air_quality( id serial primary key, city_id integer references city, timestamp timestamp, aqi smallint, air_quality_level air_quality_level_enum, pm2_5 real, pm10 real, so2 real, no2 real, o3 real, o3_8h real, co real, primary_pollutants jsonb, composite_index real);
create table hourly_city_emission( id serial primary key, city_id integer references city, exhaust_gas real, nox real, so2 real, pm real, hc real, nmhc real, co real, hcl real, timestamp timestamp);
create table hourly_district_air_quality( id serial primary key, district_id integer references district, timestamp timestamp, aqi smallint, air_quality_level air_quality_level_enum, pm2_5 real, pm10 real, so2 real, no2 real, o3 real, o3_8h real, co real, primary_pollutants jsonb, composite_index real);
create table hourly_polluting_company_emission( id serial primary key, company_id integer references polluting_company, exhaust_gas real, nox real, so2 real, pm real, hc real, nmhc real, co real, hcl real, timestamp timestamp);
create table hourly_station_air_quality( id serial primary key, station_id integer references air_quality_station, timestamp timestamp, aqi smallint, air_quality_level air_quality_level_enum, pm2_5 real, pm10 real, o3 real, o3_8h real, so2 real, no2 real, co real, primary_pollutants jsonb, composite_index real);
create table hourly_city_weather( id serial primary key, city_id integer references city, temperature real, wind_direction varchar(10), wind_degree real, wind_scale smallint, humidity real, wind_speed real, timestamp timestamp, unique (timestamp, city_id));
create table daily_city_weather( id serial primary key, city_id integer references city, max_temperature real, min_temperature real, temperature real, humidity real, wind_speed real, wind_degree real, wind_direction varchar(20), wind_scale integer, date date, unique (date, city_id));
create table hourly_district_weather( id serial primary key, district_id integer references district, temperature real, wind_direction varchar(10), wind_degree real, wind_scale smallint, humidity real, wind_speed real, timestamp timestamp, unique (timestamp, district_id));
create table daily_district_weather( id serial primary key, district_id integer references district, max_temperature real, min_temperature real, temperature real, humidity real, wind_speed real, wind_degree real, wind_direction varchar(20), wind_scale integer, date date, unique (date, district_id));
--The osm_feature table stores information about geographic features from OpenStreetMap in Hebei Province. It contains huge amount of data, so you need to be careful when querying this table:
create type osm_feature_main_type_enum as enum ('RESIDENTIAL', 'COMMERCIAL', 'INDUSTRIAL', 'GOVERNMENT', 'EDUCATION', 'HEALTHCARE', 'CULTURAL', 'INFRASTRUCTURE', 'TRANSPORT', 'ROAD', 'NATURAL', 'PUBLIC', 'LEISURE', 'PLACE', 'AGRICULTURAL', 'CEMETERY', 'WATER', 'ACCOMMODATION');
create table osm_feature( id serial primary key, name varchar(255), sub_type varchar(100), geometry geometry(Geometry, 4326), main_type osm_feature_main_type_enum);
create type construction_site_status_enum as enum('UNDER_CONSTRUCTION', 'CONSTRUCTION_SUSPENDED', 'LONG_TERM_SUSPENSION', 'COMPLETED');
create table construction_site( id serial primary key, name varchar(200), construction_code varchar(32) unique, address varchar(500), coordinate geography(Point, 4326), manager_name varchar(50), manager_phone varchar(100), construction_company varchar(200), development_company varchar(200), status construction_site_status_enum, district_id integer references district, city_id integer references city, construction_area real);
create table dust_station( id serial primary key, name varchar(200), station_code varchar(50) unique, construction_site_id integer references construction_site, coordinate geography(Point, 4326));
create table hourly_dust_station_air_quality( id serial primary key, station_id integer references dust_station, construction_site_id integer references construction_site, pm2_5 real, pm10 real, temperature real, humidity real, construction_site_status construction_site_status_enum, timestamp timestamp);
--The station_high_pollution_alert table stores the high pollution alert data of air quality stations:
create type high_pollution_pollutant_enum as enum('CO', 'NO2', 'PM10', 'PM2_5', 'SO2');
create type high_pollution_severity_level_enum as enum('MINOR', 'MODERATE', 'HIGH', 'SEVERE', 'EMERGENCY');
create table station_high_pollution_alert ( id serial primary key, station_id integer references air_quality_station, pollutant high_pollution_pollutant_enum, station_value real, background_value real, exceedance_percent real, severity_level high_pollution_severity_level_enum, timestamp timestamp, district_id integer references district, city_id integer references city);
--When you need to pollution source analysis, you can use the this table to get the wind speed and direction:
create table hourly_grid_wind( id serial primary key, coordinate geography(Point, 4326), wind_speed real, wind_direction varchar(10), wind_degree real, wind_scale smallint, timestamp timestamp);
</database_schema>
"""

KNOWLEDGE_BASE = """
<knowledge_base>
<cities_in_Hebei_Province>
city_id,name
2,唐山市
3,秦皇岛市
8,承德市
10,廊坊市
9,沧州市
11,衡水市
5,邢台市
4,邯郸市
1,石家庄市
6,保定市
7,张家口市
12,辛集市
14,定州市
13,雄安新区
</cities_in_Hebei_Province>
<special_districts>
district_id,district_name,city_name
71,武安市,邯郸市
</special_districts>
<wind_direction_definition>
Wind direction names (e.g., 东南风/Southeast wind, 北风/North wind) indicate the direction FROM which the wind originates, NOT the direction it's going to.
- 东南风 (Southeast wind) = Wind blowing FROM the southeast TO the northwest
- 北风 (North wind) = Wind blowing FROM the north TO the south
- 西北风 (Northwest wind) = Wind blowing FROM the northwest TO the southeast

Wind degree follows meteorological convention:
- 0° = North (wind FROM north)
- 90° = East (wind FROM east)
- 180° = South (wind FROM south)
- 270° = West (wind FROM west)
- Angles increase clockwise

</wind_direction_definition>
</knowledge_base>
"""

EXAMPLES = """
<example>
example1:
User: 今天10点哪些站点的AQI高出所在区县对应时间的百分之10
Assistant: 我先找出今天10点每个区县平均的AQI，然后找出前10个站点AQI超出平均值10%的站点。
```python
import pandas as pd
query = text(\"\"\"WITH district_avg_aqi AS( SELECT aqs.district_id, ROUND(AVG(hsaq.aqi)) as avg_aqi FROM hourly_station_air_quality hsaq JOIN air_quality_station aqs ON hsaq.station_id = aqs.id WHERE DATE(timestamp) = CURRENT_DATE AND EXTRACT(HOUR FROM timestamp) = 10 GROUP BY aqs.district_id) SELECT aqs.name AS station_name, d.name AS district_name, hsaq.aqi, da.avg_aqi FROM hourly_station_air_quality hsaq JOIN air_quality_station aqs ON hsaq.station_id = aqs.id JOIN district d ON aqs.district_id = d.id JOIN district_avg_aqi da ON d.id = da.district_id WHERE DATE(timestamp) = CURRENT_DATE AND EXTRACT(HOUR FROM timestamp) = 10 AND hsaq.aqi > da.avg_aqi * 1.1 LIMIT 10\"\"\")
df = pd.read_sql(query, engine)
print(df)
```
example2:
User: 帮我分析企业:河钢股份有限公司承德分公司 company_id：2534，longitude:117.716111, latitude:40.95 在时间2025-07-04 13:00:00到2025-07-04 15:00:00的污染传输情况，需要结合周边10公里的网格风场数据和周边5公里的空气质量站点数据
Assistant: 我来分析河钢股份有限公司承德分公司在指定时间段的污染传输情况。

```python
import pandas as pd
from sqlalchemy import text

# 分析企业污染传输情况
# 1. 先获取企业周边10公里的网格风场数据
query_wind = text(\"\"\"SELECT hgw.wind_speed, hgw.wind_direction, hgw.wind_degree, hgw.timestamp, ST_Distance(hgw.coordinate, ST_GeomFromText('POINT(117.716111 40.95)', 4326)) as distance_to_company FROM hourly_grid_wind hgw WHERE ST_DWithin(hgw.coordinate, ST_GeomFromText('POINT(117.716111 40.95)', 4326), 10000) AND hgw.timestamp BETWEEN '2025-07-04 13:00:00' AND '2025-07-04 15:00:00' ORDER BY hgw.timestamp, distance_to_company\"\"\")

wind_data = pd.read_sql(query_wind, engine)
print(f"企业周边10公里网格风场数据前10条：")
print(wind_data[:10])

# 2. 获取企业周边5公里的空气质量站点数据
query_stations = text(\"\"\"SELECT aqs.name as station_name, hsaq.timestamp, hsaq.aqi, hsaq.pm2_5, hsaq.pm10, hsaq.so2, hsaq.no2, hsaq.co, ST_Distance(aqs.coordinate, ST_GeomFromText('POINT(117.716111 40.95)', 4326)) as distance_to_company, ST_Azimuth(ST_GeomFromText('POINT(117.716111 40.95)', 4326), aqs.coordinate) * 180 / PI() as direction_from_company FROM air_quality_station aqs JOIN hourly_station_air_quality hsaq ON aqs.id = hsaq.station_id WHERE ST_DWithin(aqs.coordinate, ST_GeomFromText('POINT(117.716111 40.95)', 4326), 5000) AND hsaq.timestamp BETWEEN '2025-07-04 13:00:00' AND '2025-07-04 15:00:00' ORDER BY hsaq.timestamp, distance_to_company\"\"\")

station_data = pd.read_sql(query_stations, engine)
print(f"\\n企业周边5公里空气质量站点数据前10条：")
print(station_data[:10])

# 3. 获取企业自身的排放数据
query_emission = text(\"\"\"SELECT timestamp, exhaust_gas, nox, so2, pm, co FROM hourly_polluting_company_emission WHERE company_id = 2534 AND timestamp BETWEEN '2025-07-04 13:00:00' AND '2025-07-04 15:00:00' ORDER BY timestamp\"\"\")

emission_data = pd.read_sql(query_emission, engine)
print(f"\\n企业排放数据：")
print(emission_data)
```
</example>
"""
