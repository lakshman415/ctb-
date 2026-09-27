"""
Pydantic schemas for Snapshot data.

SnapshotBase: core market data fields.
SnapshotResponse: what the API returns (includes id and token_id).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SnapshotBase(BaseModel):
    """Core snapshot fields — a single point-in-time market reading."""

    price: float
    volume_5m: float | None = None
    volume_1h: float | None = None
    volume_6h: float | None = None
    volume_24h: float | None = None
    buys: int | None = None
    sells: int | None = None
    price_change_5m: float | None = None
    price_change_1h: float | None = None
    price_change_6h: float | None = None
    price_change_24h: float | None = None
    liquidity: float | None = None


class SnapshotResponse(SnapshotBase):
    """Snapshot data returned from the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    token_id: int
    timestamp: datetime
