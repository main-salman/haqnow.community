import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()

# Use a robust SQLite setup for tests to avoid disk I/O and threading issues.
if os.getenv("PYTEST_CURRENT_TEST"):
    # Single in-memory database shared across the process
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    # Normalize postgres URI for SQLAlchemy (psycopg2)
    db_url = settings.database_url.replace("postgres://", "postgresql+psycopg2://")
    engine = create_engine(
        db_url,
        future=True,
        connect_args={"check_same_thread": False}
        if settings.database_url.startswith("sqlite")
        else {},
    )
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
