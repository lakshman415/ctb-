"""
Pydantic models for DexScreener API responses.

These models represent the RAW structure returned by DexScreener.
They are NOT the same as our internal schemas — a parser maps between them.

This gives us:
    - Type-safe deserialization (catches API contract changes early)
    - Clear documentation of what DexScreener actually returns
    - Decoupling from our internal domain models

Based on: https://docs.dexscreener.com/api/reference/
"""

from pydantic import BaseModel, Field


class DexBaseToken(BaseModel):
    """Token info from DexScreener pair response."""

    address: str = ""
    name: str = ""
    symbol: str = ""


class DexQuoteToken(BaseModel):
    """Quote token info (e.g., WETH, USDC)."""

    address: str = ""
    name: str = ""
    symbol: str = ""


class DexTransactions(BaseModel):
    """Buy/sell transaction counts for a time period."""

    buys: int = 0
    sells: int = 0


class DexLiquidity(BaseModel):
    """Liquidity breakdown for a pair."""

    usd: float | None = None
    base: float | None = None
    quote: float | None = None


class DexWebsite(BaseModel):
    """Website link from token info."""

    url: str = ""


class DexSocial(BaseModel):
    """Social platform link from token info."""

    platform: str = ""
    handle: str = ""


class DexInfo(BaseModel):
    """Extended token info (image, websites, socials)."""

    imageUrl: str | None = None
    websites: list[DexWebsite] = Field(default_factory=list)
    socials: list[DexSocial] = Field(default_factory=list)


class DexBoosts(BaseModel):
    """Boost activity for a pair."""

    active: int = 0


class DexPair(BaseModel):
    """
    A single pair from DexScreener API.

    This is the core data structure. Contains all market data we need:
    price, volume, transactions, liquidity, market cap, FDV, socials.

    Volume/priceChange/txns keys are time-period strings: "m5", "h1", "h6", "h24".
    """

    chainId: str = ""
    dexId: str = ""
    url: str = ""
    pairAddress: str = ""
    labels: list[str] | None = None

    baseToken: DexBaseToken = Field(default_factory=DexBaseToken)
    quoteToken: DexQuoteToken = Field(default_factory=DexQuoteToken)

    priceNative: str | None = None
    priceUsd: str | None = None

    # Keyed by time period: {"m5": {"buys": 10, "sells": 5}, "h1": {...}, ...}
    txns: dict[str, DexTransactions] = Field(default_factory=dict)

    # Keyed by time period: {"m5": 1234.56, "h1": 5678.90, ...}
    volume: dict[str, float] = Field(default_factory=dict)

    # Keyed by time period: {"m5": 0.5, "h1": -1.2, ...}
    priceChange: dict[str, float] = Field(default_factory=dict)

    liquidity: DexLiquidity | None = None
    fdv: float | None = None
    marketCap: float | None = None
    pairCreatedAt: int | None = None  # Unix timestamp in milliseconds

    info: DexInfo | None = None
    boosts: DexBoosts | None = None


class DexSearchResponse(BaseModel):
    """Response from GET /latest/dex/search and GET /latest/dex/pairs endpoints."""

    schemaVersion: str | None = None
    pairs: list[DexPair] = Field(default_factory=list)


class DexTokenProfile(BaseModel):
    """Response item from GET /token-profiles/latest/v1."""

    url: str = ""
    chainId: str = ""
    tokenAddress: str = ""
    icon: str | None = None
    header: str | None = None
    description: str | None = None
    links: list[dict[str, str]] = Field(default_factory=list)


class DexBoostedToken(BaseModel):
    """Response item from GET /token-boosts/top/v1."""

    url: str = ""
    chainId: str = ""
    tokenAddress: str = ""
    amount: float = 0
    totalAmount: float = 0
    icon: str | None = None
    header: str | None = None
    description: str | None = None
    links: list[dict[str, str]] = Field(default_factory=list)
