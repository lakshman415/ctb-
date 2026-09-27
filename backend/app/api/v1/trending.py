"""
Trending tokens endpoint.

Returns top tokens from GMGN (if API key configured) or falls back to
our own scoring engine with strict quality thresholds.
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Query

from app.config import get_settings
from app.core.chains import to_canonical
from app.schemas.scanner import RankedTokenResponse, ScannerResultResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trending", tags=["trending"])


@router.get("/top", response_model=ScannerResultResponse)
async def get_trending_tokens(
    chain: str = Query(default="all", description="Chain filter: all, solana, ethereum, bsc, base, robinhood"),
    limit: int = Query(default=10, ge=1, le=50),
    interval: str = Query(default="24h", description="Time interval: 5m, 30m, 1h, 6h, 24h"),
) -> ScannerResultResponse:
    """
    Get top trending tokens across all chains.

    Uses GMGN data if API key is configured, otherwise falls back to
    our own scoring engine with strict quality filters:
        - Market Cap: $500K–$10M
        - Liquidity >= $30K
        - Volume 24h >= $100K
        - Buy/Sell Ratio >= 1.0
        - Liquidity/MCap >= 2%
        - Minimum transactions (buys+sells) >= 100
    """
    settings = get_settings()

    # Try GMGN first if API key is available
    gmgn_key = getattr(settings, "gmgn_api_key", None)
    if gmgn_key:
        tokens = await _fetch_from_gmgn(gmgn_key, chain, limit, settings, interval)
        if tokens:
            return ScannerResultResponse(
                scanned_at=datetime.now(tz=UTC),
                total_pairs_fetched=len(tokens),
                total_after_filter=len(tokens),
                tokens=tokens,
            )

    # Fallback: use our own scored data with traction filters
    from app.scheduler.jobs import get_all_scanned_tokens

    result = get_all_scanned_tokens()
    if result is None:
        return ScannerResultResponse(
            scanned_at=datetime.now(tz=UTC),
            total_pairs_fetched=0,
            total_after_filter=0,
            tokens=[],
        )

    # Apply traction filter: $500K-$10M MCap with real activity
    quality_tokens = [
        t for t in result.tokens
        if (t.market_cap is not None and 500_000 <= t.market_cap <= 10_000_000)
        and (t.liquidity is not None and t.liquidity >= 30_000)
        and (t.volume_24h is not None and t.volume_24h >= 100_000)
        and (t.buy_sell_ratio is None or t.buy_sell_ratio >= 1.0)
        and (t.liquidity_mcap_ratio is None or t.liquidity_mcap_ratio >= 0.02)
        and ((t.buys or 0) + (t.sells or 0) >= 100)
    ]

    # Filter by chain if specified
    if chain != "all":
        quality_tokens = [t for t in quality_tokens if t.chain == chain]

    # Take top N by score
    quality_tokens = quality_tokens[:limit]

    # Re-assign ranks
    for i, t in enumerate(quality_tokens, 1):
        t.rank = i

    return ScannerResultResponse(
        scanned_at=result.scanned_at,
        total_pairs_fetched=result.total_pairs_fetched,
        total_after_filter=len(quality_tokens),
        tokens=quality_tokens,
    )


async def _fetch_from_gmgn(
    api_key: str, chain: str, limit: int, settings, interval: str = "24h"
) -> list[RankedTokenResponse]:
    """
    Fetch trending from GMGN and convert to our response format.

    Chain ids are normalized to the canonical form on the way out — GMGN's short
    slugs ("sol", "eth") are rejected by DexScreener and would produce dead
    chart links and unresolvable watchlist entries.
    """
    from app.clients.gmgn import GMGNClient

    client = GMGNClient(api_key=api_key)

    chains = (
        ["solana", "ethereum", "bsc", "base", "robinhood"]
        if chain == "all"
        else [to_canonical(chain)]
    )
    all_tokens: list[RankedTokenResponse] = []

    for ch in chains:
        gmgn_tokens = client.get_trending(chain=ch, interval=interval, limit=limit)
        for t in gmgn_tokens:
            # Skip honeypots
            if t.is_honeypot:
                continue

            all_tokens.append(
                RankedTokenResponse(
                    rank=0,
                    score=0,
                    score_reasons=[
                        f"Holders: {t.holder_count}",
                        f"Smart money: {t.smart_degen_count}",
                        f"Renowned: {t.renowned_count}",
                        f"Snipers: {t.sniper_count}",
                        f"Open source: {t.is_open_source}",
                        f"Renounced: {t.renounced}",
                    ],
                    category="gmgn",
                    chain=to_canonical(t.chain) or to_canonical(ch),
                    name=t.name,
                    symbol=t.symbol,
                    pair_address=t.address,
                    token_address=t.address,
                    price=t.price,
                    market_cap=t.market_cap,
                    liquidity=t.liquidity,
                    volume_24h=t.volume,
                    buys=t.buys,
                    sells=t.sells,
                    buy_sell_ratio=t.buy_sell_ratio,
                    price_change_5m=t.price_change_5m,
                    price_change_1h=t.price_change_1h,
                    price_change_24h=t.price_change_24h,
                    liquidity_mcap_ratio=round(t.liquidity / t.market_cap, 4)
                    if t.market_cap > 0 and t.liquidity > 0 else None,
                )
            )

    # Sort by volume
    all_tokens.sort(key=lambda x: x.volume_24h or 0, reverse=True)
    top = all_tokens[:limit]
    for i, t in enumerate(top, 1):
        t.rank = i

    # GMGN only gives a token address, so pair_address starts out as a copy of
    # it. Resolve the real pool so chart links work and starred tokens can be
    # quoted later.
    await _resolve_pair_addresses(top, settings)

    return top


async def _resolve_pair_addresses(tokens: list[RankedTokenResponse], settings) -> None:
    """
    Fill in real pair addresses for trending tokens, in place.

    One batched DexScreener call per chain (30 addresses each). Best-effort:
    on failure the token keeps its address-shaped placeholder rather than
    dropping out of the list.
    """
    if not tokens:
        return

    from app.clients.dexscreener import DexScreenerClient

    by_chain: dict[str, list[RankedTokenResponse]] = {}
    for t in tokens:
        if t.token_address:
            by_chain.setdefault(t.chain, []).append(t)

    client = DexScreenerClient(
        base_url=settings.dexscreener_base_url,
        verify_ssl=settings.dexscreener_verify_ssl,
    )
    resolved = 0
    try:
        for chain, group in by_chain.items():
            for i in range(0, len(group), 30):
                batch = group[i : i + 30]
                try:
                    pairs = await client.get_pairs_by_token_addresses(
                        chain, [t.token_address for t in batch]
                    )
                except Exception as e:
                    logger.warning(f"Pair resolution failed for {chain}: {e}")
                    continue

                # Deepest pool per token address wins
                best: dict[str, object] = {}
                for p in pairs:
                    addr = (p.baseToken.address or "").lower()
                    if not addr:
                        continue
                    liq = (p.liquidity.usd if p.liquidity else 0) or 0
                    incumbent = best.get(addr)
                    if incumbent is None or liq > incumbent[1]:
                        best[addr] = (p.pairAddress, liq)

                for t in batch:
                    match = best.get(t.token_address.lower())
                    if match and match[0]:
                        t.pair_address = match[0]
                        resolved += 1
    finally:
        await client.close()

    logger.info(f"Trending: resolved {resolved}/{len(tokens)} real pair addresses")
