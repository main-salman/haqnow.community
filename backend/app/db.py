import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
# Use in-memory sqlite during tests to avoid disk I/O issues
_database_url = settings.database_url
if os.getenv("PYTEST_CURRENT_TEST"):
    _database_url = "sqlite+pysqlite:///:memory:"
engine = create_engine(_database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
