"""
GeckoTerminal OHLCV client.

Fetches candle history for a single pool on a given network. GeckoTerminal
indexes by *pool* address (not token) and caps each response at 1000 bars,
so history is built by walking backward with the `before_timestamp` param.

Docs: https://www.geckoterminal.com/dex-api  (public, no key, ~30 req/min)

This client is intentionally separate from BaseClient/DexScreenerClient: their
contract is fetch_pairs(chain), which does not fit candle retrieval.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from app.scalping.models import Candle

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.geckoterminal.com/api/v2"
_MAX_LIMIT = 1000  # GeckoTerminal hard cap per response
_TIMEFRAME_ROUTES = {
    # timeframe -> (path segment, aggregate value)
    "1m": ("minute", 1),
    "5m": ("minute", 5),
    "15m": ("minute", 15),
    "1h": ("hour", 1),
    "4h": ("hour", 4),
    "1d": ("day", 1),
}


class GeckoTerminalError(RuntimeError):
    """Raised when the GeckoTerminal API returns an error or malformed data."""


class GeckoTerminalClient:
    """Async client for GeckoTerminal pool OHLCV data."""

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        min_interval_seconds: float = 2.1,
        max_retries: int = 4,
        verify_ssl: bool = True,
    ) -> None:
        # Public API is ~30 req/min; ~2.1s between calls keeps us under it.
        self._min_interval = min_interval_seconds
        self._max_retries = max_retries
        self._last_request_at = 0.0
        self._client = httpx.AsyncClient(
            base_url=_BASE_URL,
            timeout=timeout,
            verify=verify_ssl,
            headers={"Accept": "application/json"},
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "GeckoTerminalClient":
        return self

    async def __aexit__(self, *_exc) -> None:
        await self.close()

    async def fetch_ohlcv(
        self,
        network: str,
        pool_address: str,
        *,
        timeframe: str = "1m",
        limit: int = _MAX_LIMIT,
        before_timestamp: int | None = None,
        currency: str = "usd",
    ) -> list[Candle]:
        """
        Fetch one page of OHLCV bars, newest first.

        Args:
            network: GeckoTerminal network id (e.g. "robinhood", "eth", "solana").
            pool_address: pool contract address.
            timeframe: one of _TIMEFRAME_ROUTES keys.
            limit: bars to request (capped at 1000).
            before_timestamp: return bars strictly before this epoch (for paging).
            currency: "usd" or "token".

        Returns:
            Candles sorted ascending by timestamp (oldest first).
        """
        if timeframe not in _TIMEFRAME_ROUTES:
            raise ValueError(
                f"Unsupported timeframe {timeframe!r}; "
                f"choose from {sorted(_TIMEFRAME_ROUTES)}"
            )

        segment, aggregate = _TIMEFRAME_ROUTES[timeframe]
        params: dict[str, str | int] = {
            "aggregate": aggregate,
            "limit": min(limit, _MAX_LIMIT),
            "currency": currency,
        }
        if before_timestamp is not None:
            params["before_timestamp"] = before_timestamp

        path = f"/networks/{network}/pools/{pool_address}/ohlcv/{segment}"
        payload = await self._get(path, params)

        try:
            rows = payload["data"]["attributes"]["ohlcv_list"]
        except (KeyError, TypeError) as exc:
            raise GeckoTerminalError(
                f"Unexpected OHLCV payload shape for {network}/{pool_address}"
            ) from exc

        candles = [Candle.from_geckoterminal_row(r) for r in rows]
        candles.sort(key=lambda c: c.ts)
        return candles

    async def fetch_ohlcv_history(
        self,
        network: str,
        pool_address: str,
        *,
        timeframe: str = "1m",
        max_bars: int = 6000,
        currency: str = "usd",
    ) -> list[Candle]:
        """
        Page backward to assemble up to `max_bars` of history.

        Stops when the API returns no more bars or the target is reached.
        Returns candles ascending by timestamp, de-duplicated.
        """
        collected: dict[int, Candle] = {}
        before: int | None = None

        while len(collected) < max_bars:
            page = await self.fetch_ohlcv(
                network,
                pool_address,
                timeframe=timeframe,
                limit=_MAX_LIMIT,
                before_timestamp=before,
                currency=currency,
            )
            if not page:
                break

            new = {c.ts: c for c in page if c.ts not in collected}
            if not new:
                # No forward progress -> we've reached the start of history.
                break
            collected.update(new)

            oldest_ts = min(c.ts for c in page)
            if before is not None and oldest_ts >= before:
                break
            before = oldest_ts

            logger.info(
                "geckoterminal history: %s bars so far (oldest=%s)",
                len(collected),
                oldest_ts,
            )

        candles = sorted(collected.values(), key=lambda c: c.ts)
        return candles[-max_bars:]

    async def _get(self, path: str, params: dict) -> dict:
        """GET with simple client-side rate limiting and retry/backoff."""
        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            await self._respect_rate_limit()
            try:
                resp = await self._client.get(path, params=params)
                if resp.status_code == 429:
                    wait = min(2 ** attempt, 30)
                    logger.warning("geckoterminal 429, backing off %ss", wait)
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPError, ValueError) as exc:  # ValueError = bad JSON
                last_exc = exc
                wait = min(2 ** attempt, 30)
                logger.warning(
                    "geckoterminal request failed (attempt %s/%s): %s; retrying in %ss",
                    attempt,
                    self._max_retries,
                    exc,
                    wait,
                )
                await asyncio.sleep(wait)

        raise GeckoTerminalError(
            f"GET {path} failed after {self._max_retries} attempts"
        ) from last_exc

    async def _respect_rate_limit(self) -> None:
        loop = asyncio.get_event_loop()
        now = loop.time()
        elapsed = now - self._last_request_at
        if elapsed < self._min_interval:
            await asyncio.sleep(self._min_interval - elapsed)
        self._last_request_at = asyncio.get_event_loop().time()
