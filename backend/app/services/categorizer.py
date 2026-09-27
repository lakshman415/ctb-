"""
Market cap categorizer.

Assigns tokens to categories (early, mid, large) based on their market cap,
and provides the appropriate filter thresholds for each category.

Why categorization matters:
    - A $200K MC token with $50K volume is healthy.
    - A $50M MC token with $50K volume is dead.
    - Each category has different minimum thresholds for volume and liquidity.
    - The scanner processes each category independently to find the best in each tier.

Usage:
    categorizer = MarketCapCategorizer(settings)
    buckets = categorizer.categorize(pairs)
    # buckets = {"early": [...], "mid": [...], "large": [...]}
"""

import logging
from dataclasses import dataclass

from app.config import Settings
from app.filters.base import TokenPair

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CategoryThresholds:
    """Thresholds for a single market cap category."""

    name: str
    mc_min: float
    mc_max: float
    min_volume: float
    min_liquidity: float


class MarketCapCategorizer:
    """
    Assigns token pairs to market cap categories and provides their thresholds.

    Categories are loaded from Settings (env vars) so they can be reconfigured
    without code changes.
    """

    def __init__(self, settings: Settings):
        """
        Build category definitions from settings.

        Args:
            settings: Application settings with MC thresholds for each tier.
        """
        self._categories = [
            CategoryThresholds(
                name="early",
                mc_min=settings.early_mc_min,
                mc_max=settings.early_mc_max,
                min_volume=settings.early_min_volume,
                min_liquidity=settings.early_min_liquidity,
            ),
            CategoryThresholds(
                name="mid",
                mc_min=settings.mid_mc_min,
                mc_max=settings.mid_mc_max,
                min_volume=settings.mid_min_volume,
                min_liquidity=settings.mid_min_liquidity,
            ),
            CategoryThresholds(
                name="large",
                mc_min=settings.large_mc_min,
                mc_max=settings.large_mc_max,
                min_volume=settings.large_min_volume,
                min_liquidity=settings.large_min_liquidity,
            ),
        ]

    @property
    def categories(self) -> list[CategoryThresholds]:
        """All configured categories."""
        return self._categories

    def categorize(self, pairs: list[TokenPair]) -> dict[str, list[TokenPair]]:
        """
        Assign each token pair to a market cap category.

        Tokens that don't fit any category (MC is None or outside all ranges)
        are placed in "uncategorized" bucket.

        Args:
            pairs: List of (TokenBase, SnapshotBase) tuples.

        Returns:
            Dictionary keyed by category name, values are lists of pairs.
        """
        buckets: dict[str, list[TokenPair]] = {cat.name: [] for cat in self._categories}
        buckets["uncategorized"] = []

        for token, snapshot in pairs:
            market_cap = token.market_cap

            if market_cap is None:
                buckets["uncategorized"].append((token, snapshot))
                continue

            placed = False
            for cat in self._categories:
                if cat.mc_min <= market_cap <= cat.mc_max:
                    buckets[cat.name].append((token, snapshot))
                    placed = True
                    break

            if not placed:
                buckets["uncategorized"].append((token, snapshot))

        # Log distribution
        for name, items in buckets.items():
            if items:
                logger.info(f"Category '{name}': {len(items)} tokens")

        return buckets

    def get_thresholds(self, category_name: str) -> CategoryThresholds | None:
        """
        Get the thresholds for a specific category by name.

        Args:
            category_name: "early", "mid", or "large".

        Returns:
            CategoryThresholds or None if not found.
        """
        for cat in self._categories:
            if cat.name == category_name:
                return cat
        return None
