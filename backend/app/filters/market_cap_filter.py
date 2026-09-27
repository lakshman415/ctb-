"""
Market cap filter.

Removes tokens outside the configured market cap range.

Why this matters:
    - Tokens below the minimum MC are too risky (often rugs/honeypots)
    - Tokens above the maximum MC have already run (not scalping opportunities)
    - Different MC ranges need different volume/liquidity thresholds
"""

import logging

from app.filters.base import BaseFilter, TokenPair

logger = logging.getLogger(__name__)


class MarketCapFilter(BaseFilter):
    """Filters tokens outside the target market cap range."""

    def __init__(self, mc_min: float, mc_max: float):
        """
        Args:
            mc_min: Minimum market cap (inclusive).
            mc_max: Maximum market cap (inclusive).
        """
        self._mc_min = mc_min
        self._mc_max = mc_max

    @property
    def name(self) -> str:
        return "MarketCapFilter"

    def apply(self, pairs: list[TokenPair]) -> list[TokenPair]:
        """
        Remove tokens outside the market cap range.

        Tokens with None market cap are removed (no data = can't categorize).
        """
        result = []
        for token, snapshot in pairs:
            market_cap = token.market_cap

            # No market cap data — can't classify
            if market_cap is None:
                continue

            if self._mc_min <= market_cap <= self._mc_max:
                result.append((token, snapshot))

        filtered_count = len(pairs) - len(result)
        if filtered_count > 0:
            logger.debug(
                f"{self.name}: removed {filtered_count} tokens "
                f"(range=${self._mc_min:,.0f}–${self._mc_max:,.0f})"
            )

        return result
