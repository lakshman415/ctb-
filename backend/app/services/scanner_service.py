"""
Scanner service — the orchestrator.

Coordinates the full scan pipeline:
    1. Fetch raw pairs from DexScreener for each supported chain
    2. Parse into internal (TokenBase, SnapshotBase) tuples
    3. Categorize by market cap (early, mid, large)
    4. Apply per-category filters (liquidity, volume thresholds differ per tier)
    5. Score each surviving token
    6. Persist tokens and snapshots to the database
    7. Return combined ranked results

This service contains NO HTTP logic and NO direct DB queries.
It delegates to clients, parser, categorizer, filters, scoring, and repositories.
"""

import logging
from datetime import UTC, datetime

from app.clients.base import BaseClient
from app.clients.dexscreener_parser import DexScreenerParser
from app.config import Settings
from app.filters.age_filter import AgeFilter
from app.filters.buy_sell_ratio_filter import BuySellRatioFilter
from app.filters.liquidity_filter import LiquidityFilter
from app.filters.pipeline import FilterPipeline
from app.filters.volume_filter import VolumeFilter
from app.repositories.snapshot_repository import SnapshotRepository
from app.repositories.token_repository import TokenRepository
from app.schemas.scanner import RankedTokenResponse, ScannerResultResponse
from app.services.categorizer import CategoryThresholds, MarketCapCategorizer
from app.services.scoring_service import ScoringService

logger = logging.getLogger(__name__)


class ScannerService:
    """
    Orchestrates market scanning: fetch → parse → categorize → filter → score → store.

    Injected with all dependencies — easy to test with mocks.
    """

    def __init__(
        self,
        client: BaseClient,
        parser: DexScreenerParser,
        categorizer: MarketCapCategorizer,
        scoring_service: ScoringService,
        token_repo: TokenRepository,
        snapshot_repo: SnapshotRepository,
        settings: Settings,
    ):
        """
        Args:
            client: External API client (e.g., DexScreenerClient).
            parser: Transforms raw API responses into internal schemas.
            categorizer: Assigns tokens to market cap categories.
            scoring_service: Deterministic scoring engine.
            token_repo: Token persistence layer.
            snapshot_repo: Snapshot persistence layer.
            settings: Application configuration.
        """
        self._client = client
        self._parser = parser
        self._categorizer = categorizer
        self._scoring_service = scoring_service
        self._token_repo = token_repo
        self._snapshot_repo = snapshot_repo
        self._settings = settings

    async def run_scan(self) -> ScannerResultResponse:
        """
        Execute a full scan cycle across all supported chains.

        Returns:
            ScannerResultResponse with ranked, filtered tokens from all categories.
        """
        scan_start = datetime.now(tz=UTC)
        all_pairs = []
        total_fetched = 0

        # Step 1: Fetch pairs from each supported chain
        for chain in self._settings.supported_chains:
            try:
                raw_pairs = await self._client.fetch_pairs(chain)
                total_fetched += len(raw_pairs)
                logger.info(f"Fetched {len(raw_pairs)} pairs from {chain}")
            except Exception as e:
                logger.error(f"Failed to fetch pairs from {chain}: {e}")
                continue

            # Step 2: Parse raw pairs into (TokenBase, SnapshotBase) tuples
            from app.clients.dexscreener_models import DexPair

            dex_pairs = [DexPair.model_validate(p) for p in raw_pairs]
            parsed = self._parser.parse_pairs(dex_pairs)
            all_pairs.extend(parsed)

        logger.info(
            f"Scan fetched {total_fetched} raw pairs, "
            f"parsed {len(all_pairs)} valid pairs"
        )

        # Step 2.5a: Deduplicate — keep highest-liquidity pool per token
        all_pairs = self._deduplicate_by_best_pool(all_pairs)
        logger.info(f"After deduplication: {len(all_pairs)} unique tokens")

        # Step 2.5b: Enrich — for tokens with suspicious data, look up better pools
        all_pairs = await self._enrich_with_best_pools(all_pairs)

        # Step 2.5c: Quality gate — remove obvious scams/garbage BEFORE anything else
        from app.filters.quality_filter import QualityFilter

        quality_filter = QualityFilter(
            min_liquidity_absolute=5_000,       # At least $5K liquidity
            min_liquidity_mcap_ratio=0.02,      # Liquidity must be ≥2% of market cap
            min_volume_absolute=1_000,          # At least $1K volume
        )
        clean_pairs = quality_filter.apply(all_pairs)
        logger.info(
            f"Quality gate: {len(all_pairs)} → {len(clean_pairs)} "
            f"(removed {len(all_pairs) - len(clean_pairs)} scams/garbage)"
        )

        # Step 3: Categorize by market cap
        buckets = self._categorizer.categorize(clean_pairs)

        # Step 4 & 5: Filter and score each category
        all_ranked: list[RankedTokenResponse] = []

        for category in self._categorizer.categories:
            category_pairs = buckets.get(category.name, [])
            if not category_pairs:
                continue

            # Build per-category filter pipeline
            pipeline = self._build_filter_pipeline(category)
            filtered = pipeline.run(category_pairs)

            if not filtered:
                continue

            # Score the survivors
            ranked = self._scoring_service.score_tokens(filtered, category=category.name)
            all_ranked.extend(ranked)

        # Step 6: Persist tokens and snapshots
        persisted_count = self._persist_results(all_pairs)
        logger.info(f"Persisted {persisted_count} token snapshots")

        # Step 7: Score ALL tokens (unfiltered) for the frontend filter sidebar
        all_scored: list[RankedTokenResponse] = []
        for category in self._categorizer.categories:
            category_pairs = buckets.get(category.name, [])
            if category_pairs:
                scored = self._scoring_service.score_tokens(
                    category_pairs, category=category.name
                )
                all_scored.extend(scored)

        # Also score uncategorized tokens
        uncategorized = buckets.get("uncategorized", [])
        if uncategorized:
            scored = self._scoring_service.score_tokens(
                uncategorized, category="uncategorized"
            )
            all_scored.extend(scored)

        # Rank all scored tokens
        all_scored.sort(key=lambda x: x.score, reverse=True)
        for i, item in enumerate(all_scored, start=1):
            item.rank = i

        # Store the unfiltered result for the frontend
        self._last_unfiltered = ScannerResultResponse(
            scanned_at=scan_start,
            total_pairs_fetched=total_fetched,
            total_after_filter=len(all_scored),
            tokens=all_scored,
        )

        # Step 8: Re-rank the filtered results
        all_ranked.sort(key=lambda x: x.score, reverse=True)
        for i, item in enumerate(all_ranked, start=1):
            item.rank = i

        total_after_filter = len(all_ranked)
        logger.info(
            f"Scan complete: {total_fetched} fetched → {len(all_pairs)} parsed → "
            f"{len(all_scored)} scored → {total_after_filter} filtered"
        )

        return ScannerResultResponse(
            scanned_at=scan_start,
            total_pairs_fetched=total_fetched,
            total_after_filter=total_after_filter,
            tokens=all_ranked,
        )

    @property
    def last_unfiltered_result(self) -> ScannerResultResponse | None:
        """The most recent scan result with ALL tokens scored (no filter applied)."""
        return getattr(self, "_last_unfiltered", None)

    def _build_filter_pipeline(self, category: CategoryThresholds) -> FilterPipeline:
        """
        Build a filter pipeline with thresholds appropriate for the given category.

        Each category has different liquidity and volume minimums.
        Age and buy/sell ratio filters use shared defaults.
        """
        from datetime import timedelta

        return FilterPipeline(
            filters=[
                LiquidityFilter(min_liquidity=category.min_liquidity),
                VolumeFilter(min_volume=category.min_volume),
                AgeFilter(
                    min_age=timedelta(minutes=30),
                    max_age=timedelta(days=14),
                ),
                BuySellRatioFilter(min_ratio=0.8),
            ]
        )

    @staticmethod
    def _deduplicate_by_best_pool(pairs) -> list:
        """
        When multiple pools exist for the same token, keep only the best one.

        Best = highest liquidity (most tradeable pool).
        Groups by (chain, token_address) and picks the winner.
        """
        from app.filters.base import TokenPair

        best: dict[str, TokenPair] = {}

        for token, snapshot in pairs:
            key = f"{token.chain}:{token.token_address}"
            existing = best.get(key)

            if existing is None:
                best[key] = (token, snapshot)
            else:
                # Pick the pool with higher liquidity
                existing_liq = existing[1].liquidity or 0
                new_liq = snapshot.liquidity or 0
                if new_liq > existing_liq:
                    best[key] = (token, snapshot)

                # Also pick the one with higher market cap if liquidity is similar
                if abs(new_liq - existing_liq) < 1000:
                    existing_mcap = existing[0].market_cap or 0
                    new_mcap = token.market_cap or 0
                    if new_mcap > existing_mcap:
                        best[key] = (token, snapshot)

        return list(best.values())

    async def _enrich_with_best_pools(self, pairs) -> list:
        """
        For tokens where we might have a bad pool, look up all their pools
        and replace with the highest-liquidity one.

        This fixes the FRONG problem: we find it via search (bad pool),
        then look up all its pools and pick the $250K one.
        """
        from app.clients.dexscreener_models import DexPair

        enriched = []
        for token, snapshot in pairs:
            # If liquidity is suspiciously low relative to volume, try to find a better pool
            vol = snapshot.volume_24h or 0
            liq = snapshot.liquidity or 0

            if vol > liq * 10 and liq < 50_000:
                # Volume >> liquidity suggests we have the wrong pool
                try:
                    better_pairs = await self._client.get_token_pairs(
                        token.chain, token.token_address
                    )
                    if better_pairs:
                        # Pick highest liquidity pool
                        best = max(
                            better_pairs,
                            key=lambda p: (p.liquidity.usd if p.liquidity else 0),
                        )
                        # Re-parse with the better pool
                        better_token = self._parser.parse_pair_to_token(best)
                        better_snapshot = self._parser.parse_pair_to_snapshot(best)
                        enriched.append((better_token, better_snapshot))
                        continue
                except Exception:
                    pass

            enriched.append((token, snapshot))

        return enriched

    def _persist_results(self, pairs) -> int:
        """
        Persist all scanned tokens and their snapshots.

        Upserts tokens (creates or updates) and always appends new snapshots.
        Returns the number of snapshots persisted.
        """
        from app.models.snapshot import Snapshot

        count = 0
        for token_schema, snapshot_schema in pairs:
            try:
                # Upsert token
                db_token = self._token_repo.upsert(token_schema)

                # Create snapshot
                snapshot = Snapshot(
                    token_id=db_token.id,
                    price=snapshot_schema.price,
                    volume_5m=snapshot_schema.volume_5m,
                    volume_1h=snapshot_schema.volume_1h,
                    volume_6h=snapshot_schema.volume_6h,
                    volume_24h=snapshot_schema.volume_24h,
                    buys=snapshot_schema.buys,
                    sells=snapshot_schema.sells,
                    price_change_5m=snapshot_schema.price_change_5m,
                    price_change_1h=snapshot_schema.price_change_1h,
                    price_change_6h=snapshot_schema.price_change_6h,
                    price_change_24h=snapshot_schema.price_change_24h,
                    liquidity=snapshot_schema.liquidity,
                )
                self._snapshot_repo.create(snapshot)
                count += 1

            except Exception as e:
                logger.warning(
                    f"Failed to persist {token_schema.symbol} "
                    f"({token_schema.pair_address}): {e}"
                )
                continue

        return count
