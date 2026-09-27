"""
Unit tests for all filters and the FilterPipeline.

Tests cover:
    - Each filter's pass/fail logic
    - Handling of None/missing data
    - Edge cases (zero sells, boundary values, empty lists)
    - Pipeline chaining behavior
"""

from datetime import UTC, datetime, timedelta

from app.filters.age_filter import AgeFilter
from app.filters.base import TokenPair
from app.filters.buy_sell_ratio_filter import BuySellRatioFilter
from app.filters.liquidity_filter import LiquidityFilter
from app.filters.market_cap_filter import MarketCapFilter
from app.filters.pipeline import FilterPipeline
from app.filters.volume_filter import VolumeFilter
from app.schemas.snapshot import SnapshotBase
from app.schemas.token import TokenBase

# ─── Fixtures ───────────────────────────────────────────────────────────────


def _make_pair(
    symbol: str = "TEST",
    market_cap: float | None = 500_000,
    liquidity: float | None = 100_000,
    volume_24h: float | None = 200_000,
    volume_6h: float | None = None,
    buys: int | None = 100,
    sells: int | None = 50,
    pair_created_at: datetime | None = None,
) -> TokenPair:
    """Helper to create a (TokenBase, SnapshotBase) pair with configurable values."""
    token = TokenBase(
        pair_address=f"pair_{symbol.lower()}",
        token_address=f"addr_{symbol.lower()}",
        name=f"Token {symbol}",
        symbol=symbol,
        chain="solana",
        market_cap=market_cap,
        pair_created_at=pair_created_at,
    )
    snapshot = SnapshotBase(
        price=0.01,
        liquidity=liquidity,
        volume_24h=volume_24h,
        volume_6h=volume_6h,
        buys=buys,
        sells=sells,
    )
    return (token, snapshot)


# ─── LiquidityFilter ────────────────────────────────────────────────────────


class TestLiquidityFilter:
    """Tests for LiquidityFilter."""

    def test_passes_above_threshold(self):
        filt = LiquidityFilter(min_liquidity=50_000)
        pairs = [_make_pair(liquidity=100_000)]

        result = filt.apply(pairs)
        assert len(result) == 1

    def test_removes_below_threshold(self):
        filt = LiquidityFilter(min_liquidity=50_000)
        pairs = [_make_pair(liquidity=30_000)]

        result = filt.apply(pairs)
        assert len(result) == 0

    def test_removes_none_liquidity(self):
        filt = LiquidityFilter(min_liquidity=50_000)
        pairs = [_make_pair(liquidity=None)]

        result = filt.apply(pairs)
        assert len(result) == 0

    def test_exact_threshold_passes(self):
        filt = LiquidityFilter(min_liquidity=50_000)
        pairs = [_make_pair(liquidity=50_000)]

        result = filt.apply(pairs)
        assert len(result) == 1

    def test_empty_input(self):
        filt = LiquidityFilter(min_liquidity=50_000)
        assert filt.apply([]) == []

    def test_mixed_pass_and_fail(self):
        filt = LiquidityFilter(min_liquidity=50_000)
        pairs = [
            _make_pair(symbol="PASS", liquidity=100_000),
            _make_pair(symbol="FAIL", liquidity=10_000),
            _make_pair(symbol="NONE", liquidity=None),
        ]

        result = filt.apply(pairs)
        assert len(result) == 1
        assert result[0][0].symbol == "PASS"


# ─── MarketCapFilter ────────────────────────────────────────────────────────


class TestMarketCapFilter:
    """Tests for MarketCapFilter."""

    def test_passes_within_range(self):
        filt = MarketCapFilter(mc_min=100_000, mc_max=1_000_000)
        pairs = [_make_pair(market_cap=500_000)]

        result = filt.apply(pairs)
        assert len(result) == 1

    def test_removes_below_min(self):
        filt = MarketCapFilter(mc_min=100_000, mc_max=1_000_000)
        pairs = [_make_pair(market_cap=50_000)]

        result = filt.apply(pairs)
        assert len(result) == 0

    def test_removes_above_max(self):
        filt = MarketCapFilter(mc_min=100_000, mc_max=1_000_000)
        pairs = [_make_pair(market_cap=5_000_000)]

        result = filt.apply(pairs)
        assert len(result) == 0

    def test_removes_none_market_cap(self):
        filt = MarketCapFilter(mc_min=100_000, mc_max=1_000_000)
        pairs = [_make_pair(market_cap=None)]

        result = filt.apply(pairs)
        assert len(result) == 0

    def test_boundary_min_passes(self):
        filt = MarketCapFilter(mc_min=100_000, mc_max=1_000_000)
        pairs = [_make_pair(market_cap=100_000)]

        result = filt.apply(pairs)
        assert len(result) == 1

    def test_boundary_max_passes(self):
        filt = MarketCapFilter(mc_min=100_000, mc_max=1_000_000)
        pairs = [_make_pair(market_cap=1_000_000)]

        result = filt.apply(pairs)
        assert len(result) == 1


# ─── VolumeFilter ───────────────────────────────────────────────────────────


class TestVolumeFilter:
    """Tests for VolumeFilter."""

    def test_passes_above_threshold(self):
        filt = VolumeFilter(min_volume=100_000)
        pairs = [_make_pair(volume_24h=200_000)]

        result = filt.apply(pairs)
        assert len(result) == 1

    def test_removes_below_threshold(self):
        filt = VolumeFilter(min_volume=100_000)
        pairs = [_make_pair(volume_24h=50_000)]

        result = filt.apply(pairs)
        assert len(result) == 0

    def test_removes_none_volume(self):
        filt = VolumeFilter(min_volume=100_000)
        pairs = [_make_pair(volume_24h=None, volume_6h=None)]

        result = filt.apply(pairs)
        assert len(result) == 0

    def test_falls_back_to_6h_volume(self):
        filt = VolumeFilter(min_volume=100_000)
        pairs = [_make_pair(volume_24h=None, volume_6h=150_000)]

        result = filt.apply(pairs)
        assert len(result) == 1

    def test_fallback_6h_below_threshold(self):
        filt = VolumeFilter(min_volume=100_000)
        pairs = [_make_pair(volume_24h=None, volume_6h=50_000)]

        result = filt.apply(pairs)
        assert len(result) == 0

    def test_prefers_24h_over_6h(self):
        """If 24h volume exists, use it even if 6h is higher."""
        filt = VolumeFilter(min_volume=100_000)
        pairs = [_make_pair(volume_24h=80_000, volume_6h=200_000)]

        result = filt.apply(pairs)
        assert len(result) == 0  # Uses 24h (80k < 100k)


# ─── AgeFilter ──────────────────────────────────────────────────────────────


class TestAgeFilter:
    """Tests for AgeFilter."""

    def test_passes_within_age_range(self):
        filt = AgeFilter(min_age=timedelta(hours=1), max_age=timedelta(days=7))
        created = datetime.now(tz=UTC) - timedelta(hours=12)
        pairs = [_make_pair(pair_created_at=created)]

        result = filt.apply(pairs)
        assert len(result) == 1

    def test_removes_too_new(self):
        filt = AgeFilter(min_age=timedelta(hours=1), max_age=timedelta(days=7))
        created = datetime.now(tz=UTC) - timedelta(minutes=30)
        pairs = [_make_pair(pair_created_at=created)]

        result = filt.apply(pairs)
        assert len(result) == 0

    def test_removes_too_old(self):
        filt = AgeFilter(min_age=timedelta(hours=1), max_age=timedelta(days=7))
        created = datetime.now(tz=UTC) - timedelta(days=30)
        pairs = [_make_pair(pair_created_at=created)]

        result = filt.apply(pairs)
        assert len(result) == 0

    def test_none_age_passes_through(self):
        """Tokens with no creation date pass (scored lower, not filtered)."""
        filt = AgeFilter(min_age=timedelta(hours=1), max_age=timedelta(days=7))
        pairs = [_make_pair(pair_created_at=None)]

        result = filt.apply(pairs)
        assert len(result) == 1

    def test_min_age_only(self):
        """Only enforce minimum age, no maximum."""
        filt = AgeFilter(min_age=timedelta(hours=1), max_age=None)
        created = datetime.now(tz=UTC) - timedelta(days=365)
        pairs = [_make_pair(pair_created_at=created)]

        result = filt.apply(pairs)
        assert len(result) == 1

    def test_max_age_only(self):
        """Only enforce maximum age, no minimum."""
        filt = AgeFilter(min_age=None, max_age=timedelta(days=7))
        created = datetime.now(tz=UTC) - timedelta(minutes=5)
        pairs = [_make_pair(pair_created_at=created)]

        result = filt.apply(pairs)
        assert len(result) == 1


# ─── BuySellRatioFilter ─────────────────────────────────────────────────────


class TestBuySellRatioFilter:
    """Tests for BuySellRatioFilter."""

    def test_passes_good_ratio(self):
        filt = BuySellRatioFilter(min_ratio=1.0)
        pairs = [_make_pair(buys=100, sells=50)]  # ratio = 2.0

        result = filt.apply(pairs)
        assert len(result) == 1

    def test_removes_bad_ratio(self):
        filt = BuySellRatioFilter(min_ratio=1.0)
        pairs = [_make_pair(buys=30, sells=60)]  # ratio = 0.5

        result = filt.apply(pairs)
        assert len(result) == 0

    def test_exact_ratio_passes(self):
        filt = BuySellRatioFilter(min_ratio=1.0)
        pairs = [_make_pair(buys=50, sells=50)]  # ratio = 1.0

        result = filt.apply(pairs)
        assert len(result) == 1

    def test_zero_sells_passes(self):
        """Zero sells = infinite buy pressure, should pass."""
        filt = BuySellRatioFilter(min_ratio=1.0)
        pairs = [_make_pair(buys=100, sells=0)]

        result = filt.apply(pairs)
        assert len(result) == 1

    def test_none_buys_passes_through(self):
        """No transaction data — passes (scoring penalizes instead)."""
        filt = BuySellRatioFilter(min_ratio=1.0)
        pairs = [_make_pair(buys=None, sells=None)]

        result = filt.apply(pairs)
        assert len(result) == 1

    def test_custom_min_ratio(self):
        filt = BuySellRatioFilter(min_ratio=1.5)
        pairs = [
            _make_pair(symbol="PASS", buys=150, sells=100),  # ratio = 1.5
            _make_pair(symbol="FAIL", buys=120, sells=100),  # ratio = 1.2
        ]

        result = filt.apply(pairs)
        assert len(result) == 1
        assert result[0][0].symbol == "PASS"


# ─── FilterPipeline ─────────────────────────────────────────────────────────


class TestFilterPipeline:
    """Tests for FilterPipeline orchestrator."""

    def test_chains_filters_in_order(self):
        """Filters execute sequentially, output of one feeds the next."""
        pipeline = FilterPipeline(
            filters=[
                LiquidityFilter(min_liquidity=50_000),
                VolumeFilter(min_volume=100_000),
            ]
        )
        pairs = [
            _make_pair(symbol="BOTH", liquidity=100_000, volume_24h=200_000),
            _make_pair(symbol="LIQ_ONLY", liquidity=100_000, volume_24h=50_000),
            _make_pair(symbol="NEITHER", liquidity=10_000, volume_24h=50_000),
        ]

        result = pipeline.run(pairs)
        assert len(result) == 1
        assert result[0][0].symbol == "BOTH"

    def test_empty_input(self):
        pipeline = FilterPipeline(
            filters=[LiquidityFilter(min_liquidity=50_000)]
        )
        result = pipeline.run([])
        assert result == []

    def test_no_filters(self):
        """Pipeline with no filters returns input unchanged."""
        pipeline = FilterPipeline(filters=[])
        pairs = [_make_pair(), _make_pair(symbol="B")]

        result = pipeline.run(pairs)
        assert len(result) == 2

    def test_all_filtered_out(self):
        """If all pairs fail, returns empty list."""
        pipeline = FilterPipeline(
            filters=[LiquidityFilter(min_liquidity=1_000_000)]
        )
        pairs = [
            _make_pair(symbol="A", liquidity=50_000),
            _make_pair(symbol="B", liquidity=100_000),
        ]

        result = pipeline.run(pairs)
        assert result == []

    def test_filter_count_and_names(self):
        pipeline = FilterPipeline(
            filters=[
                LiquidityFilter(min_liquidity=50_000),
                MarketCapFilter(mc_min=100_000, mc_max=1_000_000),
                VolumeFilter(min_volume=100_000),
            ]
        )
        assert pipeline.filter_count == 3
        assert pipeline.filter_names == [
            "LiquidityFilter",
            "MarketCapFilter",
            "VolumeFilter",
        ]

    def test_full_pipeline_realistic(self):
        """Realistic scenario with all 5 filters."""
        now = datetime.now(tz=UTC)

        pipeline = FilterPipeline(
            filters=[
                LiquidityFilter(min_liquidity=40_000),
                MarketCapFilter(mc_min=100_000, mc_max=1_000_000),
                VolumeFilter(min_volume=100_000),
                AgeFilter(min_age=timedelta(hours=1), max_age=timedelta(days=7)),
                BuySellRatioFilter(min_ratio=1.0),
            ]
        )

        pairs = [
            # Passes all
            _make_pair(
                symbol="GOOD",
                liquidity=80_000,
                market_cap=500_000,
                volume_24h=200_000,
                buys=150,
                sells=100,
                pair_created_at=now - timedelta(hours=12),
            ),
            # Fails liquidity
            _make_pair(
                symbol="LOW_LIQ",
                liquidity=10_000,
                market_cap=500_000,
                volume_24h=200_000,
                buys=150,
                sells=100,
                pair_created_at=now - timedelta(hours=12),
            ),
            # Fails market cap (too high)
            _make_pair(
                symbol="BIG_MC",
                liquidity=80_000,
                market_cap=5_000_000,
                volume_24h=200_000,
                buys=150,
                sells=100,
                pair_created_at=now - timedelta(hours=12),
            ),
            # Fails volume
            _make_pair(
                symbol="LOW_VOL",
                liquidity=80_000,
                market_cap=500_000,
                volume_24h=50_000,
                buys=150,
                sells=100,
                pair_created_at=now - timedelta(hours=12),
            ),
            # Fails age (too new)
            _make_pair(
                symbol="TOO_NEW",
                liquidity=80_000,
                market_cap=500_000,
                volume_24h=200_000,
                buys=150,
                sells=100,
                pair_created_at=now - timedelta(minutes=10),
            ),
            # Fails buy/sell ratio
            _make_pair(
                symbol="DUMP",
                liquidity=80_000,
                market_cap=500_000,
                volume_24h=200_000,
                buys=30,
                sells=100,
                pair_created_at=now - timedelta(hours=12),
            ),
        ]

        result = pipeline.run(pairs)
        assert len(result) == 1
        assert result[0][0].symbol == "GOOD"
