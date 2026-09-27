"""
Pydantic schemas for Token data.

TokenBase: shared fields used for both input and output.
TokenResponse: what the API returns to clients.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TokenBase(BaseModel):
    """Core token fields shared across schemas."""

    pair_address: str
    token_address: str
    name: str
    symbol: str
    chain: str
    price: float | None = None
    market_cap: float | None = None
    fdv: float | None = None
    liquidity: float | None = None
    pair_created_at: datetime | None = None
    website: str | None = None
    twitter: str | None = None
    telegram: str | None = None


class TokenResponse(TokenBase):
    """Token data returned from the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
