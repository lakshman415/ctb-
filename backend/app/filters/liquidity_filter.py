"""
Liquidity filter.

Removes tokens that don't meet the minimum liquidity threshold.

Why liquidity matters:
    - Low liquidity = high slippage when entering/exiting positions
    - Tokens with <$40K liquidity are nearly untradeable for scalping
    - Liquidity is the strongest signal of whether a token is "real"
"""

import logging

from app.filters.base import BaseFilter, TokenPair

logger = logging.getLogger(__name__)


class LiquidityFilter(BaseFilter):
    """Filters tokens below a minimum USD liquidity threshold."""

    def __init__(self, min_liquidity: float):
        """
        Args:
            min_liquidity: Minimum USD liquidity required to pass.
        """
        self._min_liquidity = min_liquidity

    @property
    def name(self) -> str:
        return "LiquidityFilter"

    def apply(self, pairs: list[TokenPair]) -> list[TokenPair]:
        """
        Remove tokens with liquidity below the configured minimum.

        Tokens with None liquidity are also removed (no data = no confidence).
        """
        result = []
        for token, snapshot in pairs:
            liquidity = snapshot.liquidity

            # No liquidity data — can't verify, skip
            if liquidity is None:
                continue

            if liquidity >= self._min_liquidity:
                result.append((token, snapshot))

        filtered_count = len(pairs) - len(result)
        if filtered_count > 0:
            logger.debug(
                f"{self.name}: removed {filtered_count} tokens "
                f"(min_liquidity=${self._min_liquidity:,.0f})"
            )

        return result
