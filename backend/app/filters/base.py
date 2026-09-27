"""
Abstract base filter.

Every filter implements the same interface:
    apply(pairs) -> filtered pairs

Filters operate on (TokenBase, SnapshotBase) tuples because filtering decisions
often depend on both identity data (market cap, chain, age) and time-series data
(volume, buys/sells, liquidity at scan time).

Filters are composable — the pipeline chains them in sequence.
Each filter is independently enable/disable-able via configuration.
"""

from abc import ABC, abstractmethod

from app.schemas.snapshot import SnapshotBase
from app.schemas.token import TokenBase

# Type alias for a token-snapshot pair flowing through the filter pipeline
TokenPair = tuple[TokenBase, SnapshotBase]


class BaseFilter(ABC):
    """
    Contract for all token filters.

    Subclasses implement `apply()` to remove token pairs that don't meet criteria.
    Filters should be stateless and side-effect free.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable filter name for logging and debugging."""
        ...

    @abstractmethod
    def apply(self, pairs: list[TokenPair]) -> list[TokenPair]:
        """
        Filter a list of token pairs, returning only those that pass.

        Args:
            pairs: List of (TokenBase, SnapshotBase) tuples to evaluate.

        Returns:
            Filtered subset of pairs that meet this filter's criteria.
        """
        ...
