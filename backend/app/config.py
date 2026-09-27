"""
Application settings loaded from environment variables.

Uses Pydantic BaseSettings for typed, validated configuration.
All market cap thresholds, scoring weights, and chain lists are configurable
without touching code.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MarketCapCategoryConfig(BaseSettings):
    """Thresholds for a single market cap category."""

    mc_min: float
    mc_max: float
    min_volume: float
    min_liquidity: float


class Settings(BaseSettings):
    """
    Root application settings.

    Values are loaded from environment variables (and .env file in dev).
    Nested configs use prefixed env vars.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Application ---
    app_env: str = Field(default="development")
    app_debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    # --- Database ---
    database_url: str = Field(default="postgresql://ctb:ctb_secret@localhost:5432/ctb_db")

    # --- Scanner ---
    scanner_interval_seconds: int = Field(default=60)
    supported_chains: list[str] = Field(default=["solana", "ethereum", "base", "robinhood"])

    # --- DexScreener ---
    dexscreener_base_url: str = Field(default="https://api.dexscreener.com")
    dexscreener_verify_ssl: bool = Field(default=True)

    # --- GMGN (optional — trending data, set up at https://gmgn.ai/ai) ---
    gmgn_api_key: str | None = Field(default=None)

    # --- Fixed wallet addresses per chain ---
    wallet_sol: str = Field(default="")
    wallet_eth: str = Field(default="")
    wallet_bsc: str = Field(default="")
    wallet_robinhood: str = Field(default="")
    wallet_base: str = Field(default="")

    # --- Market Cap Thresholds: Early ---
    early_mc_min: float = Field(default=100_000)
    early_mc_max: float = Field(default=1_000_000)
    early_min_volume: float = Field(default=100_000)
    early_min_liquidity: float = Field(default=40_000)

    # --- Market Cap Thresholds: Mid ---
    mid_mc_min: float = Field(default=1_000_000)
    mid_mc_max: float = Field(default=10_000_000)
    mid_min_volume: float = Field(default=500_000)
    mid_min_liquidity: float = Field(default=150_000)

    # --- Market Cap Thresholds: Large ---
    large_mc_min: float = Field(default=10_000_000)
    large_mc_max: float = Field(default=300_000_000)
    large_min_volume: float = Field(default=2_000_000)
    large_min_liquidity: float = Field(default=500_000)

    # --- Scoring Weights ---
    weight_liquidity: float = Field(default=0.20)
    weight_volume: float = Field(default=0.25)
    weight_buy_pressure: float = Field(default=0.20)
    weight_token_age: float = Field(default=0.10)
    weight_social_presence: float = Field(default=0.10)
    weight_price_trend: float = Field(default=0.15)

    @property
    def early_category(self) -> MarketCapCategoryConfig:
        """Early market cap category thresholds."""
        return MarketCapCategoryConfig(
            mc_min=self.early_mc_min,
            mc_max=self.early_mc_max,
            min_volume=self.early_min_volume,
            min_liquidity=self.early_min_liquidity,
        )

    @property
    def mid_category(self) -> MarketCapCategoryConfig:
        """Mid market cap category thresholds."""
        return MarketCapCategoryConfig(
            mc_min=self.mid_mc_min,
            mc_max=self.mid_mc_max,
            min_volume=self.mid_min_volume,
            min_liquidity=self.mid_min_liquidity,
        )

    @property
    def large_category(self) -> MarketCapCategoryConfig:
        """Large market cap category thresholds."""
        return MarketCapCategoryConfig(
            mc_min=self.large_mc_min,
            mc_max=self.large_mc_max,
            min_volume=self.large_min_volume,
            min_liquidity=self.large_min_liquidity,
        )

    @property
    def scoring_weights(self) -> dict[str, float]:
        """All scoring weights as a dictionary for the scoring engine."""
        return {
            "liquidity": self.weight_liquidity,
            "volume": self.weight_volume,
            "buy_pressure": self.weight_buy_pressure,
            "token_age": self.weight_token_age,
            "social_presence": self.weight_social_presence,
            "price_trend": self.weight_price_trend,
        }


def get_settings() -> Settings:
    """
    Factory function for settings.

    Can be overridden in tests via FastAPI dependency injection.
    """
    return Settings()
