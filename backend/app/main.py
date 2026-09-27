"""
FastAPI application factory.

Creates and configures the application instance:
    - Loads settings
    - Initializes database
    - Sets up logging
    - Registers routers
    - Configures startup/shutdown lifecycle events
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_v1_router
from app.config import get_settings
from app.core.database import init_db
from app.core.logging import setup_logging
from app.scheduler.jobs import init_scheduler, shutdown_scheduler, start_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Startup: init DB, init scheduler, start scheduler.
    Shutdown: stop scheduler, clean up resources.
    """
    settings = get_settings()

    # Initialize database engine and session factory
    init_db(settings.database_url)
    logger.info("Database initialized")

    # Auto-create tables for SQLite (in production, use Alembic migrations)
    if settings.database_url.startswith("sqlite"):
        from app.core.database import Base, engine
        from app.core.migrations import run_sqlite_migrations
        from app.models import (  # noqa: F401 — register models
            Alert, JournalEntry, Snapshot, Token, Watchlist, WatchlistItem,
        )

        Base.metadata.create_all(bind=engine)
        logger.info("SQLite tables created")

        # create_all can't alter pre-existing tables — patch in new columns
        run_sqlite_migrations(engine)

    # Initialize and start the periodic scanner
    init_scheduler(settings.scanner_interval_seconds)
    start_scheduler()
    logger.info("Application startup complete")

    yield

    # Shutdown
    shutdown_scheduler()
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """
    Application factory.

    Returns a fully configured FastAPI instance.
    """
    settings = get_settings()

    # Configure logging before anything else
    setup_logging(level=settings.log_level)

    app = FastAPI(
        title="CTB - Crypto Trading Brain",
        description="Market intelligence platform for memecoin scalping",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Register API routes
    app.include_router(api_v1_router)

    return app


# Application instance used by uvicorn
app = create_app()
