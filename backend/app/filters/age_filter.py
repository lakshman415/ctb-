"""
Age filter.

Removes tokens that are too new (potential rug pulls) or too old
(missed the opportunity window).

Why age matters:
    - Tokens < 1 hour old are extremely high risk (rug pulls, honeypots)
    - Tokens > 30 days old in the "early" category have likely already played out
    - Sweet spot for scalping is typically 1 hour to 7 days old
"""

import logging
from datetime import UTC, datetime, timedelta

from app.filters.base import BaseFilter, TokenPair

logger = logging.getLogger(__name__)


class AgeFilter(BaseFilter):
    """Filters tokens outside an acceptable age window."""

    def __init__(
        self,
        min_age: timedelta | None = None,
        max_age: timedelta | None = None,
    ):
        """
        Args:
            min_age: Minimum token age (pair creation time). None = no minimum.
            max_age: Maximum token age. None = no maximum.
        """
        self._min_age = min_age
        self._max_age = max_age

    @property
    def name(self) -> str:
        return "AgeFilter"

    def apply(self, pairs: list[TokenPair]) -> list[TokenPair]:
        """
        Remove tokens outside the acceptable age range.

        Tokens with no pair_created_at are kept (we can't verify, so we let
        downstream scoring penalize them for missing data instead of dropping).
        """
        now = datetime.now(tz=UTC)
        result = []

        for token, snapshot in pairs:
            # No creation time — let it pass, scoring will penalize
            if token.pair_created_at is None:
                result.append((token, snapshot))
                continue

            age = now - token.pair_created_at

            # Too new
            if self._min_age is not None and age < self._min_age:
                continue

            # Too old
            if self._max_age is not None and age > self._max_age:
                continue

            result.append((token, snapshot))

        filtered_count = len(pairs) - len(result)
        if filtered_count > 0:
            min_str = str(self._min_age) if self._min_age else "none"
            max_str = str(self._max_age) if self._max_age else "none"
            logger.debug(
                f"{self.name}: removed {filtered_count} tokens "
                f"(age range: {min_str} – {max_str})"
            )

        return result
