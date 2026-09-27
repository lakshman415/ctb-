"""
Pydantic schemas for token analysis responses.

Returned by the /tokens/analyze endpoint when a user pastes a CA.
"""

from datetime import datetime

from pydantic import BaseModel


class TokenOverview(BaseModel):
    """Basic token identity and current market data."""

    pair_address: str
    token_address: str
    name: str
    symbol: str
    chain: str
    dex: str
    price: float | None = None
    market_cap: float | None = None
    fdv: float | None = None
    liquidity: float | None = None
    pair_created_at: datetime | None = None
    website: str | None = None
    twitter: str | None = None
    telegram: str | None = None
    dexscreener_url: str | None = None


class VolumeData(BaseModel):
    """Volume across time periods."""

    volume_5m: float | None = None
    volume_1h: float | None = None
    volume_6h: float | None = None
    volume_24h: float | None = None


class TransactionData(BaseModel):
    """Buy/sell activity."""

    buys: int | None = None
    sells: int | None = None
    buy_sell_ratio: float | None = None
    total_txns: int | None = None


class PriceChangeData(BaseModel):
    """Price changes across time periods."""

    change_5m: float | None = None
    change_1h: float | None = None
    change_6h: float | None = None
    change_24h: float | None = None


class TechnicalIndicators(BaseModel):
    """Computed technical analysis metrics."""

    # Momentum
    momentum_1h: str | None = None  # "bullish", "bearish", "neutral"
    momentum_24h: str | None = None

    # Liquidity health
    liquidity_mcap_ratio: float | None = None
    liquidity_grade: str | None = None  # "excellent", "good", "fair", "poor", "danger"

    # Volume analysis
    volume_to_liquidity_ratio: float | None = None
    volume_grade: str | None = None  # "very_high", "high", "moderate", "low"

    # Buy pressure
    buy_pressure_grade: str | None = None  # "strong", "moderate", "weak", "selling"

    # Age assessment
    age_hours: float | None = None
    age_grade: str | None = None  # "very_new", "new", "established", "mature"

    # Social score
    social_count: int = 0  # 0-3 (website, twitter, telegram)

    # Support/Resistance (price-based)
    support_levels: list[float] = []
    resistance_levels: list[float] = []

    # Support/Resistance (market-cap-based)
    mcap_support_levels: list[float] = []
    mcap_resistance_levels: list[float] = []

    # Trend
    trend_direction: str | None = None  # "uptrend", "downtrend", "sideways"
    trend_strength: str | None = None  # "strong", "moderate", "weak"
    trend_explanation: str | None = None

    # Volatility
    volatility_grade: str | None = None  # "extreme", "high", "moderate", "low"
    volatility_explanation: str | None = None

    # Risk/Reward
    risk_reward_rating: str | None = None  # "excellent", "good", "fair", "poor"
    risk_reward_explanation: str | None = None

    # Key signals — what a pro would notice
    key_signals: list[str] = []

    # Overall
    overall_grade: str | None = None  # "A", "B", "C", "D", "F"
    risk_level: str | None = None  # "low", "medium", "high", "extreme"
    summary: list[str] = []  # Human-readable analysis points


class TokenAnalysisResponse(BaseModel):
    """Full analysis response for a single token."""

    overview: TokenOverview
    volume: VolumeData
    transactions: TransactionData
    price_changes: PriceChangeData
    technicals: TechnicalIndicators
    score: float
    analyzed_at: datetime
