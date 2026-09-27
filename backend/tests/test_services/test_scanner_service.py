"""
Integration tests for the ScannerService pipeline.

Tests the full flow: fetch → parse → categorize → filter → score → persist.
Uses a mock client to avoid real API calls and an in-memory SQLite DB.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.clients.base import BaseClient
from app.clients.dexscreener_parser import DexScreenerParser
from app.config import Settings
from app.core.database import Base
from app.models.snapshot import Snapshot
from app.models.token import Token
from app.repositories.snapshot_repository import SnapshotRepository
from app.repositories.token_repository import TokenRepository
from app.services.categorizer import MarketCapCategorizer
from app.services.scanner_service import ScannerService
from app.services.scoring_service import ScoringService

# ─── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def integration_engine():
    """In-memory SQLite for integration tests."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def integration_session(integration_engine):
    """Fresh DB session per test."""
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=integration_engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def settings() -> Settings:
    """Test settings with default thresholds."""
    return Settings(
        app_env="testing",
        database_url="sqlite:///:memory:",
        supported_chains=["solana"],
    )


def _make_raw_pair(
    chain: str = "solana",
    pair_address: str = "pair_abc123",
    token_address: str = "addr_abc123",
    name: str = "TestToken",
    symbol: str = "TEST",
    price_usd: str = "0.005",
    market_cap: float = 500_000,
    fdv: float = 600_000,
    liquidity_usd: float = 100_000,
    volume_24h: float = 300_000,
    buys_24h: int = 200,
    sells_24h: int = 100,
    price_change_1h: float = 5.0,
    pair_created_ms: int | None = None,
    website: str | None = "https://testtoken.io",
    twitter: str | None = "testtoken",
    telegram: str | None = "testchat",
) -> dict[str, Any]:
    """Build a raw pair dict matching DexScreener response format."""
    if pair_created_ms is None:
        # Default: 12 hours ago
        pair_created_ms = int(
            (datetime.now(tz=UTC) - timedelta(hours=12)).timestamp() * 1000
        )

    pair = {
        "chainId": chain,
        "dexId": "raydium",
        "url": f"https://dexscreener.com/{chain}/{pair_address}",
        "pairAddress": pair_address,
        "baseToken": {
            "address": token_address,
            "name": name,
            "symbol": symbol,
        },
        "quoteToken": {
            "address": "USDC_ADDR",
            "name": "USDC",
            "symbol": "USDC",
        },
        "priceUsd": price_usd,
        "txns": {
            "h24": {"buys": buys_24h, "sells": sells_24h},
            "h1": {"buys": buys_24h // 24, "sells": sells_24h // 24},
        },
        "volume": {
            "h24": volume_24h,
            "h1": volume_24h / 24,
        },
        "priceChange": {
            "h1": price_change_1h,
            "h24": price_change_1h * 3,
        },
        "liquidity": {"usd": liquidity_usd, "base": 1000000, "quote": 50000},
        "fdv": fdv,
        "marketCap": market_cap,
        "pairCreatedAt": pair_created_ms,
        "info": {
            "imageUrl": "https://example.com/logo.png",
            "websites": [{"url": website}] if website else [],
            "socials": [],
        },
    }

    # Add socials
    if twitter:
        pair["info"]["socials"].append({"platform": "twitter", "handle": twitter})
    if telegram:
        pair["info"]["socials"].append({"platform": "telegram", "handle": telegram})

    return pair


class MockClient(BaseClient):
    """Mock DexScreener client that returns pre-configured pairs."""

    def __init__(self, pairs_by_chain: dict[str, list[dict[str, Any]]]):
        self._pairs_by_chain = pairs_by_chain

    async def fetch_pairs(self, chain: str) -> list[dict[str, Any]]:
        return self._pairs_by_chain.get(chain, [])

    async def close(self) -> None:
        pass


# ─── Integration Tests ──────────────────────────────────────────────────────


class TestScannerServiceIntegration:
    """Full pipeline integration tests."""

    @pytest.mark.asyncio
    async def test_full_pipeline_with_passing_token(
        self, integration_session: Session, settings: Settings
    ):
        """A token that meets all criteria should appear in results."""
        raw_pairs = [
            _make_raw_pair(
                symbol="GOOD",
                market_cap=500_000,
                liquidity_usd=100_000,
                volume_24h=300_000,
                buys_24h=200,
                sells_24h=100,
            )
        ]

        client = MockClient(pairs_by_chain={"solana": raw_pairs})
        scanner = ScannerService(
            client=client,
            parser=DexScreenerParser(),
            categorizer=MarketCapCategorizer(settings),
            scoring_service=ScoringService(settings),
            token_repo=TokenRepository(integration_session),
            snapshot_repo=SnapshotRepository(integration_session),
            settings=settings,
        )

        result = await scanner.run_scan()

        assert result.total_pairs_fetched == 1
        assert result.total_after_filter == 1
        assert result.tokens[0].symbol == "GOOD"
        assert result.tokens[0].rank == 1
        assert result.tokens[0].score > 0
        assert result.tokens[0].category == "early"
        assert len(result.tokens[0].score_reasons) == 6

    @pytest.mark.asyncio
    async def test_low_liquidity_filtered_out(
        self, integration_session: Session, settings: Settings
    ):
        """A token below minimum liquidity should not appear in results."""
        raw_pairs = [
            _make_raw_pair(
                symbol="LOW_LIQ",
                market_cap=500_000,
                liquidity_usd=10_000,  # Below 40K early threshold
                volume_24h=300_000,
            )
        ]

        client = MockClient(pairs_by_chain={"solana": raw_pairs})
        scanner = ScannerService(
            client=client,
            parser=DexScreenerParser(),
            categorizer=MarketCapCategorizer(settings),
            scoring_service=ScoringService(settings),
            token_repo=TokenRepository(integration_session),
            snapshot_repo=SnapshotRepository(integration_session),
            settings=settings,
        )

        result = await scanner.run_scan()

        # Token is filtered out but still persisted (we save everything)
        assert result.total_pairs_fetched == 1
        assert result.total_after_filter == 0

    @pytest.mark.asyncio
    async def test_persistence_creates_token_and_snapshot(
        self, integration_session: Session, settings: Settings
    ):
        """Scanned tokens should be persisted to the database."""
        raw_pairs = [
            _make_raw_pair(symbol="PERSIST", pair_address="persist_pair_001")
        ]

        client = MockClient(pairs_by_chain={"solana": raw_pairs})
        scanner = ScannerService(
            client=client,
            parser=DexScreenerParser(),
            categorizer=MarketCapCategorizer(settings),
            scoring_service=ScoringService(settings),
            token_repo=TokenRepository(integration_session),
            snapshot_repo=SnapshotRepository(integration_session),
            settings=settings,
        )

        await scanner.run_scan()

        # Verify token was persisted
        token = (
            integration_session.query(Token)
            .filter(Token.pair_address == "persist_pair_001")
            .first()
        )
        assert token is not None
        assert token.symbol == "PERSIST"
        assert token.chain == "solana"

        # Verify snapshot was created
        snapshots = (
            integration_session.query(Snapshot)
            .filter(Snapshot.token_id == token.id)
            .all()
        )
        assert len(snapshots) == 1
        assert snapshots[0].volume_24h == 300_000

    @pytest.mark.asyncio
    async def test_upsert_updates_existing_token(
        self, integration_session: Session, settings: Settings
    ):
        """Running scan twice should update the token, not create a duplicate."""
        raw_pairs = [
            _make_raw_pair(
                symbol="UPS",
                pair_address="upsert_pair",
                market_cap=500_000,
            )
        ]

        client = MockClient(pairs_by_chain={"solana": raw_pairs})

        scanner = ScannerService(
            client=client,
            parser=DexScreenerParser(),
            categorizer=MarketCapCategorizer(settings),
            scoring_service=ScoringService(settings),
            token_repo=TokenRepository(integration_session),
            snapshot_repo=SnapshotRepository(integration_session),
            settings=settings,
        )

        # First scan
        await scanner.run_scan()

        # Change market cap for second scan
        raw_pairs[0]["marketCap"] = 600_000
        client = MockClient(pairs_by_chain={"solana": raw_pairs})
        scanner._client = client

        # Second scan
        await scanner.run_scan()

        # Should still be only 1 token
        tokens = (
            integration_session.query(Token)
            .filter(Token.pair_address == "upsert_pair")
            .all()
        )
        assert len(tokens) == 1
        assert tokens[0].market_cap == 600_000

        # But should have 2 snapshots (one per scan)
        snapshots = (
            integration_session.query(Snapshot)
            .filter(Snapshot.token_id == tokens[0].id)
            .all()
        )
        assert len(snapshots) == 2

    @pytest.mark.asyncio
    async def test_multiple_categories(
        self, integration_session: Session, settings: Settings
    ):
        """Tokens from different categories should all appear in results."""
        raw_pairs = [
            _make_raw_pair(
                symbol="EARLY",
                pair_address="pair_early",
                token_address="addr_early",
                market_cap=500_000,
                liquidity_usd=60_000,
                volume_24h=200_000,
            ),
            _make_raw_pair(
                symbol="MID",
                pair_address="pair_mid",
                token_address="addr_mid",
                market_cap=5_000_000,
                liquidity_usd=200_000,
                volume_24h=1_000_000,
            ),
        ]

        client = MockClient(pairs_by_chain={"solana": raw_pairs})
        scanner = ScannerService(
            client=client,
            parser=DexScreenerParser(),
            categorizer=MarketCapCategorizer(settings),
            scoring_service=ScoringService(settings),
            token_repo=TokenRepository(integration_session),
            snapshot_repo=SnapshotRepository(integration_session),
            settings=settings,
        )

        result = await scanner.run_scan()

        assert result.total_after_filter == 2
        categories = {t.category for t in result.tokens}
        assert "early" in categories
        assert "mid" in categories

    @pytest.mark.asyncio
    async def test_empty_chain_response(
        self, integration_session: Session, settings: Settings
    ):
        """Scanner handles empty API responses gracefully."""
        client = MockClient(pairs_by_chain={"solana": []})
        scanner = ScannerService(
            client=client,
            parser=DexScreenerParser(),
            categorizer=MarketCapCategorizer(settings),
            scoring_service=ScoringService(settings),
            token_repo=TokenRepository(integration_session),
            snapshot_repo=SnapshotRepository(integration_session),
            settings=settings,
        )

        result = await scanner.run_scan()

        assert result.total_pairs_fetched == 0
        assert result.total_after_filter == 0
        assert result.tokens == []

    @pytest.mark.asyncio
    async def test_client_error_doesnt_crash(
        self, integration_session: Session, settings: Settings
    ):
        """If the client raises, the scan continues with other chains."""
        client = AsyncMock(spec=BaseClient)
        client.fetch_pairs.side_effect = Exception("API timeout")

        scanner = ScannerService(
            client=client,
            parser=DexScreenerParser(),
            categorizer=MarketCapCategorizer(settings),
            scoring_service=ScoringService(settings),
            token_repo=TokenRepository(integration_session),
            snapshot_repo=SnapshotRepository(integration_session),
            settings=settings,
        )

        # Should not raise
        result = await scanner.run_scan()

        assert result.total_pairs_fetched == 0
        assert result.total_after_filter == 0
