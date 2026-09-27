"""
Unit tests for ScoringService and MarketCapCategorizer.

Tests cover:
    - Individual scoring dimension logic
    - Composite score calculation
    - Ranking (sorted by score, rank numbers assigned)
    - Reason generation
    - Missing data penalty behavior
    - MarketCapCategorizer bucketing
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.config import Settings
from app.filters.base import TokenPair
from app.schemas.snapshot import SnapshotBase
from app.schemas.token import TokenBase
from app.services.categorizer import MarketCapCategorizer
from app.services.scoring_service import ScoringService

# ─── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def settings() -> Settings:
    """Test settings with default weights."""
    return Settings(
        app_env="testing",
        database_url="sqlite:///./test.db",
    )


@pytest.fixture
def scorer(settings: Settings) -> ScoringService:
    """A scoring service with default weights."""
    return ScoringService(settings)


@pytest.fixture
def categorizer(settings: Settings) -> MarketCapCategorizer:
    """A categorizer with default thresholds."""
    return MarketCapCategorizer(settings)


def _make_pair(
    symbol: str = "TEST",
    market_cap: float | None = 500_000,
    liquidity: float | None = 250_000,
    volume_24h: float | None = 1_000_000,
    buys: int | None = 200,
    sells: int | None = 100,
    pair_created_at: datetime | None | str = "default",
    website: str | None = "https://test.io",
    twitter: str | None = "testtoken",
    telegram: str | None = "testchat",
    price_change_1h: float | None = 5.0,
    price_change_24h: float | None = 15.0,
) -> TokenPair:
    """Helper to create a scored-ready pair."""
    if pair_created_at == "default":
        pair_created_at = datetime.now(tz=UTC) - timedelta(hours=24)

    token = TokenBase(
        pair_address=f"pair_{symbol.lower()}",
        token_address=f"addr_{symbol.lower()}",
        name=f"Token {symbol}",
        symbol=symbol,
        chain="solana",
        market_cap=market_cap,
        pair_created_at=pair_created_at,
        website=website,
        twitter=twitter,
        telegram=telegram,
    )
    snapshot = SnapshotBase(
        price=0.01,
        liquidity=liquidity,
        volume_24h=volume_24h,
        buys=buys,
        sells=sells,
        price_change_1h=price_change_1h,
        price_change_24h=price_change_24h,
    )
    return (token, snapshot)


# ─── Individual Dimension Tests ─────────────────────────────────────────────


class TestLiquidityScoring:
    """Tests for _score_liquidity."""

    def test_none_returns_zero(self, scorer: ScoringService):
        assert scorer._score_liquidity(None) == 0.0

    def test_zero_returns_zero(self, scorer: ScoringService):
        assert scorer._score_liquidity(0) == 0.0

    def test_excellent_returns_one(self, scorer: ScoringService):
        assert scorer._score_liquidity(1_000_000) == 1.0

    def test_above_excellent_caps_at_one(self, scorer: ScoringService):
        assert scorer._score_liquidity(5_000_000) == 1.0

    def test_mid_range(self, scorer: ScoringService):
        score = scorer._score_liquidity(500_000)
        assert score == pytest.approx(0.5)


class TestVolumeScoring:
    """Tests for _score_volume."""

    def test_none_returns_zero(self, scorer: ScoringService):
        assert scorer._score_volume(None) == 0.0

    def test_excellent_returns_one(self, scorer: ScoringService):
        assert scorer._score_volume(5_000_000) == 1.0

    def test_mid_range(self, scorer: ScoringService):
        score = scorer._score_volume(2_500_000)
        assert score == pytest.approx(0.5)


class TestBuyPressureScoring:
    """Tests for _score_buy_pressure."""

    def test_none_data_returns_zero(self, scorer: ScoringService):
        assert scorer._score_buy_pressure(None, None) == 0.0

    def test_zero_sells_returns_one(self, scorer: ScoringService):
        assert scorer._score_buy_pressure(100, 0) == 1.0

    def test_equal_buys_sells(self, scorer: ScoringService):
        score = scorer._score_buy_pressure(100, 100)
        assert score == pytest.approx(0.4)

    def test_excellent_ratio(self, scorer: ScoringService):
        score = scorer._score_buy_pressure(250, 100)
        assert score == pytest.approx(1.0)

    def test_below_one_ratio(self, scorer: ScoringService):
        score = scorer._score_buy_pressure(50, 100)  # ratio = 0.5
        assert score == pytest.approx(0.2)


class TestTokenAgeScoring:
    """Tests for _score_token_age."""

    def test_none_returns_zero(self, scorer: ScoringService):
        assert scorer._score_token_age(None) == 0.0

    def test_24h_old_is_peak(self, scorer: ScoringService):
        created = datetime.now(tz=UTC) - timedelta(hours=24)
        score = scorer._score_token_age(created)
        assert score == pytest.approx(1.0, abs=0.01)

    def test_very_new_is_low(self, scorer: ScoringService):
        created = datetime.now(tz=UTC) - timedelta(minutes=15)
        score = scorer._score_token_age(created)
        assert score < 0.2

    def test_14_days_old_is_near_zero(self, scorer: ScoringService):
        created = datetime.now(tz=UTC) - timedelta(days=14)
        score = scorer._score_token_age(created)
        assert score < 0.1

    def test_1h_old(self, scorer: ScoringService):
        created = datetime.now(tz=UTC) - timedelta(hours=1)
        score = scorer._score_token_age(created)
        assert score == pytest.approx(0.5, abs=0.05)


class TestSocialScoring:
    """Tests for _score_social_presence."""

    def test_all_three(self, scorer: ScoringService):
        score = scorer._score_social_presence("https://x.com", "handle", "chat")
        assert score == pytest.approx(1.0)

    def test_none(self, scorer: ScoringService):
        score = scorer._score_social_presence(None, None, None)
        assert score == 0.0

    def test_one_link(self, scorer: ScoringService):
        score = scorer._score_social_presence("https://x.com", None, None)
        assert score == pytest.approx(0.34)

    def test_two_links(self, scorer: ScoringService):
        score = scorer._score_social_presence("https://x.com", "handle", None)
        assert score == pytest.approx(0.67, abs=0.01)


class TestPriceTrendScoring:
    """Tests for _score_price_trend."""

    def test_none_returns_zero(self, scorer: ScoringService):
        assert scorer._score_price_trend(None, None) == 0.0

    def test_positive_5pct(self, scorer: ScoringService):
        score = scorer._score_price_trend(5.0, None)
        # 5% is in 0-20 range: 0.3 + (5/20)*0.5 = 0.425
        assert score == pytest.approx(0.425)

    def test_negative_heavy(self, scorer: ScoringService):
        score = scorer._score_price_trend(-15.0, None)
        assert score == 0.0

    def test_parabolic_pump(self, scorer: ScoringService):
        score = scorer._score_price_trend(150.0, None)
        assert score == pytest.approx(0.7)

    def test_falls_back_to_24h(self, scorer: ScoringService):
        score = scorer._score_price_trend(None, 10.0)
        # Uses 24h as fallback: 10% in 0-20 range
        assert score > 0.3


# ─── Composite Scoring Tests ────────────────────────────────────────────────


class TestCompositeScoring:
    """Tests for full score_tokens flow."""

    def test_good_token_gets_high_score(self, scorer: ScoringService):
        pairs = [_make_pair(symbol="GOOD")]
        results = scorer.score_tokens(pairs, category="early")

        assert len(results) == 1
        assert results[0].score > 50  # Good token should score well
        assert results[0].rank == 1
        assert results[0].category == "early"
        assert results[0].symbol == "GOOD"

    def test_bad_token_gets_low_score(self, scorer: ScoringService):
        pairs = [
            _make_pair(
                symbol="BAD",
                liquidity=0,
                volume_24h=0,
                buys=10,
                sells=100,
                website=None,
                twitter=None,
                telegram=None,
                price_change_1h=-20.0,
                pair_created_at=datetime.now(tz=UTC) - timedelta(days=30),
            )
        ]
        results = scorer.score_tokens(pairs, category="early")

        assert len(results) == 1
        assert results[0].score < 15

    def test_ranking_order(self, scorer: ScoringService):
        pairs = [
            _make_pair(symbol="MED", liquidity=100_000, volume_24h=500_000),
            _make_pair(symbol="BEST", liquidity=800_000, volume_24h=4_000_000),
            _make_pair(symbol="WORST", liquidity=10_000, volume_24h=50_000),
        ]
        results = scorer.score_tokens(pairs, category="mid")

        assert results[0].symbol == "BEST"
        assert results[1].symbol == "MED"
        assert results[2].symbol == "WORST"
        assert results[0].rank == 1
        assert results[1].rank == 2
        assert results[2].rank == 3

    def test_scores_include_reasons(self, scorer: ScoringService):
        pairs = [_make_pair()]
        results = scorer.score_tokens(pairs, category="early")

        reasons = results[0].score_reasons
        assert len(reasons) == 6
        assert any("Liquidity" in r for r in reasons)
        assert any("Volume" in r for r in reasons)
        assert any("Buy pressure" in r for r in reasons)
        assert any("Token age" in r for r in reasons)
        assert any("Social" in r for r in reasons)
        assert any("Price trend" in r for r in reasons)

    def test_buy_sell_ratio_in_response(self, scorer: ScoringService):
        pairs = [_make_pair(buys=200, sells=100)]
        results = scorer.score_tokens(pairs, category="early")

        assert results[0].buy_sell_ratio == 2.0

    def test_empty_input(self, scorer: ScoringService):
        results = scorer.score_tokens([], category="early")
        assert results == []

    def test_missing_data_penalized(self, scorer: ScoringService):
        """Token with all None data should score very low."""
        pairs = [
            _make_pair(
                symbol="EMPTY",
                liquidity=None,
                volume_24h=None,
                buys=None,
                sells=None,
                pair_created_at=None,
                website=None,
                twitter=None,
                telegram=None,
                price_change_1h=None,
                price_change_24h=None,
            )
        ]
        results = scorer.score_tokens(pairs, category="early")
        assert results[0].score == 0.0


# ─── MarketCapCategorizer Tests ─────────────────────────────────────────────


class TestMarketCapCategorizer:
    """Tests for MarketCapCategorizer."""

    def test_categorizes_early(self, categorizer: MarketCapCategorizer):
        pairs = [_make_pair(symbol="EARLY", market_cap=500_000)]
        buckets = categorizer.categorize(pairs)

        assert len(buckets["early"]) == 1
        assert buckets["early"][0][0].symbol == "EARLY"

    def test_categorizes_mid(self, categorizer: MarketCapCategorizer):
        pairs = [_make_pair(symbol="MID", market_cap=5_000_000)]
        buckets = categorizer.categorize(pairs)

        assert len(buckets["mid"]) == 1

    def test_categorizes_large(self, categorizer: MarketCapCategorizer):
        pairs = [_make_pair(symbol="BIG", market_cap=50_000_000)]
        buckets = categorizer.categorize(pairs)

        assert len(buckets["large"]) == 1

    def test_none_market_cap_uncategorized(self, categorizer: MarketCapCategorizer):
        pairs = [_make_pair(symbol="UNK", market_cap=None)]
        buckets = categorizer.categorize(pairs)

        assert len(buckets["uncategorized"]) == 1

    def test_outside_all_ranges_uncategorized(self, categorizer: MarketCapCategorizer):
        pairs = [_make_pair(symbol="HUGE", market_cap=500_000_000)]
        buckets = categorizer.categorize(pairs)

        assert len(buckets["uncategorized"]) == 1

    def test_multiple_categories(self, categorizer: MarketCapCategorizer):
        pairs = [
            _make_pair(symbol="E", market_cap=200_000),
            _make_pair(symbol="M", market_cap=3_000_000),
            _make_pair(symbol="L", market_cap=100_000_000),
            _make_pair(symbol="X", market_cap=None),
        ]
        buckets = categorizer.categorize(pairs)

        assert len(buckets["early"]) == 1
        assert len(buckets["mid"]) == 1
        assert len(buckets["large"]) == 1
        assert len(buckets["uncategorized"]) == 1

    def test_get_thresholds(self, categorizer: MarketCapCategorizer):
        early = categorizer.get_thresholds("early")
        assert early is not None
        assert early.mc_min == 100_000
        assert early.mc_max == 1_000_000
        assert early.min_volume == 100_000
        assert early.min_liquidity == 40_000

    def test_get_thresholds_unknown(self, categorizer: MarketCapCategorizer):
        assert categorizer.get_thresholds("unknown") is None

    def test_boundary_values(self, categorizer: MarketCapCategorizer):
        """Tokens at exact category boundaries should be categorized."""
        pairs = [
            _make_pair(symbol="MIN_E", market_cap=100_000),
            _make_pair(symbol="MAX_E", market_cap=1_000_000),
        ]
        buckets = categorizer.categorize(pairs)

        assert len(buckets["early"]) == 2
