"""
SQLAlchemy 2.0 database engine, session management, and DeclarativeBase setup.
Includes auto-normalization for PostgreSQL URL schemes ('postgres://' -> 'postgresql+psycopg://').
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from app.config.settings import Settings

settings = Settings()

connect_args = {}
db_url = settings.database_url

# Normalize legacy or shorthand PostgreSQL URL schemes for SQLAlchemy 2.0
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
elif db_url.startswith("postgres+"):
    db_url = db_url.replace("postgres+", "postgresql+", 1)

if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    db_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy 2.0 ORM models."""

    pass


def get_db() -> Generator[Session, None, None]:
    """
    Dependency generator providing a transactional SQLAlchemy session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Create all defined database tables if they do not already exist.
    """
    Base.metadata.create_all(bind=engine)


def clear_db() -> None:
    """
    Drop all existing tables and recreate a completely fresh, empty database schema.
    """
    # Import all models to ensure metadata registers all tables
    import app.models  # noqa: F401

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
