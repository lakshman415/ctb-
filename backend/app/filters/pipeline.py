"""
Filter pipeline orchestrator.

Chains multiple filters in sequence, passing the output of one as input to the next.
Provides logging at each step so you can see exactly how many tokens each filter removes.

Usage:
    pipeline = FilterPipeline(filters=[
        LiquidityFilter(min_liquidity=40_000),
        VolumeFilter(min_volume=100_000),
        MarketCapFilter(mc_min=100_000, mc_max=1_000_000),
    ])
    result = pipeline.run(pairs)
"""

import logging

from app.filters.base import BaseFilter, TokenPair

logger = logging.getLogger(__name__)


class FilterPipeline:
    """
    Executes a list of filters in order, logging results at each step.

    The pipeline is itself NOT a filter (doesn't extend BaseFilter) — it's
    an orchestrator. This avoids confusion between individual filters and
    the pipeline as a whole.
    """

    def __init__(self, filters: list[BaseFilter]):
        """
        Args:
            filters: Ordered list of filters to apply sequentially.
                     Order matters — put cheap/aggressive filters first
                     to reduce work for expensive ones downstream.
        """
        self._filters = filters

    @property
    def filter_count(self) -> int:
        """Number of filters in the pipeline."""
        return len(self._filters)

    @property
    def filter_names(self) -> list[str]:
        """Names of all filters in execution order."""
        return [f.name for f in self._filters]

    def run(self, pairs: list[TokenPair]) -> list[TokenPair]:
        """
        Execute all filters in sequence.

        Logs the count before/after each filter for observability.
        Short-circuits if the list becomes empty.

        Args:
            pairs: Input token-snapshot pairs to filter.

        Returns:
            Filtered subset of pairs that passed ALL filters.
        """
        initial_count = len(pairs)
        current = pairs

        logger.info(
            f"FilterPipeline starting: {initial_count} pairs, "
            f"{self.filter_count} filters [{', '.join(self.filter_names)}]"
        )

        for filt in self._filters:
            if not current:
                logger.info(f"FilterPipeline: 0 pairs remaining, skipping {filt.name}")
                break

            before = len(current)
            current = filt.apply(current)
            after = len(current)
            removed = before - after

            if removed > 0:
                logger.info(
                    f"  {filt.name}: {before} → {after} "
                    f"(removed {removed}, {removed/before*100:.0f}%)"
                )

        final_count = len(current)
        logger.info(
            f"FilterPipeline complete: {initial_count} → {final_count} "
            f"(kept {final_count}/{initial_count})"
        )

        return current
