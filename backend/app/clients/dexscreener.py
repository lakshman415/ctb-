"""
DexScreener API client.

Wraps the DexScreener public API with:
    - Async HTTP via httpx
    - Rate-limit awareness (respects 300 req/min for pair endpoints, 60 req/min for others)
    - Retry logic with exponential backoff for transient failures
    - Structured error handling via ExternalAPIError
    - Type-safe response parsing via Pydantic models

Business logic does NOT belong here. This is purely data fetching + parsing.

API docs: https://docs.dexscreener.com/api/reference/
"""

import asyncio
import logging
from typing import Any

import httpx

from app.clients.base import BaseClient
from app.clients.dexscreener_models import (
    DexBoostedToken,
    DexPair,
    DexSearchResponse,
    DexTokenProfile,
)
from app.core.exceptions import ExternalAPIError

logger = logging.getLogger(__name__)

# Rate limits from DexScreener docs
_RATE_LIMIT_SEARCH = 300  # requests/minute for search and pair endpoints
_RATE_LIMIT_OTHER = 60  # requests/minute for profiles, boosts, etc.

# Retry configuration
_MAX_RETRIES = 3
_RETRY_BACKOFF_BASE = 1.0  # seconds, doubles each retry


class DexScreenerClient(BaseClient):
    """
    Async HTTP client for DexScreener's public REST API.

    Provides methods for each endpoint we use:
        - search_pairs: discover tokens by search query
        - get_token_pairs: get all pairs for a token on a chain
        - get_boosted_tokens: find tokens with active boosts (momentum signal)
        - get_latest_profiles: recently listed token profiles

    Usage:
        client = DexScreenerClient(base_url="https://api.dexscreener.com")
        pairs = await client.fetch_pairs("solana")
        await client.close()
    """

    def __init__(self, base_url: str, timeout: float = 30.0, verify_ssl: bool = True):
        """
        Initialize the DexScreener client.

        Args:
            base_url: DexScreener API base URL (e.g., "https://api.dexscreener.com").
            timeout: HTTP request timeout in seconds.
            verify_ssl: Whether to verify SSL certificates. Set False for corporate proxies.
        """
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            verify=verify_ssl,
            headers={
                "Accept": "application/json",
                "User-Agent": "CTB-Scanner/0.1.0",
            },
        )

    async def fetch_pairs(self, chain: str) -> list[dict[str, Any]]:
        """
        Fetch token pairs for a specific chain using multiple strategies.

        Combines several data sources to build a broad list:
        1. Boosted tokens (tokens with active promotion = momentum)
        2. Latest token profiles (newly listed/updated tokens)
        3. Search by chain name (general discovery)
        4. Search by popular quote tokens on that chain

        Returns raw dictionaries for the BaseClient interface contract.

        Args:
            chain: Chain identifier (e.g., "solana", "ethereum", "base").

        Returns:
            List of raw pair dictionaries from DexScreener.

        Raises:
            ExternalAPIError: On network errors or non-2xx responses.
        """
        all_pairs: list[DexPair] = []
        seen_addresses: set[str] = set()

        def _add_pair(pair: DexPair) -> None:
            if pair.pairAddress and pair.pairAddress not in seen_addresses:
                all_pairs.append(pair)
                seen_addresses.add(pair.pairAddress)

        # Strategy 1: Get boosted tokens and find their pairs on this chain
        try:
            boosted = await self.get_boosted_tokens()
            chain_boosted = [b for b in boosted if b.chainId == chain]
            for token in chain_boosted[:15]:
                try:
                    pairs = await self.get_token_pairs(chain, token.tokenAddress)
                    for pair in pairs[:3]:  # Top 3 pools per token
                        _add_pair(pair)
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Boosted tokens fetch failed for {chain}: {e}")

        # Strategy 2: Latest token profiles on this chain
        try:
            profiles = await self.get_latest_profiles()
            chain_profiles = [p for p in profiles if p.chainId == chain]
            for profile in chain_profiles[:15]:
                try:
                    pairs = await self.get_token_pairs(chain, profile.tokenAddress)
                    for pair in pairs[:2]:
                        _add_pair(pair)
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Latest profiles fetch failed for {chain}: {e}")

        # Strategy 3: Search by chain name
        try:
            search_results = await self.search_pairs(query=chain)
            for pair in search_results:
                if pair.chainId == chain:
                    _add_pair(pair)
        except Exception as e:
            logger.debug(f"Search by chain failed for {chain}: {e}")

        # Strategy 4: Search by popular trading terms for more diversity
        search_terms = {
            "solana": ["SOL", "pump", "meme sol"],
            "ethereum": ["ETH", "pepe", "meme eth"],
            "bsc": ["BNB", "pancakeswap", "meme bnb"],
            "base": ["BASE", "degen base", "meme base"],
            "robinhood": ["robinhood", "uniswap robinhood", "meme robinhood"],
        }
        for term in search_terms.get(chain, [chain])[:2]:
            try:
                results = await self.search_pairs(query=term)
                for pair in results:
                    if pair.chainId == chain:
                        _add_pair(pair)
            except Exception:
                continue

        logger.info(f"fetch_pairs({chain}): {len(all_pairs)} unique pairs from all strategies")
        return [pair.model_dump() for pair in all_pairs]

    async def search_pairs(self, query: str) -> list[DexPair]:
        """
        Search for pairs matching a query string.

        Rate limit: 300 requests/minute.
        Endpoint: GET /latest/dex/search?q={query}

        Args:
            query: Search string (token name, symbol, address, or chain).

        Returns:
            List of DexPair objects matching the query.

        Raises:
            ExternalAPIError: On request failure.
        """
        data = await self._request("GET", "/latest/dex/search", params={"q": query})

        response = DexSearchResponse.model_validate(data)
        logger.debug(f"Search '{query}' returned {len(response.pairs)} pairs")
        return response.pairs

    async def get_pairs_by_chain_and_address(
        self, chain: str, pair_address: str
    ) -> list[DexPair]:
        """
        Get a specific pair by chain and pair address.

        Rate limit: 300 requests/minute.
        Endpoint: GET /latest/dex/pairs/{chainId}/{pairId}

        Args:
            chain: Chain identifier.
            pair_address: The pair contract address.

        Returns:
            List of DexPair objects (usually 1).

        Raises:
            ExternalAPIError: On request failure.
        """
        data = await self._request(
            "GET", f"/latest/dex/pairs/{chain}/{pair_address}"
        )

        response = DexSearchResponse.model_validate(data)
        return response.pairs

    async def get_token_pairs(self, chain: str, token_address: str) -> list[DexPair]:
        """
        Get all pools/pairs for a specific token on a chain.

        Rate limit: 300 requests/minute.
        Endpoint: GET /token-pairs/v1/{chainId}/{tokenAddress}

        Args:
            chain: Chain identifier.
            token_address: The token contract address.

        Returns:
            List of DexPair objects for this token.

        Raises:
            ExternalAPIError: On request failure.
        """
        data = await self._request(
            "GET", f"/token-pairs/v1/{chain}/{token_address}"
        )

        # This endpoint returns a list directly, not wrapped in {pairs: [...]}
        if isinstance(data, list):
            pairs = [DexPair.model_validate(item) for item in data]
        else:
            pairs = []

        logger.debug(
            f"Token pairs for {token_address} on {chain}: {len(pairs)} pairs"
        )
        return pairs

    async def get_pairs_by_token_addresses(
        self, chain: str, token_addresses: list[str]
    ) -> list[DexPair]:
        """
        Get pools for up to 30 token addresses in a single request.

        Preferred over pair-address lookups when only the token address is known
        to be reliable — a token may have several pools, and a stored pair
        address can be stale or wrong.

        Rate limit: 300 requests/minute.
        Endpoint: GET /tokens/v1/{chainId}/{tokenAddresses}

        Args:
            chain: Chain identifier.
            token_addresses: Token contract addresses (max 30 per call).

        Returns:
            List of DexPair objects across all requested tokens.

        Raises:
            ExternalAPIError: On request failure.
        """
        if not token_addresses:
            return []

        data = await self._request(
            "GET", f"/tokens/v1/{chain}/{','.join(token_addresses)}"
        )

        # This endpoint returns a bare list, not {pairs: [...]}
        if isinstance(data, list):
            pairs = [DexPair.model_validate(item) for item in data]
        elif isinstance(data, dict):
            pairs = [DexPair.model_validate(p) for p in data.get("pairs", [])]
        else:
            pairs = []

        logger.debug(
            f"Batch token lookup on {chain}: {len(token_addresses)} tokens → {len(pairs)} pairs"
        )
        return pairs

    async def get_boosted_tokens(self) -> list[DexBoostedToken]:
        """
        Get tokens with the most active boosts (momentum/trending signal).

        Rate limit: 60 requests/minute.
        Endpoint: GET /token-boosts/top/v1

        Returns:
            List of DexBoostedToken objects sorted by boost amount.

        Raises:
            ExternalAPIError: On request failure.
        """
        data = await self._request("GET", "/token-boosts/top/v1")

        if isinstance(data, list):
            tokens = [DexBoostedToken.model_validate(item) for item in data]
        else:
            tokens = []

        logger.debug(f"Boosted tokens: {len(tokens)} tokens")
        return tokens

    async def get_latest_profiles(self) -> list[DexTokenProfile]:
        """
        Get the latest token profiles (recently listed/updated tokens).

        Rate limit: 60 requests/minute.
        Endpoint: GET /token-profiles/latest/v1

        Returns:
            List of DexTokenProfile objects.

        Raises:
            ExternalAPIError: On request failure.
        """
        data = await self._request("GET", "/token-profiles/latest/v1")

        if isinstance(data, list):
            profiles = [DexTokenProfile.model_validate(item) for item in data]
        else:
            profiles = []

        logger.debug(f"Latest profiles: {len(profiles)} tokens")
        return profiles

    async def close(self) -> None:
        """Close the underlying HTTP client and release connections."""
        await self._client.aclose()
        logger.debug("DexScreener HTTP client closed")

    # ─── Private Methods ────────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
    ) -> Any:
        """
        Execute an HTTP request with retry logic and error handling.

        Retries on:
            - 429 (rate limited) — waits before retrying
            - 5xx (server errors) — exponential backoff
            - Network timeouts

        Args:
            method: HTTP method (GET, POST, etc.).
            path: API path (e.g., "/latest/dex/search").
            params: Optional query parameters.

        Returns:
            Parsed JSON response body.

        Raises:
            ExternalAPIError: After all retries exhausted or on 4xx client errors.
        """
        last_exception: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                response = await self._client.request(
                    method=method,
                    url=path,
                    params=params,
                )

                # Rate limited — wait and retry
                if response.status_code == 429:
                    wait_time = _RETRY_BACKOFF_BASE * (2**attempt)
                    logger.warning(
                        f"Rate limited by DexScreener. "
                        f"Waiting {wait_time:.1f}s (attempt {attempt + 1}/{_MAX_RETRIES})"
                    )
                    await asyncio.sleep(wait_time)
                    continue

                # Server error — retry with backoff
                if response.status_code >= 500:
                    wait_time = _RETRY_BACKOFF_BASE * (2**attempt)
                    logger.warning(
                        f"DexScreener server error {response.status_code}. "
                        f"Retrying in {wait_time:.1f}s (attempt {attempt + 1}/{_MAX_RETRIES})"
                    )
                    await asyncio.sleep(wait_time)
                    continue

                # Client error (4xx except 429) — don't retry, it's our fault
                if response.status_code >= 400:
                    raise ExternalAPIError(
                        source="DexScreener",
                        message=(
                            f"Client error {response.status_code} on {method} {path}: "
                            f"{response.text[:200]}"
                        ),
                    )

                # Success
                return response.json()

            except httpx.TimeoutException as e:
                wait_time = _RETRY_BACKOFF_BASE * (2**attempt)
                logger.warning(
                    f"DexScreener timeout on {method} {path}. "
                    f"Retrying in {wait_time:.1f}s (attempt {attempt + 1}/{_MAX_RETRIES})"
                )
                last_exception = e
                await asyncio.sleep(wait_time)

            except httpx.RequestError as e:
                wait_time = _RETRY_BACKOFF_BASE * (2**attempt)
                logger.warning(
                    f"DexScreener request error on {method} {path}: {e}. "
                    f"Retrying in {wait_time:.1f}s (attempt {attempt + 1}/{_MAX_RETRIES})"
                )
                last_exception = e
                await asyncio.sleep(wait_time)

            except ExternalAPIError:
                # Re-raise client errors immediately (no retry)
                raise

        # All retries exhausted
        raise ExternalAPIError(
            source="DexScreener",
            message=f"All {_MAX_RETRIES} retries exhausted for {method} {path}. "
            f"Last error: {last_exception}",
        )
