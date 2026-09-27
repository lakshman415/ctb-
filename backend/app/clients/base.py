"""
Abstract base class for external API clients.

All external data sources (DexScreener, CoinGecko, etc.) implement this interface.
This ensures consistent error handling, retry logic, and testability across clients.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseClient(ABC):
    """
    Contract for external API clients.

    Subclasses must implement:
        - fetch_pairs(chain): retrieve raw pair data for a chain.
        - close(): clean up resources (HTTP connections, etc.).
    """

    @abstractmethod
    async def fetch_pairs(self, chain: str) -> list[dict[str, Any]]:
        """
        Fetch raw token pair data for a given chain.

        Args:
            chain: Chain identifier (e.g., "solana", "ethereum").

        Returns:
            List of raw pair dictionaries from the external API.

        Raises:
            ExternalAPIError: If the API call fails.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Release any held resources (e.g., HTTP client connections)."""
        ...
