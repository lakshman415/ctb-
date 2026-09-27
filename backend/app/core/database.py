"""
Database engine and session management.

Provides the SQLAlchemy engine, session factory, and a dependency-injectable
session generator for use in FastAPI endpoints and services.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


# Engine and session factory are initialized at app startup via init_db().
engine = None
SessionLocal: sessionmaker[Session] | None = None


def init_db(database_url: str) -> None:
    """
    Initialize the database engine and session factory.

    Called once during application startup with the DATABASE_URL from settings.
    """
    global engine, SessionLocal
    engine = create_engine(database_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Yield a database session for dependency injection.

    Usage in FastAPI:
        db: Session = Depends(get_db)
    """
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
