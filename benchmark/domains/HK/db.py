from sqlalchemy import create_engine
from config import settings

engine = create_engine(
    settings.hk_database_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args={"connect_timeout": 5, "options": "-c statement_timeout=3000"},
)
