"""
Volume filter.

Removes tokens that don't meet the minimum 24h volume threshold.

Why volume matters:
    - Low volume = can't enter/exit positions without moving the price
    - Volume confirms that price action is backed by real trading activity
    - Dead volume tokens can be manipulated with small trades
"""

import logging

from app.filters.base import BaseFilter, TokenPair

logger = logging.getLogger(__name__)


class VolumeFilter(BaseFilter):
    """Filters tokens below minimum 24h volume."""

    def __init__(self, min_volume: float):
        """
        Args:
            min_volume: Minimum 24h volume in USD.
        """
        self._min_volume = min_volume

    @property
    def name(self) -> str:
        return "VolumeFilter"

    def apply(self, pairs: list[TokenPair]) -> list[TokenPair]:
        """
        Remove tokens with 24h volume below the minimum.

        Falls back to 6h volume if 24h is unavailable.
        Tokens with no volume data at all are removed.
        """
        result = []
        for token, snapshot in pairs:
            # Prefer 24h volume, fall back to 6h
            volume = snapshot.volume_24h
            if volume is None:
                volume = snapshot.volume_6h

            # No volume data — skip
            if volume is None:
                continue

            if volume >= self._min_volume:
                result.append((token, snapshot))

        filtered_count = len(pairs) - len(result)
        if filtered_count > 0:
            logger.debug(
                f"{self.name}: removed {filtered_count} tokens "
                f"(min_volume=${self._min_volume:,.0f})"
            )

        return result
