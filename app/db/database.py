"""SQLAlchemy database setup."""

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker, declarative_base

from app.config import get_settings

settings = get_settings()

# Ensure data directory exists
Path(settings.data_dir).mkdir(parents=True, exist_ok=True)

# Create engine with connection pool settings for better concurrency
engine = create_engine(
    settings.database_url,
    connect_args={
        "check_same_thread": False,  # Needed for SQLite
        "timeout": 30,  # Wait up to 30 seconds for locks
    },
    echo=False,
    pool_pre_ping=True,  # Check connection health
)


# Enable WAL mode for better concurrency (allows concurrent reads while writing)
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")  # 30 second timeout
    cursor.close()

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database tables."""
    from app.db import models  # noqa: F401 - Import models to register them

    Base.metadata.create_all(bind=engine)
