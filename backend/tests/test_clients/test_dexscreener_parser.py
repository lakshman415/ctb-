"""
Unit tests for DexScreenerParser.

Tests cover:
    - Full pair parsing (token + snapshot)
    - Missing/null field handling
    - Price string edge cases
    - Timestamp conversion
    - Social link extraction
    - Transaction fallback logic
    - Batch parsing with error resilience
"""

from datetime import UTC, datetime

import pytest

from app.clients.dexscreener_models import (
    DexBaseToken,
    DexInfo,
    DexLiquidity,
    DexPair,
    DexQuoteToken,
    DexSocial,
    DexTransactions,
    DexWebsite,
)
from app.clients.dexscreener_parser import DexScreenerParser


@pytest.fixture
def parser() -> DexScreenerParser:
    """Provide a fresh parser instance."""
    return DexScreenerParser()


@pytest.fixture
def sample_pair() -> DexPair:
    """A realistic DexScreener pair response with all fields populated."""
    return DexPair(
        chainId="solana",
        dexId="raydium",
        url="https://dexscreener.com/solana/abc123",
        pairAddress="abc123def456",
        labels=["v2"],
        baseToken=DexBaseToken(
            address="So11111111111111111111111111111111111111112",
            name="DogeCoin2",
            symbol="DOGE2",
        ),
        quoteToken=DexQuoteToken(
            address="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            name="USDC",
            symbol="USDC",
        ),
        priceNative="0.00234",
        priceUsd="0.00567",
        txns={
            "m5": DexTransactions(buys=15, sells=8),
            "h1": DexTransactions(buys=120, sells=90),
            "h6": DexTransactions(buys=800, sells=600),
            "h24": DexTransactions(buys=3200, sells=2400),
        },
        volume={
            "m5": 12500.0,
            "h1": 185000.0,
            "h6": 920000.0,
            "h24": 3500000.0,
        },
        priceChange={
            "m5": 1.5,
            "h1": -2.3,
            "h6": 5.7,
            "h24": 12.4,
        },
        liquidity=DexLiquidity(usd=250000.0, base=100000000.0, quote=125000.0),
        fdv=5000000.0,
        marketCap=4500000.0,
        pairCreatedAt=1700000000000,  # 2023-11-14T22:13:20Z
        info=DexInfo(
            imageUrl="https://example.com/logo.png",
            websites=[DexWebsite(url="https://dogecoin2.io")],
            socials=[
                DexSocial(platform="twitter", handle="dogecoin2official"),
                DexSocial(platform="telegram", handle="dogecoin2chat"),
            ],
        ),
    )


@pytest.fixture
def minimal_pair() -> DexPair:
    """A sparse pair with many fields missing (common for new/obscure tokens)."""
    return DexPair(
        chainId="ethereum",
        pairAddress="0xdeadbeef1234",
        baseToken=DexBaseToken(
            address="0xtoken123",
            name="Unknown Token",
            symbol="UNK",
        ),
        priceUsd="0.000001",
    )


class TestParseTokenFullData:
    """Tests for parse_pair_to_token with complete data."""

    def test_basic_fields(self, parser: DexScreenerParser, sample_pair: DexPair):
        token = parser.parse_pair_to_token(sample_pair)

        assert token.pair_address == "abc123def456"
        assert token.token_address == "So11111111111111111111111111111111111111112"
        assert token.name == "DogeCoin2"
        assert token.symbol == "DOGE2"
        assert token.chain == "solana"

    def test_price_and_market_data(self, parser: DexScreenerParser, sample_pair: DexPair):
        token = parser.parse_pair_to_token(sample_pair)

        assert token.price == 0.00567
        assert token.market_cap == 4500000.0
        assert token.fdv == 5000000.0
        assert token.liquidity == 250000.0

    def test_pair_created_at_conversion(self, parser: DexScreenerParser, sample_pair: DexPair):
        token = parser.parse_pair_to_token(sample_pair)

        expected = datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)
        assert token.pair_created_at == expected

    def test_social_links(self, parser: DexScreenerParser, sample_pair: DexPair):
        token = parser.parse_pair_to_token(sample_pair)

        assert token.website == "https://dogecoin2.io"
        assert token.twitter == "dogecoin2official"
        assert token.telegram == "dogecoin2chat"


class TestParseTokenMinimalData:
    """Tests for parse_pair_to_token with sparse/missing data."""

    def test_basic_fields_still_work(self, parser: DexScreenerParser, minimal_pair: DexPair):
        token = parser.parse_pair_to_token(minimal_pair)

        assert token.pair_address == "0xdeadbeef1234"
        assert token.token_address == "0xtoken123"
        assert token.name == "Unknown Token"
        assert token.symbol == "UNK"
        assert token.chain == "ethereum"

    def test_missing_market_data_is_none(self, parser: DexScreenerParser, minimal_pair: DexPair):
        token = parser.parse_pair_to_token(minimal_pair)

        assert token.market_cap is None
        assert token.fdv is None
        assert token.liquidity is None
        assert token.pair_created_at is None

    def test_missing_socials_are_none(self, parser: DexScreenerParser, minimal_pair: DexPair):
        token = parser.parse_pair_to_token(minimal_pair)

        assert token.website is None
        assert token.twitter is None
        assert token.telegram is None


class TestParseSnapshot:
    """Tests for parse_pair_to_snapshot."""

    def test_price_extracted(self, parser: DexScreenerParser, sample_pair: DexPair):
        snapshot = parser.parse_pair_to_snapshot(sample_pair)

        assert snapshot.price == 0.00567

    def test_volume_by_period(self, parser: DexScreenerParser, sample_pair: DexPair):
        snapshot = parser.parse_pair_to_snapshot(sample_pair)

        assert snapshot.volume_5m == 12500.0
        assert snapshot.volume_1h == 185000.0
        assert snapshot.volume_6h == 920000.0
        assert snapshot.volume_24h == 3500000.0

    def test_price_change_by_period(self, parser: DexScreenerParser, sample_pair: DexPair):
        snapshot = parser.parse_pair_to_snapshot(sample_pair)

        assert snapshot.price_change_5m == 1.5
        assert snapshot.price_change_1h == -2.3
        assert snapshot.price_change_6h == 5.7
        assert snapshot.price_change_24h == 12.4

    def test_transactions_24h(self, parser: DexScreenerParser, sample_pair: DexPair):
        snapshot = parser.parse_pair_to_snapshot(sample_pair)

        assert snapshot.buys == 3200
        assert snapshot.sells == 2400

    def test_liquidity_in_snapshot(self, parser: DexScreenerParser, sample_pair: DexPair):
        snapshot = parser.parse_pair_to_snapshot(sample_pair)

        assert snapshot.liquidity == 250000.0

    def test_minimal_snapshot_defaults(self, parser: DexScreenerParser, minimal_pair: DexPair):
        snapshot = parser.parse_pair_to_snapshot(minimal_pair)

        assert snapshot.price == 0.000001
        assert snapshot.volume_5m is None
        assert snapshot.volume_1h is None
        assert snapshot.volume_6h is None
        assert snapshot.volume_24h is None
        assert snapshot.buys is None
        assert snapshot.sells is None
        assert snapshot.price_change_24h is None
        assert snapshot.liquidity is None


class TestTransactionFallback:
    """Tests for _extract_txns_24h fallback logic."""

    def test_falls_back_to_h6_when_h24_missing(self, parser: DexScreenerParser):
        pair = DexPair(
            chainId="solana",
            pairAddress="test123",
            baseToken=DexBaseToken(address="addr", name="Test", symbol="TST"),
            txns={
                "h1": DexTransactions(buys=10, sells=5),
                "h6": DexTransactions(buys=60, sells=30),
            },
        )
        snapshot = parser.parse_pair_to_snapshot(pair)

        assert snapshot.buys == 60
        assert snapshot.sells == 30

    def test_falls_back_to_h1_when_h6_missing(self, parser: DexScreenerParser):
        pair = DexPair(
            chainId="solana",
            pairAddress="test456",
            baseToken=DexBaseToken(address="addr", name="Test", symbol="TST"),
            txns={
                "m5": DexTransactions(buys=2, sells=1),
                "h1": DexTransactions(buys=20, sells=10),
            },
        )
        snapshot = parser.parse_pair_to_snapshot(pair)

        assert snapshot.buys == 20
        assert snapshot.sells == 10

    def test_returns_none_when_no_txns(self, parser: DexScreenerParser):
        pair = DexPair(
            chainId="solana",
            pairAddress="test789",
            baseToken=DexBaseToken(address="addr", name="Test", symbol="TST"),
            txns={},
        )
        snapshot = parser.parse_pair_to_snapshot(pair)

        assert snapshot.buys is None
        assert snapshot.sells is None


class TestPriceEdgeCases:
    """Tests for price string parsing edge cases."""

    def test_none_price(self, parser: DexScreenerParser):
        assert parser._parse_price(None) is None

    def test_empty_string_price(self, parser: DexScreenerParser):
        assert parser._parse_price("") is None

    def test_valid_price(self, parser: DexScreenerParser):
        assert parser._parse_price("0.00001234") == 0.00001234

    def test_large_price(self, parser: DexScreenerParser):
        assert parser._parse_price("45678.90") == 45678.90

    def test_invalid_price_string(self, parser: DexScreenerParser):
        assert parser._parse_price("not_a_number") is None


class TestTimestampConversion:
    """Tests for millisecond timestamp conversion."""

    def test_valid_timestamp(self, parser: DexScreenerParser):
        # 2023-11-14T22:13:20Z in milliseconds
        result = parser._ms_to_datetime(1700000000000)
        expected = datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)
        assert result == expected

    def test_none_timestamp(self, parser: DexScreenerParser):
        assert parser._ms_to_datetime(None) is None

    def test_zero_timestamp(self, parser: DexScreenerParser):
        result = parser._ms_to_datetime(0)
        expected = datetime(1970, 1, 1, 0, 0, 0, tzinfo=UTC)
        assert result == expected


class TestBatchParsing:
    """Tests for parse_pairs batch processing."""

    def test_parses_valid_pairs(self, parser: DexScreenerParser, sample_pair: DexPair):
        results = parser.parse_pairs([sample_pair])

        assert len(results) == 1
        token, snapshot = results[0]
        assert token.symbol == "DOGE2"
        assert snapshot.price == 0.00567

    def test_skips_empty_pair_address(self, parser: DexScreenerParser):
        invalid_pair = DexPair(
            chainId="solana",
            pairAddress="",  # Empty — should be skipped
            baseToken=DexBaseToken(address="addr", name="Test", symbol="TST"),
        )
        results = parser.parse_pairs([invalid_pair])

        assert len(results) == 0

    def test_mixed_valid_and_invalid(
        self, parser: DexScreenerParser, sample_pair: DexPair
    ):
        invalid_pair = DexPair(
            chainId="solana",
            pairAddress="",
            baseToken=DexBaseToken(address="addr", name="Bad", symbol="BAD"),
        )
        results = parser.parse_pairs([sample_pair, invalid_pair])

        assert len(results) == 1
        assert results[0][0].symbol == "DOGE2"

    def test_empty_input(self, parser: DexScreenerParser):
        results = parser.parse_pairs([])
        assert len(results) == 0

    def test_multiple_valid_pairs(self, parser: DexScreenerParser):
        pair_a = DexPair(
            chainId="solana",
            pairAddress="pair_a",
            baseToken=DexBaseToken(address="addr_a", name="TokenA", symbol="TOKA"),
            priceUsd="1.5",
        )
        pair_b = DexPair(
            chainId="ethereum",
            pairAddress="pair_b",
            baseToken=DexBaseToken(address="addr_b", name="TokenB", symbol="TOKB"),
            priceUsd="2.5",
        )
        results = parser.parse_pairs([pair_a, pair_b])

        assert len(results) == 2
        assert results[0][0].symbol == "TOKA"
        assert results[1][0].symbol == "TOKB"
        assert results[0][0].chain == "solana"
        assert results[1][0].chain == "ethereum"
