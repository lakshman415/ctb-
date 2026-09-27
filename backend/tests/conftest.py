"""
Shared test fixtures.

Provides:
    - In-memory SQLite database for fast, isolated tests
    - Test DB session
    - FastAPI test client with dependency overrides
    - Sample token and snapshot factories
"""

from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.router import api_v1_router
from app.config import Settings
from app.core.database import Base, get_db
from app.dependencies import get_cached_settings

# In-memory SQLite for tests — no PostgreSQL required to run unit tests.
TEST_DATABASE_URL = "sqlite:///./test.db"


@pytest.fixture(scope="session")
def test_engine():
    """Create a test database engine (session-scoped for speed)."""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(test_engine):
    """Provide a clean database session per test (rolled back after each test)."""
    test_session_local = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = test_session_local()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def test_settings() -> Settings:
    """Provide test settings with known values."""
    return Settings(
        app_env="testing",
        app_debug=True,
        log_level="DEBUG",
        database_url=TEST_DATABASE_URL,
        scanner_interval_seconds=300,  # Slow interval for tests
        supported_chains=["solana", "ethereum"],
    )


def _create_test_app() -> FastAPI:
    """
    Create a FastAPI app for testing WITHOUT the production lifespan.

    The production lifespan tries to connect to PostgreSQL and start the scheduler.
    Tests don't need that — they use SQLite and override dependencies directly.
    """

    @asynccontextmanager
    async def _test_lifespan(app: FastAPI):
        yield

    app = FastAPI(
        title="CTB Test",
        lifespan=_test_lifespan,
    )
    app.include_router(api_v1_router)
    return app


@pytest.fixture
def client(db_session: Session, test_settings: Settings):
    """
    FastAPI test client with overridden dependencies.

    Uses a test app (no PostgreSQL, no scheduler) with a test DB session
    and test settings so tests are fully isolated from real infrastructure.
    """
    app = _create_test_app()

    def _override_db():
        yield db_session

    def _override_settings():
        return test_settings

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_cached_settings] = _override_settings

    with TestClient(app) as tc:
        yield tc

    app.dependency_overrides.clear()
