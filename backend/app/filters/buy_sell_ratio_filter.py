"""
Buy/Sell ratio filter.

Removes tokens where the buy-to-sell ratio indicates weak buying pressure.

Why buy/sell ratio matters:
    - A healthy scalping candidate has more buyers than sellers (momentum)
    - Ratio < 1.0 means selling pressure dominates — price likely dropping
    - Ratio > 2.0 might indicate wash trading (should be flagged, not filtered)
"""

import logging

from app.filters.base import BaseFilter, TokenPair

logger = logging.getLogger(__name__)


class BuySellRatioFilter(BaseFilter):
    """Filters tokens with unfavorable buy/sell ratios."""

    def __init__(self, min_ratio: float = 1.0):
        """
        Args:
            min_ratio: Minimum buys/sells ratio. Default 1.0 means at least
                       equal buys and sells.
        """
        self._min_ratio = min_ratio

    @property
    def name(self) -> str:
        return "BuySellRatioFilter"

    def apply(self, pairs: list[TokenPair]) -> list[TokenPair]:
        """
        Remove tokens with buy/sell ratio below the minimum.

        Tokens with no transaction data are kept (can't verify,
        scoring will penalize instead).
        Tokens with zero sells get infinite ratio — they pass.
        """
        result = []
        for token, snapshot in pairs:
            buys = snapshot.buys
            sells = snapshot.sells

            # No transaction data — let it pass, scoring penalizes
            if buys is None or sells is None:
                result.append((token, snapshot))
                continue

            # Zero sells = infinite buy pressure — passes
            if sells == 0:
                result.append((token, snapshot))
                continue

            ratio = buys / sells

            if ratio >= self._min_ratio:
                result.append((token, snapshot))

        filtered_count = len(pairs) - len(result)
        if filtered_count > 0:
            logger.debug(
                f"{self.name}: removed {filtered_count} tokens "
                f"(min_ratio={self._min_ratio:.2f})"
            )

        return result
