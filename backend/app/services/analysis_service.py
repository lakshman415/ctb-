"""
Token analysis service.

Given a contract address and chain, fetches the token data from DexScreener
and performs technical analysis — momentum, liquidity health, volume analysis,
buy pressure, age assessment, and overall grading.
"""

import logging
from datetime import UTC, datetime

from app.clients.dexscreener import DexScreenerClient
from app.clients.dexscreener_models import DexPair
from app.schemas.analysis import (
    PriceChangeData,
    TechnicalIndicators,
    TokenAnalysisResponse,
    TokenOverview,
    TransactionData,
    VolumeData,
)

logger = logging.getLogger(__name__)


class AnalysisService:
    """Analyzes a single token by contract address and chain."""

    def __init__(self, client: DexScreenerClient):
        self._client = client

    async def analyze(self, chain: str, address: str) -> TokenAnalysisResponse | None:
        """
        Fetch token data and run technical analysis.

        Args:
            chain: Chain identifier (solana, ethereum, base, robinhood).
            address: Token contract address.

        Returns:
            Full analysis or None if token not found.
        """
        # Fetch all pairs for this token on this chain
        pairs = await self._client.get_token_pairs(chain, address)

        if not pairs:
            # Try search as fallback
            search_results = await self._client.search_pairs(query=address)
            pairs = [p for p in search_results if p.chainId == chain]

        if not pairs:
            return None

        # Use the highest-liquidity pair
        best_pair = self._select_best_pair(pairs)

        # Build analysis
        overview = self._build_overview(best_pair, chain)
        volume = self._build_volume(best_pair)
        transactions = self._build_transactions(best_pair)
        price_changes = self._build_price_changes(best_pair)
        technicals = self._build_technicals(best_pair, overview)
        score = self._calculate_score(technicals, volume, transactions)

        return TokenAnalysisResponse(
            overview=overview,
            volume=volume,
            transactions=transactions,
            price_changes=price_changes,
            technicals=technicals,
            score=round(score, 1),
            analyzed_at=datetime.now(tz=UTC),
        )

    def _select_best_pair(self, pairs: list[DexPair]) -> DexPair:
        """Pick the pair with highest liquidity (most tradeable)."""
        def liq(p: DexPair) -> float:
            if p.liquidity and p.liquidity.usd:
                return p.liquidity.usd
            return 0.0

        return max(pairs, key=liq)

    def _build_overview(self, pair: DexPair, chain: str) -> TokenOverview:
        price = float(pair.priceUsd) if pair.priceUsd else None
        created_at = None
        if pair.pairCreatedAt:
            created_at = datetime.fromtimestamp(pair.pairCreatedAt / 1000, tz=UTC)

        website = None
        twitter = None
        telegram = None
        if pair.info:
            if pair.info.websites:
                website = pair.info.websites[0].url or None
            for social in pair.info.socials:
                if social.platform.lower() == "twitter":
                    twitter = social.handle
                elif social.platform.lower() == "telegram":
                    telegram = social.handle

        return TokenOverview(
            pair_address=pair.pairAddress,
            token_address=pair.baseToken.address,
            name=pair.baseToken.name,
            symbol=pair.baseToken.symbol,
            chain=chain,
            dex=pair.dexId,
            price=price,
            market_cap=pair.marketCap,
            fdv=pair.fdv,
            liquidity=pair.liquidity.usd if pair.liquidity else None,
            pair_created_at=created_at,
            website=website,
            twitter=twitter,
            telegram=telegram,
            dexscreener_url=f"https://dexscreener.com/{chain}/{pair.pairAddress}",
        )

    def _build_volume(self, pair: DexPair) -> VolumeData:
        return VolumeData(
            volume_5m=pair.volume.get("m5"),
            volume_1h=pair.volume.get("h1"),
            volume_6h=pair.volume.get("h6"),
            volume_24h=pair.volume.get("h24"),
        )

    def _build_transactions(self, pair: DexPair) -> TransactionData:
        # Prefer 24h, fall back
        buys = None
        sells = None
        for period in ("h24", "h6", "h1"):
            if period in pair.txns:
                buys = pair.txns[period].buys
                sells = pair.txns[period].sells
                break

        ratio = None
        total = None
        if buys is not None and sells is not None:
            ratio = round(buys / sells, 2) if sells > 0 else 999.0
            total = buys + sells

        return TransactionData(
            buys=buys,
            sells=sells,
            buy_sell_ratio=ratio,
            total_txns=total,
        )

    def _build_price_changes(self, pair: DexPair) -> PriceChangeData:
        return PriceChangeData(
            change_5m=pair.priceChange.get("m5"),
            change_1h=pair.priceChange.get("h1"),
            change_6h=pair.priceChange.get("h6"),
            change_24h=pair.priceChange.get("h24"),
        )

    def _build_technicals(self, pair: DexPair, overview: TokenOverview) -> TechnicalIndicators:
        indicators = TechnicalIndicators()
        summary: list[str] = []

        # Momentum
        change_1h = pair.priceChange.get("h1")
        change_24h = pair.priceChange.get("h24")

        if change_1h is not None:
            if change_1h > 5:
                indicators.momentum_1h = "bullish"
            elif change_1h < -5:
                indicators.momentum_1h = "bearish"
            else:
                indicators.momentum_1h = "neutral"

        if change_24h is not None:
            if change_24h > 10:
                indicators.momentum_24h = "bullish"
            elif change_24h < -10:
                indicators.momentum_24h = "bearish"
            else:
                indicators.momentum_24h = "neutral"

        # Liquidity health
        liq = overview.liquidity or 0
        mcap = overview.market_cap or 0

        if mcap > 0 and liq > 0:
            ratio = liq / mcap
            indicators.liquidity_mcap_ratio = round(ratio, 4)
            if ratio >= 0.20:
                indicators.liquidity_grade = "excellent"
                summary.append(f"Excellent liquidity ({ratio*100:.1f}% of MCap)")
            elif ratio >= 0.10:
                indicators.liquidity_grade = "good"
                summary.append(f"Good liquidity ({ratio*100:.1f}% of MCap)")
            elif ratio >= 0.05:
                indicators.liquidity_grade = "fair"
                summary.append(f"Fair liquidity ({ratio*100:.1f}% of MCap)")
            elif ratio >= 0.02:
                indicators.liquidity_grade = "poor"
                summary.append(f"Low liquidity ({ratio*100:.1f}% of MCap) — high slippage risk")
            else:
                indicators.liquidity_grade = "danger"
                summary.append(f"Dangerously low liquidity ({ratio*100:.2f}% of MCap) — possible scam")

        # Volume analysis
        vol_24h = pair.volume.get("h24", 0)
        if liq > 0 and vol_24h:
            vol_liq_ratio = vol_24h / liq
            indicators.volume_to_liquidity_ratio = round(vol_liq_ratio, 2)
            if vol_liq_ratio >= 10:
                indicators.volume_grade = "very_high"
                summary.append(f"Very high volume ({vol_liq_ratio:.1f}x liquidity) — strong interest")
            elif vol_liq_ratio >= 3:
                indicators.volume_grade = "high"
                summary.append(f"High volume ({vol_liq_ratio:.1f}x liquidity)")
            elif vol_liq_ratio >= 1:
                indicators.volume_grade = "moderate"
                summary.append(f"Moderate volume ({vol_liq_ratio:.1f}x liquidity)")
            else:
                indicators.volume_grade = "low"
                summary.append(f"Low volume ({vol_liq_ratio:.1f}x liquidity) — low interest")

        # Buy pressure
        txn = self._build_transactions(pair)
        if txn.buy_sell_ratio is not None:
            if txn.buy_sell_ratio >= 2.0:
                indicators.buy_pressure_grade = "strong"
                summary.append(f"Strong buy pressure (B/S ratio: {txn.buy_sell_ratio:.1f})")
            elif txn.buy_sell_ratio >= 1.2:
                indicators.buy_pressure_grade = "moderate"
                summary.append(f"Moderate buy pressure (B/S ratio: {txn.buy_sell_ratio:.1f})")
            elif txn.buy_sell_ratio >= 0.8:
                indicators.buy_pressure_grade = "weak"
                summary.append(f"Weak/neutral pressure (B/S ratio: {txn.buy_sell_ratio:.1f})")
            else:
                indicators.buy_pressure_grade = "selling"
                summary.append(f"Sell pressure dominant (B/S ratio: {txn.buy_sell_ratio:.1f}) — bearish")

        # Age
        if overview.pair_created_at:
            age_hours = (datetime.now(tz=UTC) - overview.pair_created_at).total_seconds() / 3600
            indicators.age_hours = round(age_hours, 1)
            if age_hours < 1:
                indicators.age_grade = "very_new"
                summary.append(f"Very new ({age_hours*60:.0f} minutes) — extremely high risk")
            elif age_hours < 24:
                indicators.age_grade = "new"
                summary.append(f"New ({age_hours:.0f}h old) — high risk, high potential")
            elif age_hours < 168:
                indicators.age_grade = "established"
                summary.append(f"Established ({age_hours/24:.1f} days old)")
            else:
                indicators.age_grade = "mature"
                summary.append(f"Mature ({age_hours/24:.0f} days old)")

        # Social
        social_count = sum([
            1 if overview.website else 0,
            1 if overview.twitter else 0,
            1 if overview.telegram else 0,
        ])
        indicators.social_count = social_count
        if social_count == 3:
            summary.append("All socials present (website, twitter, telegram)")
        elif social_count == 0:
            summary.append("No social links — anonymous project, higher risk")

        # Support/Resistance levels (estimated from price changes)
        price = float(pair.priceUsd) if pair.priceUsd else None
        if price and price > 0:
            sr_levels = self._compute_support_resistance(price, pair)
            indicators.support_levels = sr_levels["support"]
            indicators.resistance_levels = sr_levels["resistance"]

        # Market Cap S/R levels
        mcap = overview.market_cap
        if mcap and mcap > 0 and price and price > 0:
            mcap_sr = self._compute_mcap_support_resistance(mcap, pair)
            indicators.mcap_support_levels = mcap_sr["support"]
            indicators.mcap_resistance_levels = mcap_sr["resistance"]
            if mcap_sr["support"]:
                summary.append(
                    f"MCap Support: {', '.join(self._fmt_mcap(s) for s in mcap_sr['support'])}"
                )
            if mcap_sr["resistance"]:
                summary.append(
                    f"MCap Resistance: {', '.join(self._fmt_mcap(r) for r in mcap_sr['resistance'])}"
                )

        # Trend analysis
        self._analyze_trend(indicators, pair, summary)

        # Volatility
        self._analyze_volatility(indicators, pair, summary)

        # Risk/Reward
        self._analyze_risk_reward(indicators, overview, txn, summary)

        # Key signals — what a pro trader would notice
        self._generate_key_signals(indicators, overview, pair, txn)

        # Overall grade
        grade_score = self._calculate_score(indicators, self._build_volume(pair), txn)
        if grade_score >= 70:
            indicators.overall_grade = "A"
            indicators.risk_level = "low"
        elif grade_score >= 55:
            indicators.overall_grade = "B"
            indicators.risk_level = "medium"
        elif grade_score >= 40:
            indicators.overall_grade = "C"
            indicators.risk_level = "medium"
        elif grade_score >= 25:
            indicators.overall_grade = "D"
            indicators.risk_level = "high"
        else:
            indicators.overall_grade = "F"
            indicators.risk_level = "extreme"

        indicators.summary = summary
        return indicators

    def _calculate_score(
        self, technicals: TechnicalIndicators, volume: VolumeData, txns: TransactionData
    ) -> float:
        """Simple weighted score based on technical indicators."""
        score = 0.0

        # Liquidity (25 pts)
        grade_map = {"excellent": 25, "good": 20, "fair": 15, "poor": 8, "danger": 0}
        score += grade_map.get(technicals.liquidity_grade or "", 0)

        # Volume (25 pts)
        vol_map = {"very_high": 25, "high": 20, "moderate": 15, "low": 5}
        score += vol_map.get(technicals.volume_grade or "", 0)

        # Buy pressure (20 pts)
        bp_map = {"strong": 20, "moderate": 15, "weak": 8, "selling": 0}
        score += bp_map.get(technicals.buy_pressure_grade or "", 0)

        # Age (15 pts) — "new" and "established" are best for scalping
        age_map = {"very_new": 5, "new": 15, "established": 12, "mature": 6}
        score += age_map.get(technicals.age_grade or "", 0)

        # Social (10 pts)
        score += (technicals.social_count / 3) * 10

        # Momentum bonus (5 pts)
        if technicals.momentum_1h == "bullish":
            score += 5
        elif technicals.momentum_1h == "bearish":
            score -= 2

        return min(max(score, 0), 100)

    @staticmethod
    def _compute_support_resistance(
        price: float, pair: DexPair
    ) -> dict[str, list[float]]:
        """
        Estimate support and resistance levels from price change data.

        Approach: Use the % changes to back-calculate recent highs/lows,
        then identify key psychological levels and Fibonacci retracements.

        Since we don't have full candle history, this uses:
        1. Recent high/low estimated from price changes
        2. Fibonacci retracement levels between high and low
        3. Round number psychological levels near current price
        """
        support: list[float] = []
        resistance: list[float] = []

        # Estimate recent high and low from price changes
        change_1h = pair.priceChange.get("h1", 0) or 0
        change_24h = pair.priceChange.get("h24", 0) or 0

        # Back-calculate what price was at those times
        price_1h_ago = price / (1 + change_1h / 100) if change_1h != -100 else price
        price_24h_ago = price / (1 + change_24h / 100) if change_24h != -100 else price

        # Determine recent range
        all_prices = [price, price_1h_ago, price_24h_ago]
        recent_high = max(all_prices)
        recent_low = min(all_prices)

        # Expand range slightly (estimated swing)
        range_size = recent_high - recent_low
        if range_size < price * 0.01:
            # If range is too tight, estimate from typical volatility
            range_size = price * 0.15  # Assume 15% typical range
            recent_high = price + range_size * 0.6
            recent_low = price - range_size * 0.4

        # Fibonacci levels from recent low to high
        fib_levels = [0.236, 0.382, 0.5, 0.618, 0.786]
        for fib in fib_levels:
            level = recent_low + (recent_high - recent_low) * fib
            if level < price * 0.98:  # Below current = support
                support.append(round(level, 8))
            elif level > price * 1.02:  # Above current = resistance
                resistance.append(round(level, 8))

        # Add recent low as strong support
        if recent_low < price * 0.98:
            support.append(round(recent_low, 8))

        # Add recent high as strong resistance
        if recent_high > price * 1.02:
            resistance.append(round(recent_high, 8))

        # Psychological round numbers
        magnitude = 10 ** int(f"{price:.1e}".split("e")[1])
        for mult in [0.5, 1, 2, 5, 10]:
            level = round(price / (magnitude * mult)) * (magnitude * mult)
            if level > 0:
                if level < price * 0.95:
                    support.append(round(level, 8))
                elif level > price * 1.05:
                    resistance.append(round(level, 8))

        # Deduplicate, sort, and limit
        support = sorted(set(support), reverse=True)[:3]  # Top 3 nearest supports
        resistance = sorted(set(resistance))[:3]  # Top 3 nearest resistances

        return {"support": support, "resistance": resistance}

    @staticmethod
    def _compute_mcap_support_resistance(
        mcap: float, pair: DexPair
    ) -> dict[str, list[float]]:
        """
        Compute support/resistance based on market cap.

        Uses the same approach as price S/R but with market cap values.
        More intuitive for traders: "support at $300K mcap" is easier to grasp.
        """
        support: list[float] = []
        resistance: list[float] = []

        change_1h = pair.priceChange.get("h1", 0) or 0
        change_24h = pair.priceChange.get("h24", 0) or 0

        # Back-calculate market caps at previous times
        mcap_1h_ago = mcap / (1 + change_1h / 100) if change_1h != -100 else mcap
        mcap_24h_ago = mcap / (1 + change_24h / 100) if change_24h != -100 else mcap

        all_mcaps = [mcap, mcap_1h_ago, mcap_24h_ago]
        recent_high = max(all_mcaps)
        recent_low = min(all_mcaps)

        range_size = recent_high - recent_low
        if range_size < mcap * 0.05:
            range_size = mcap * 0.20
            recent_high = mcap + range_size * 0.6
            recent_low = mcap - range_size * 0.4

        # Fibonacci levels
        fib_levels = [0.236, 0.382, 0.5, 0.618, 0.786]
        for fib in fib_levels:
            level = recent_low + (recent_high - recent_low) * fib
            if level < mcap * 0.95:
                support.append(round(level))
            elif level > mcap * 1.05:
                resistance.append(round(level))

        # Recent low/high
        if recent_low < mcap * 0.95:
            support.append(round(recent_low))
        if recent_high > mcap * 1.05:
            resistance.append(round(recent_high))

        # Round number psychological levels for market cap
        if mcap < 100_000:
            levels = [10_000, 25_000, 50_000, 75_000, 100_000]
        elif mcap < 1_000_000:
            levels = [100_000, 250_000, 500_000, 750_000, 1_000_000]
        elif mcap < 10_000_000:
            levels = [1_000_000, 2_500_000, 5_000_000, 7_500_000, 10_000_000]
        elif mcap < 100_000_000:
            levels = [10_000_000, 25_000_000, 50_000_000, 75_000_000, 100_000_000]
        else:
            levels = [100_000_000, 250_000_000, 500_000_000, 1_000_000_000]

        for level in levels:
            if level < mcap * 0.90:
                support.append(level)
            elif level > mcap * 1.10:
                resistance.append(level)

        support = sorted(set(support), reverse=True)[:3]
        resistance = sorted(set(resistance))[:3]

        return {"support": support, "resistance": resistance}

    @staticmethod
    def _analyze_trend(
        indicators: "TechnicalIndicators", pair: DexPair, summary: list[str]
    ) -> None:
        """Determine trend direction and strength from multi-timeframe price changes."""
        change_5m = pair.priceChange.get("m5", 0) or 0
        change_1h = pair.priceChange.get("h1", 0) or 0
        change_6h = pair.priceChange.get("h6", 0) or 0
        change_24h = pair.priceChange.get("h24", 0) or 0

        # Count how many timeframes are positive
        positive_count = sum(1 for c in [change_5m, change_1h, change_6h, change_24h] if c > 0)
        negative_count = sum(1 for c in [change_5m, change_1h, change_6h, change_24h] if c < 0)

        # Direction
        if positive_count >= 3:
            indicators.trend_direction = "uptrend"
        elif negative_count >= 3:
            indicators.trend_direction = "downtrend"
        else:
            indicators.trend_direction = "sideways"

        # Strength based on magnitude
        avg_change = (abs(change_1h) + abs(change_24h)) / 2
        if avg_change > 30:
            indicators.trend_strength = "strong"
        elif avg_change > 10:
            indicators.trend_strength = "moderate"
        else:
            indicators.trend_strength = "weak"

        # Explanation
        if indicators.trend_direction == "uptrend":
            if change_5m > 0 and change_1h > 0:
                indicators.trend_explanation = (
                    f"Consistent uptrend across all timeframes. "
                    f"Short-term momentum is aligned with the longer trend (+{change_1h:.1f}% 1h, +{change_24h:.1f}% 24h). "
                    f"Good for momentum entries."
                )
            else:
                indicators.trend_explanation = (
                    f"Overall uptrend but with short-term pullback. "
                    f"24h is up {change_24h:.1f}% but recent action is cooling. "
                    f"Could be a healthy retracement or start of reversal."
                )
        elif indicators.trend_direction == "downtrend":
            indicators.trend_explanation = (
                f"Downtrend confirmed across multiple timeframes "
                f"({change_1h:.1f}% 1h, {change_24h:.1f}% 24h). "
                f"Wait for reversal signals before entering."
            )
        else:
            indicators.trend_explanation = (
                f"Price is moving sideways — no clear direction. "
                f"Mixed signals across timeframes. Wait for a breakout."
            )

        summary.append(
            f"Trend: {indicators.trend_direction} ({indicators.trend_strength})"
        )

    @staticmethod
    def _analyze_volatility(
        indicators: "TechnicalIndicators", pair: DexPair, summary: list[str]
    ) -> None:
        """Assess how volatile the token is."""
        change_1h = abs(pair.priceChange.get("h1", 0) or 0)
        change_24h = abs(pair.priceChange.get("h24", 0) or 0)

        # Use the larger timeframe move as volatility proxy
        max_move = max(change_1h, change_24h)

        if max_move > 100:
            indicators.volatility_grade = "extreme"
            indicators.volatility_explanation = (
                f"Extremely volatile ({max_move:.0f}% max move). "
                f"Use very tight stop losses. Position size should be small. "
                f"Expect violent swings in both directions."
            )
        elif max_move > 40:
            indicators.volatility_grade = "high"
            indicators.volatility_explanation = (
                f"High volatility ({max_move:.0f}% max move). "
                f"Normal for memecoins. Use stop losses and don't over-leverage. "
                f"Good for scalping if you're quick."
            )
        elif max_move > 15:
            indicators.volatility_grade = "moderate"
            indicators.volatility_explanation = (
                f"Moderate volatility ({max_move:.0f}% max move). "
                f"Tradeable with standard risk management. "
                f"Not too wild, not too boring."
            )
        else:
            indicators.volatility_grade = "low"
            indicators.volatility_explanation = (
                f"Low volatility ({max_move:.0f}% max move). "
                f"Price isn't moving much. Either consolidating before a move, "
                f"or the token is losing interest."
            )

        summary.append(f"Volatility: {indicators.volatility_grade}")

    def _analyze_risk_reward(
        self,
        indicators: "TechnicalIndicators",
        overview,
        txns,
        summary: list[str],
    ) -> None:
        """Assess risk/reward based on multiple factors."""
        score = 0
        reasons = []

        # Liquidity = safety
        if indicators.liquidity_grade in ("excellent", "good"):
            score += 2
            reasons.append("good liquidity for safe exits")
        elif indicators.liquidity_grade in ("poor", "danger"):
            score -= 2
            reasons.append("low liquidity = hard to exit")

        # Buy pressure = demand
        if indicators.buy_pressure_grade == "strong":
            score += 2
            reasons.append("strong buyer demand")
        elif indicators.buy_pressure_grade == "selling":
            score -= 2
            reasons.append("sellers dominating")

        # Trend alignment
        if indicators.trend_direction == "uptrend":
            score += 1
            reasons.append("trend is in your favor")
        elif indicators.trend_direction == "downtrend":
            score -= 1
            reasons.append("trading against the trend")

        # Volatility — high vol = opportunity but also risk
        if indicators.volatility_grade == "extreme":
            score -= 1
            reasons.append("extreme volatility increases risk")
        elif indicators.volatility_grade == "high":
            score += 1
            reasons.append("good volatility for scalping")

        # Social presence = legitimacy
        if indicators.social_count >= 2:
            score += 1
            reasons.append("project has social presence")
        elif indicators.social_count == 0:
            score -= 1
            reasons.append("no socials = anonymous/risky")

        # Rating
        if score >= 4:
            indicators.risk_reward_rating = "excellent"
        elif score >= 2:
            indicators.risk_reward_rating = "good"
        elif score >= 0:
            indicators.risk_reward_rating = "fair"
        else:
            indicators.risk_reward_rating = "poor"

        indicators.risk_reward_explanation = (
            f"Risk/Reward: {indicators.risk_reward_rating}. "
            f"Factors: {', '.join(reasons)}."
        )
        summary.append(f"Risk/Reward: {indicators.risk_reward_rating}")

    @staticmethod
    def _generate_key_signals(
        indicators: "TechnicalIndicators",
        overview,
        pair: DexPair,
        txns,
    ) -> None:
        """Generate key signals a professional trader would look for."""
        signals = []

        change_1h = pair.priceChange.get("h1", 0) or 0
        change_5m = pair.priceChange.get("m5", 0) or 0
        change_24h = pair.priceChange.get("h24", 0) or 0

        # Volume spike
        if indicators.volume_grade == "very_high":
            signals.append("VOLUME SPIKE — Unusual volume detected. Something is happening with this token.")

        # Buy pressure divergence
        if txns.buy_sell_ratio and txns.buy_sell_ratio >= 2.0 and change_1h < 0:
            signals.append("ACCUMULATION — Buyers are stepping in aggressively despite price dip. Potential reversal.")

        # Sell pressure with price up (distribution)
        if txns.buy_sell_ratio and txns.buy_sell_ratio < 0.8 and change_1h > 5:
            signals.append("DISTRIBUTION WARNING — Price rising but sells dominate. Insiders may be exiting.")

        # Fresh breakout
        if change_5m > 10 and change_1h > 20:
            signals.append("BREAKOUT — Strong short-term momentum. If volume confirms, this could run further.")

        # Dump recovery
        if change_24h < -30 and change_1h > 10:
            signals.append("RECOVERY BOUNCE — Token dumped 24h but recovering. Could be dead cat bounce or real reversal.")

        # New token with good metrics
        if indicators.age_grade == "new" and indicators.buy_pressure_grade == "strong":
            signals.append("EARLY MOVER — New token with strong buy pressure. High risk but highest potential reward.")

        # Liquidity concern
        if indicators.liquidity_grade in ("poor", "danger"):
            signals.append("LIQUIDITY WARNING — Very thin liquidity. You will get massive slippage trying to sell. Be careful with position size.")

        # High mcap but low volume (dying)
        if overview.market_cap and overview.market_cap > 1_000_000:
            vol = pair.volume.get("h24", 0) or 0
            if vol < overview.market_cap * 0.05:
                signals.append("LOW ACTIVITY — High market cap but very low volume. Token may be losing interest.")

        # All timeframes aligned
        if change_5m > 0 and change_1h > 0 and change_24h > 0:
            signals.append("ALL TIMEFRAMES GREEN — Price up across 5m, 1h, and 24h. Momentum is fully aligned.")

        # All timeframes red
        if change_5m < 0 and change_1h < 0 and change_24h < 0:
            signals.append("ALL TIMEFRAMES RED — Price down everywhere. Don't try to catch a falling knife.")

        if not signals:
            signals.append("NO STRONG SIGNALS — Token is in a neutral state. Wait for a clearer setup.")

        indicators.key_signals = signals

    @staticmethod
    def _fmt_mcap(value: float) -> str:
        """Format market cap for display."""
        if value >= 1_000_000_000:
            return f"${value / 1_000_000_000:.1f}B"
        if value >= 1_000_000:
            return f"${value / 1_000_000:.1f}M"
        if value >= 1_000:
            return f"${value / 1_000:.0f}K"
        return f"${value:.0f}"
