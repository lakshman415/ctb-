"""
Pydantic schemas for scanner / dashboard responses.

RankedTokenResponse: a single row in the dashboard table.
ScannerResultResponse: the full scanner output with metadata.
"""

from datetime import datetime

from pydantic import BaseModel


class RankedTokenResponse(BaseModel):
    """A single ranked token for the dashboard."""

    rank: int
    score: float
    score_reasons: list[str]
    category: str  # "early", "mid", "large"
    chain: str
    name: str
    symbol: str
    pair_address: str
    token_address: str
    price: float | None = None
    market_cap: float | None = None
    liquidity: float | None = None
    volume_24h: float | None = None
    buys: int | None = None
    sells: int | None = None
    buy_sell_ratio: float | None = None
    price_change_5m: float | None = None
    price_change_1h: float | None = None
    price_change_24h: float | None = None
    liquidity_mcap_ratio: float | None = None


class ScannerResultResponse(BaseModel):
    """Full scanner output returned by the /scanner endpoint."""

    scanned_at: datetime
    total_pairs_fetched: int
    total_after_filter: int
    tokens: list[RankedTokenResponse]
