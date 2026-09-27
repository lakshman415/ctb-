"""
Request/response schemas for watchlists, watchlist items, and alerts.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ─── Alerts ────────────────────────────────────────────────

class AlertCreate(BaseModel):
    watchlist_id: int  # WatchlistItem id
    metric: str        # market_cap | price | volume_24h | liquidity | price_change_1h
    condition: str     # above | below
    threshold: float


class AlertResponse(BaseModel):
    id: int
    metric: str
    condition: str
    threshold: float
    enabled: bool
    triggered: bool
    triggered_at: datetime | None
    triggered_value: float | None

    model_config = ConfigDict(from_attributes=True)


# ─── Watchlist items ───────────────────────────────────────

class WatchlistItemCreate(BaseModel):
    chain: str
    token_address: str
    pair_address: str
    symbol: str
    name: str
    watchlist_id: int | None = None  # Defaults to the first list when omitted
    added_price: float | None = None
    added_market_cap: float | None = None
    note: str | None = None


class WatchlistItemResponse(BaseModel):
    id: int
    watchlist_id: int | None
    chain: str
    token_address: str
    pair_address: str
    symbol: str
    name: str
    added_price: float | None
    added_market_cap: float | None
    note: str | None
    position: int
    created_at: datetime
    alerts: list[AlertResponse]

    model_config = ConfigDict(from_attributes=True)


# ─── Watchlists (the lists themselves) ─────────────────────

class WatchlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class WatchlistRename(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class WatchlistReorder(BaseModel):
    """Ordered watchlist ids — index in the array becomes the stored position."""

    ids: list[int]


class WatchlistResponse(BaseModel):
    id: int
    name: str
    position: int
    created_at: datetime
    item_count: int

    model_config = ConfigDict(from_attributes=True)


# ─── Live quotes ───────────────────────────────────────────

class WatchlistTokenQuote(BaseModel):
    """A watchlist item enriched with current market data."""

    item_id: int
    watchlist_id: int | None
    chain: str
    token_address: str
    pair_address: str
    symbol: str
    name: str

    # Live metrics — null when the pair lookup failed
    price: float | None
    market_cap: float | None
    volume_24h: float | None
    liquidity: float | None
    age_hours: float | None
    price_change_5m: float | None
    price_change_1h: float | None
    price_change_24h: float | None

    # Snapshot from when the token was added
    added_price: float | None
    added_market_cap: float | None

    note: str | None
    position: int
    created_at: datetime
    alert_count: int
    is_stale: bool  # True when live data could not be fetched
