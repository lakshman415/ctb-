"""
Quality filter — eliminates scams and garbage data BEFORE scoring.

This filter runs on ALL tokens before they reach the frontend.
It catches the obvious trash that no legitimate trader would look at:

Key scam indicators:
    1. Liquidity/MCap ratio too low (fake market cap, no real liquidity)
    2. Zero or near-zero liquidity (can't trade it)
    3. Zero volume (dead token or wash trading stopped)
    4. Market cap with no liquidity backing (honeypot)
    5. Extreme buy/sell imbalance with no volume (wash trading)
    6. No price data (broken pair)

The rule of thumb from experienced memecoin traders:
    - Liquidity should be at least 5% of market cap for micro/small caps
    - Liquidity should be at least 2% of market cap for mid/large caps
    - A token with $7M mcap and $2 liquidity = 100% scam

Sources:
    - smithii.io: "liquidity should equal at least 10-20% of market cap"
    - Experienced traders use 5% as minimum viable threshold
"""

import logging

from app.filters.base import BaseFilter, TokenPair

logger = logging.getLogger(__name__)


class QualityFilter(BaseFilter):
    """
    Eliminates obviously fake/scam tokens based on data quality metrics.

    This is NOT a trading filter (those are user-configurable).
    This is a DATA QUALITY gate — removes tokens that have impossible
    or clearly manipulated metrics.
    """

    def __init__(
        self,
        min_liquidity_absolute: float = 1_000,
        min_liquidity_mcap_ratio: float = 0.02,
        min_volume_absolute: float = 100,
        min_price: float = 0,
    ):
        """
        Args:
            min_liquidity_absolute: Minimum USD liquidity to be considered real ($1K).
            min_liquidity_mcap_ratio: Min liquidity/mcap ratio (2% = 0.02).
                If a token has $5M mcap, it needs at least $100K liquidity.
            min_volume_absolute: Minimum 24h volume to show any activity ($100).
            min_price: Minimum price (0 = must have non-zero price).
        """
        self._min_liquidity_absolute = min_liquidity_absolute
        self._min_liquidity_mcap_ratio = min_liquidity_mcap_ratio
        self._min_volume_absolute = min_volume_absolute
        self._min_price = min_price

    @property
    def name(self) -> str:
        return "QualityFilter"

    def apply(self, pairs: list[TokenPair]) -> list[TokenPair]:
        """
        Remove tokens with impossible or clearly fake metrics.

        A token is removed if ANY of these are true:
            - No price data
            - Liquidity is None or below absolute minimum
            - Market cap exists but liquidity/mcap ratio is too low (scam signal)
            - Volume is None or zero (dead/fake token)
        """
        result = []
        removed_reasons: dict[str, int] = {
            "no_price": 0,
            "no_liquidity": 0,
            "low_liquidity": 0,
            "bad_liq_mcap_ratio": 0,
            "no_volume": 0,
        }

        for token, snapshot in pairs:
            # Must have price
            if token.price is None or token.price <= self._min_price:
                removed_reasons["no_price"] += 1
                continue

            # Must have liquidity data
            if snapshot.liquidity is None:
                removed_reasons["no_liquidity"] += 1
                continue

            # Liquidity must be above absolute minimum
            if snapshot.liquidity < self._min_liquidity_absolute:
                removed_reasons["low_liquidity"] += 1
                continue

            # If market cap exists, check liquidity/mcap ratio
            # This is the KEY scam detector:
            # $7M mcap with $2 liquidity = ratio of 0.0000003 = SCAM
            # $500K mcap with $50K liquidity = ratio of 0.10 = LEGITIMATE
            if token.market_cap is not None and token.market_cap > 0:
                ratio = snapshot.liquidity / token.market_cap
                if ratio < self._min_liquidity_mcap_ratio:
                    removed_reasons["bad_liq_mcap_ratio"] += 1
                    continue

            # Must have some volume (24h or 6h or 1h)
            volume = snapshot.volume_24h or snapshot.volume_6h or snapshot.volume_1h
            if volume is None or volume < self._min_volume_absolute:
                removed_reasons["no_volume"] += 1
                continue

            result.append((token, snapshot))

        total_removed = len(pairs) - len(result)
        if total_removed > 0:
            logger.info(
                f"{self.name}: removed {total_removed}/{len(pairs)} garbage tokens "
                f"(no_price={removed_reasons['no_price']}, "
                f"no_liq={removed_reasons['no_liquidity']}, "
                f"low_liq={removed_reasons['low_liquidity']}, "
                f"bad_ratio={removed_reasons['bad_liq_mcap_ratio']}, "
                f"no_vol={removed_reasons['no_volume']})"
            )

        return result
