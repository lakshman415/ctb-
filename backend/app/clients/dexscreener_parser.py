"""
DexScreener response parser.

Maps raw DexScreener API responses (DexPair) into our internal domain schemas
(TokenBase + SnapshotBase). This is a pure transformation layer — no I/O,
no side effects, fully testable.

Why this exists separately from the client:
    - Single Responsibility: client fetches, parser transforms
    - Testability: parser can be unit tested with static fixtures
    - Flexibility: if DexScreener changes their response shape, only this file changes
"""

import logging
from datetime import UTC, datetime

from app.clients.dexscreener_models import DexPair
from app.schemas.snapshot import SnapshotBase
from app.schemas.token import TokenBase

logger = logging.getLogger(__name__)


class DexScreenerParser:
    """
    Transforms DexScreener DexPair objects into internal TokenBase + SnapshotBase.

    Handles:
        - Null/missing field safety (DexScreener responses are sparse)
        - Price string → float conversion
        - Unix ms timestamp → datetime conversion
        - Social link extraction (twitter, telegram, website)
        - Volume/txn/priceChange extraction by time period
    """

    def parse_pair_to_token(self, pair: DexPair) -> TokenBase:
        """
        Extract persistent token identity data from a DexPair.

        This produces the data stored in the `tokens` table — things that
        don't change between snapshots (address, name, chain, socials).

        Args:
            pair: A validated DexPair from the DexScreener API.

        Returns:
            TokenBase schema ready for persistence or further processing.
        """
        return TokenBase(
            pair_address=pair.pairAddress,
            token_address=pair.baseToken.address,
            name=pair.baseToken.name,
            symbol=pair.baseToken.symbol,
            chain=pair.chainId,
            price=self._parse_price(pair.priceUsd),
            market_cap=pair.marketCap,
            fdv=pair.fdv,
            liquidity=self._extract_liquidity_usd(pair),
            pair_created_at=self._ms_to_datetime(pair.pairCreatedAt),
            website=self._extract_website(pair),
            twitter=self._extract_social(pair, "twitter"),
            telegram=self._extract_social(pair, "telegram"),
        )

    def parse_pair_to_snapshot(self, pair: DexPair) -> SnapshotBase:
        """
        Extract point-in-time market data from a DexPair.

        This produces the data stored in the `snapshots` table — things that
        change every scan cycle (price, volume, buys, sells, price changes).

        Args:
            pair: A validated DexPair from the DexScreener API.

        Returns:
            SnapshotBase schema ready for persistence.
        """
        # Extract transaction counts (sum across all time periods for current snapshot)
        buys_24h, sells_24h = self._extract_txns_24h(pair)

        return SnapshotBase(
            price=self._parse_price(pair.priceUsd) or 0.0,
            volume_5m=pair.volume.get("m5"),
            volume_1h=pair.volume.get("h1"),
            volume_6h=pair.volume.get("h6"),
            volume_24h=pair.volume.get("h24"),
            buys=buys_24h,
            sells=sells_24h,
            price_change_5m=pair.priceChange.get("m5"),
            price_change_1h=pair.priceChange.get("h1"),
            price_change_6h=pair.priceChange.get("h6"),
            price_change_24h=pair.priceChange.get("h24"),
            liquidity=self._extract_liquidity_usd(pair),
        )

    def parse_pairs(self, pairs: list[DexPair]) -> list[tuple[TokenBase, SnapshotBase]]:
        """
        Parse a batch of DexPair objects into (token, snapshot) tuples.

        Skips pairs that fail parsing (logs warning, doesn't crash the pipeline).

        Args:
            pairs: List of DexPair objects from the API.

        Returns:
            List of (TokenBase, SnapshotBase) tuples for valid pairs.
        """
        results: list[tuple[TokenBase, SnapshotBase]] = []

        for pair in pairs:
            try:
                # Skip pairs with no pair address (invalid data)
                if not pair.pairAddress:
                    logger.debug(f"Skipping pair with empty pairAddress: {pair}")
                    continue

                token = self.parse_pair_to_token(pair)
                snapshot = self.parse_pair_to_snapshot(pair)
                results.append((token, snapshot))

            except Exception as e:
                logger.warning(
                    f"Failed to parse pair {pair.pairAddress} on {pair.chainId}: {e}"
                )
                continue

        logger.info(f"Parsed {len(results)}/{len(pairs)} pairs successfully")
        return results

    # ─── Private Helpers ────────────────────────────────────────────────

    @staticmethod
    def _parse_price(price_str: str | None) -> float | None:
        """
        Convert DexScreener price string to float.

        DexScreener returns prices as strings (e.g., "0.00001234").
        Returns None if unparseable.
        """
        if price_str is None:
            return None
        try:
            return float(price_str)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _ms_to_datetime(timestamp_ms: int | None) -> datetime | None:
        """
        Convert Unix millisecond timestamp to timezone-aware datetime.

        DexScreener's pairCreatedAt is in milliseconds.
        """
        if timestamp_ms is None:
            return None
        try:
            return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)
        except (ValueError, TypeError, OSError):
            return None

    @staticmethod
    def _extract_liquidity_usd(pair: DexPair) -> float | None:
        """Extract USD liquidity value, handling null liquidity object."""
        if pair.liquidity is None:
            return None
        return pair.liquidity.usd

    @staticmethod
    def _extract_website(pair: DexPair) -> str | None:
        """Extract the first website URL from pair info."""
        if pair.info is None:
            return None
        if pair.info.websites:
            return pair.info.websites[0].url or None
        return None

    @staticmethod
    def _extract_social(pair: DexPair, platform: str) -> str | None:
        """
        Extract a specific social handle/URL from pair info.

        Args:
            pair: The DexPair to extract from.
            platform: Platform name to match (e.g., "twitter", "telegram").

        Returns:
            The handle string if found, None otherwise.
        """
        if pair.info is None:
            return None
        for social in pair.info.socials:
            if social.platform.lower() == platform.lower():
                return social.handle or None
        return None

    @staticmethod
    def _extract_txns_24h(pair: DexPair) -> tuple[int | None, int | None]:
        """
        Extract 24h buy and sell counts from transactions data.

        DexScreener provides txns keyed by time period. We want h24 for scoring.
        Falls back to h6, h1 if h24 not available.

        Returns:
            Tuple of (buys, sells) for the best available time period.
        """
        # Try time periods in order of preference
        for period in ("h24", "h6", "h1"):
            if period in pair.txns:
                txn = pair.txns[period]
                return txn.buys, txn.sells

        return None, None
