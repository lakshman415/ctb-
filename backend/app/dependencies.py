"""
Dependency injection providers for FastAPI.

Centralizes all dependency construction so endpoints stay thin.
Override these in tests to inject mocks/fakes without touching business logic.
"""

from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from app.clients.dexscreener import DexScreenerClient
from app.clients.dexscreener_parser import DexScreenerParser
from app.config import Settings, get_settings
from app.core.database import get_db
from app.repositories.snapshot_repository import SnapshotRepository
from app.repositories.token_repository import TokenRepository
from app.services.categorizer import MarketCapCategorizer
from app.services.scanner_service import ScannerService
from app.services.scoring_service import ScoringService
from app.services.snapshot_service import SnapshotService


@lru_cache
def get_cached_settings() -> Settings:
    """
    Cached settings instance.

    Avoids re-reading .env on every request. Cache is invalidated on restart.
    """
    return get_settings()


def get_token_repository(db: Session = Depends(get_db)) -> TokenRepository:
    """Provide a TokenRepository bound to the current DB session."""
    return TokenRepository(db)


def get_snapshot_repository(db: Session = Depends(get_db)) -> SnapshotRepository:
    """Provide a SnapshotRepository bound to the current DB session."""
    return SnapshotRepository(db)


def get_scoring_service(
    settings: Settings = Depends(get_cached_settings),
) -> ScoringService:
    """Provide the scoring service with current settings."""
    return ScoringService(settings)


def get_snapshot_service(
    snapshot_repo: SnapshotRepository = Depends(get_snapshot_repository),
) -> SnapshotService:
    """Provide the snapshot service with its repository."""
    return SnapshotService(snapshot_repo)


def get_scanner_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_cached_settings),
) -> ScannerService:
    """
    Provide a fully-assembled ScannerService for on-demand scans.

    Creates all dependencies fresh for each request.
    """
    client = DexScreenerClient(
        base_url=settings.dexscreener_base_url,
        verify_ssl=settings.dexscreener_verify_ssl,
    )
    parser = DexScreenerParser()
    categorizer = MarketCapCategorizer(settings)
    scoring_service = ScoringService(settings)
    token_repo = TokenRepository(db)
    snapshot_repo = SnapshotRepository(db)

    return ScannerService(
        client=client,
        parser=parser,
        categorizer=categorizer,
        scoring_service=scoring_service,
        token_repo=token_repo,
        snapshot_repo=snapshot_repo,
        settings=settings,
    )
