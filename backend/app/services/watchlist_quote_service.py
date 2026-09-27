"""
Live quotes for watchlist tokens.

The watchlist stores a snapshot from when a token was added. To show current
market cap, volume, age, and price changes, fresh data has to be pulled on read.

Lookups go by token address rather than the stored pair address: a token can
have several pools, and a stored pair address may be stale or plain wrong (items
added from trending data sometimes carry the token address in that field). The
highest-liquidity pool wins, matching how the scanner picks a canonical pool.

Requests are batched: DexScreener's token endpoint accepts up to 30
comma-separated addresses, so a 60-token watchlist costs 2 calls per chain.
"""

import asyncio
import logging
from datetime import UTC, datetime

from app.clients.dexscreener import DexScreenerClient
from app.clients.dexscreener_models import DexPair
from app.core.chains import to_canonical
from app.models.watchlist import WatchlistItem
from app.schemas.watchlist import WatchlistTokenQuote

logger = logging.getLogger(__name__)

# DexScreener caps the token endpoint at 30 addresses per request
BATCH_SIZE = 30


class WatchlistQuoteService:
    """Fetches current market data for watchlist items."""

    def __init__(self, client: DexScreenerClient):
        self._client = client

    async def quote_items(self, items: list[WatchlistItem]) -> list[WatchlistTokenQuote]:
        """
        Build a live quote for each watchlist item, preserving input order.

        Items whose token can't be resolved still come back — with null metrics
        and their stored snapshot intact — so tokens never vanish from the table
        just because an upstream lookup failed.
        """
        if not items:
            return []

        best_pools = await self._resolve_best_pools(items)
        return [
            self._to_quote(item, best_pools.get(self._key(item.chain, item.token_address)))
            for item in items
        ]

    @staticmethod
    def _key(chain: str, token_address: str) -> str:
        # Canonical form: rows saved before chain normalization may hold a short
        # slug like "sol", which DexScreener rejects outright.
        return f"{to_canonical(chain)}:{token_address.lower()}"

    async def _resolve_best_pools(self, items: list[WatchlistItem]) -> dict[str, DexPair]:
        """
        Fetch pools for every item and keep the deepest one per token.

        Returns a map of "chain:token_address" -> best DexPair.
        """
        # Group token addresses by chain — the endpoint is chain-scoped
        by_chain: dict[str, list[str]] = {}
        for item in items:
            if not item.token_address:
                continue
            addresses = by_chain.setdefault(to_canonical(item.chain), [])
            if item.token_address not in addresses:
                addresses.append(item.token_address)

        batches: list[tuple[str, list[str]]] = []
        for chain, addresses in by_chain.items():
            for i in range(0, len(addresses), BATCH_SIZE):
                batches.append((chain, addresses[i : i + BATCH_SIZE]))

        results = await asyncio.gather(
            *(
                self._client.get_pairs_by_token_addresses(chain, addrs)
                for chain, addrs in batches
            ),
            return_exceptions=True,
        )

        best: dict[str, DexPair] = {}
        for (chain, _), outcome in zip(batches, results, strict=True):
            if isinstance(outcome, BaseException):
                logger.warning(f"Watchlist quote batch failed for {chain}: {outcome}")
                continue

            for pair in outcome:
                token_address = pair.baseToken.address
                if not token_address:
                    continue

                key = self._key(pair.chainId or chain, token_address)
                incumbent = best.get(key)
                if incumbent is None or self._liquidity(pair) > self._liquidity(incumbent):
                    best[key] = pair

        return best

    @staticmethod
    def _liquidity(pair: DexPair) -> float:
        return (pair.liquidity.usd or 0.0) if pair.liquidity else 0.0

    @classmethod
    def _to_quote(cls, item: WatchlistItem, pair: DexPair | None) -> WatchlistTokenQuote:
        """Map a watchlist item plus its live pair into the response schema."""
        age_hours: float | None = None
        price: float | None = None

        if pair is not None:
            if pair.pairCreatedAt:
                created = datetime.fromtimestamp(pair.pairCreatedAt / 1000, tz=UTC)
                age_hours = (datetime.now(tz=UTC) - created).total_seconds() / 3600
            if pair.priceUsd:
                try:
                    price = float(pair.priceUsd)
                except ValueError:
                    price = None

        return WatchlistTokenQuote(
            item_id=item.id,
            watchlist_id=item.watchlist_id,
            chain=item.chain,
            token_address=item.token_address,
            # Report the resolved pool so the UI links to a real pair
            pair_address=(pair.pairAddress if pair and pair.pairAddress else item.pair_address),
            # Prefer the live symbol/name — tokens occasionally rename after listing
            symbol=(pair.baseToken.symbol if pair and pair.baseToken.symbol else item.symbol),
            name=(pair.baseToken.name if pair and pair.baseToken.name else item.name),
            price=price,
            # DexScreener omits marketCap on some pairs but still reports fdv;
            # for memecoins with no locked supply the two are equivalent.
            market_cap=(pair.marketCap or pair.fdv) if pair else None,
            volume_24h=(pair.volume.get("h24") if pair else None),
            liquidity=cls._liquidity(pair) if pair else None,
            age_hours=age_hours,
            price_change_5m=(pair.priceChange.get("m5") if pair else None),
            price_change_1h=(pair.priceChange.get("h1") if pair else None),
            price_change_24h=(pair.priceChange.get("h24") if pair else None),
            added_price=item.added_price,
            added_market_cap=item.added_market_cap,
            note=item.note,
            position=item.position,
            created_at=item.created_at,
            alert_count=len([a for a in item.alerts if a.enabled]),
            is_stale=pair is None,
        )
