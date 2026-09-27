"""
Scoring service — deterministic token ranking.

Computes a weighted composite score (0–100) for each token based on 6 dimensions:
    1. Liquidity — how tradeable is this token?
    2. Volume — is there real trading activity?
    3. Buy Pressure — are buyers dominating sellers?
    4. Token Age — is it in the sweet spot for scalping?
    5. Social Presence — does the project look legitimate?
    6. Price Trend — is momentum positive?

No AI. No ML. Pure math with configurable weights.
Each score includes human-readable reasons explaining the assessment.

Normalization approach:
    - Each dimension produces a 0.0–1.0 sub-score
    - Sub-scores are multiplied by their configured weight
    - The weighted sum is scaled to 0–100
    - Missing data results in a 0.0 sub-score (penalized, not ignored)
"""

import logging
from datetime import UTC, datetime

from app.config import Settings
from app.filters.base import TokenPair
from app.schemas.scanner import RankedTokenResponse

logger = logging.getLogger(__name__)

# Normalization reference points (used to map raw values to 0-1 range)
# These represent "excellent" values — anything at or above gets 1.0
_LIQUIDITY_EXCELLENT = 1_000_000  # $1M liquidity = perfect score
_VOLUME_EXCELLENT = 5_000_000  # $5M 24h volume = perfect score
_BUY_RATIO_EXCELLENT = 2.5  # 2.5x buys vs sells = perfect score
_AGE_IDEAL_HOURS = 24  # 24 hours old = peak score
_AGE_DECAY_DAYS = 14  # After 14 days, age score approaches 0


class ScoringService:
    """
    Deterministic scoring engine.

    Scores are 0–100. Each dimension is normalized to 0–1
    then multiplied by its configured weight.
    """

    def __init__(self, settings: Settings):
        """
        Args:
            settings: Application settings containing scoring weights.
        """
        self._weights = settings.scoring_weights

    def score_tokens(
        self, pairs: list[TokenPair], category: str = "unknown"
    ) -> list[RankedTokenResponse]:
        """
        Score and rank a list of filtered token pairs.

        Args:
            pairs: Pre-filtered (TokenBase, SnapshotBase) tuples ready for scoring.
            category: Market cap category label (e.g., "early", "mid", "large").

        Returns:
            Tokens ranked by score (highest first), with reasons.
        """
        scored: list[RankedTokenResponse] = []

        for token, snapshot in pairs:
            score, reasons = self._calculate_score(token, snapshot)

            # Compute buy/sell ratio for the response
            buy_sell_ratio: float | None = None
            if snapshot.buys is not None and snapshot.sells is not None:
                buy_sell_ratio = (
                    snapshot.buys / snapshot.sells if snapshot.sells > 0 else float("inf")
                )

            scored.append(
                RankedTokenResponse(
                    rank=0,  # Set after sorting
                    score=round(score, 1),
                    score_reasons=reasons,
                    category=category,
                    chain=token.chain,
                    name=token.name,
                    symbol=token.symbol,
                    pair_address=token.pair_address,
                    token_address=token.token_address,
                    price=token.price,
                    market_cap=token.market_cap,
                    liquidity=snapshot.liquidity,
                    volume_24h=snapshot.volume_24h,
                    buys=snapshot.buys,
                    sells=snapshot.sells,
                    buy_sell_ratio=round(buy_sell_ratio, 2) if buy_sell_ratio is not None else None,
                    price_change_1h=snapshot.price_change_1h,
                    price_change_24h=snapshot.price_change_24h,
                    liquidity_mcap_ratio=round(snapshot.liquidity / token.market_cap, 4)
                    if snapshot.liquidity and token.market_cap and token.market_cap > 0
                    else None,
                )
            )

        # Sort by score descending, assign ranks
        scored.sort(key=lambda x: x.score, reverse=True)
        for i, item in enumerate(scored, start=1):
            item.rank = i

        logger.info(f"Scored {len(scored)} tokens in category '{category}'")
        return scored

    def _calculate_score(
        self, token, snapshot
    ) -> tuple[float, list[str]]:
        """
        Calculate composite score for a single token.

        Returns:
            Tuple of (score 0-100, list of human-readable reason strings).
        """
        reasons: list[str] = []

        # 1. Liquidity score
        liq_score = self._score_liquidity(snapshot.liquidity)
        reasons.append(self._reason_liquidity(snapshot.liquidity, liq_score))

        # 2. Volume score
        vol_score = self._score_volume(snapshot.volume_24h)
        reasons.append(self._reason_volume(snapshot.volume_24h, vol_score))

        # 3. Buy pressure score
        buy_score = self._score_buy_pressure(snapshot.buys, snapshot.sells)
        reasons.append(self._reason_buy_pressure(snapshot.buys, snapshot.sells, buy_score))

        # 4. Token age score
        age_score = self._score_token_age(token.pair_created_at)
        reasons.append(self._reason_token_age(token.pair_created_at, age_score))

        # 5. Social presence score
        social_score = self._score_social_presence(
            token.website, token.twitter, token.telegram
        )
        reasons.append(
            self._reason_social_presence(
                token.website, token.twitter, token.telegram, social_score
            )
        )

        # 6. Price trend score
        trend_score = self._score_price_trend(
            snapshot.price_change_1h, snapshot.price_change_24h
        )
        reasons.append(
            self._reason_price_trend(
                snapshot.price_change_1h, snapshot.price_change_24h, trend_score
            )
        )

        # Weighted composite
        composite = (
            liq_score * self._weights["liquidity"]
            + vol_score * self._weights["volume"]
            + buy_score * self._weights["buy_pressure"]
            + age_score * self._weights["token_age"]
            + social_score * self._weights["social_presence"]
            + trend_score * self._weights["price_trend"]
        )

        # Scale to 0-100
        final_score = composite * 100

        return final_score, reasons

    # ─── Dimension Scorers (0.0 – 1.0) ─────────────────────────────────────

    @staticmethod
    def _score_liquidity(liquidity: float | None) -> float:
        """
        Score liquidity on 0-1 scale.

        Uses logarithmic-like scaling: diminishing returns above excellent threshold.
        """
        if liquidity is None or liquidity <= 0:
            return 0.0
        return min(liquidity / _LIQUIDITY_EXCELLENT, 1.0)

    @staticmethod
    def _score_volume(volume_24h: float | None) -> float:
        """
        Score 24h volume on 0-1 scale.

        Higher volume = more tradeable = better for scalping.
        """
        if volume_24h is None or volume_24h <= 0:
            return 0.0
        return min(volume_24h / _VOLUME_EXCELLENT, 1.0)

    @staticmethod
    def _score_buy_pressure(buys: int | None, sells: int | None) -> float:
        """
        Score buy/sell ratio on 0-1 scale.

        Ratio of 1.0 (equal) = 0.4, ratio of 2.5+ = 1.0.
        Below 1.0 = linear decline toward 0.
        """
        if buys is None or sells is None:
            return 0.0

        if sells == 0:
            return 1.0  # All buys, no sells = maximum pressure

        ratio = buys / sells

        if ratio >= _BUY_RATIO_EXCELLENT:
            return 1.0
        elif ratio >= 1.0:
            # Scale 1.0–2.5 to 0.4–1.0
            return 0.4 + (ratio - 1.0) / (_BUY_RATIO_EXCELLENT - 1.0) * 0.6
        else:
            # Below 1.0: linear scale from 0 to 0.4
            return ratio * 0.4

    @staticmethod
    def _score_token_age(pair_created_at: datetime | None) -> float:
        """
        Score token age on 0-1 scale.

        Peak score at ~24 hours old. Decays for both very new and very old tokens.
        - < 1 hour: low score (too risky)
        - ~24 hours: peak score
        - > 14 days: approaching 0 (opportunity passed)
        """
        if pair_created_at is None:
            return 0.0

        now = datetime.now(tz=UTC)
        age_hours = (now - pair_created_at).total_seconds() / 3600

        if age_hours < 0:
            return 0.0  # Future timestamp = bad data

        if age_hours < 1:
            # Very new: 0 at birth, ramps up to 0.5 at 1 hour
            return (age_hours / 1.0) * 0.5
        elif age_hours <= _AGE_IDEAL_HOURS:
            # Ramp from 0.5 at 1h to 1.0 at 24h
            return 0.5 + (age_hours - 1.0) / (_AGE_IDEAL_HOURS - 1.0) * 0.5
        else:
            # Decay: 1.0 at 24h down to ~0 at 14 days
            decay_hours = _AGE_DECAY_DAYS * 24
            hours_past_peak = age_hours - _AGE_IDEAL_HOURS
            decay = max(0.0, 1.0 - (hours_past_peak / decay_hours))
            return decay

    @staticmethod
    def _score_social_presence(
        website: str | None, twitter: str | None, telegram: str | None
    ) -> float:
        """
        Score social presence on 0-1 scale.

        Simple presence check: each link adds 0.33.
        Having all three = 1.0 (project looks legitimate).
        """
        score = 0.0
        if website:
            score += 0.34
        if twitter:
            score += 0.33
        if telegram:
            score += 0.33
        return min(score, 1.0)

    @staticmethod
    def _score_price_trend(
        price_change_1h: float | None, price_change_24h: float | None
    ) -> float:
        """
        Score price trend on 0-1 scale.

        Favors tokens with positive but not extreme price changes.
        - Negative: low score
        - 0-20% 1h change: good (scaling up)
        - 20-100% 1h change: great (capped at 1.0)
        - >100% 1h change: slightly penalized (might be pump & dump)
        """
        # Use 1h change as primary, 24h as fallback context
        change = price_change_1h
        if change is None:
            change = price_change_24h
        if change is None:
            return 0.0

        if change < -10:
            # Heavy dump: 0
            return 0.0
        elif change < 0:
            # Mild negative: 0.0 to 0.3
            return (10 + change) / 10 * 0.3
        elif change <= 20:
            # Healthy growth: 0.3 to 0.8
            return 0.3 + (change / 20) * 0.5
        elif change <= 100:
            # Strong growth: 0.8 to 1.0
            return 0.8 + (change - 20) / 80 * 0.2
        else:
            # Parabolic (pump risk): slight penalty, cap at 0.7
            return 0.7

    # ─── Reason Generators ──────────────────────────────────────────────────

    @staticmethod
    def _reason_liquidity(liquidity: float | None, score: float) -> str:
        if liquidity is None:
            return "Liquidity: no data (penalized)"
        return f"Liquidity: ${liquidity:,.0f} (score: {score:.0%})"

    @staticmethod
    def _reason_volume(volume: float | None, score: float) -> str:
        if volume is None:
            return "Volume 24h: no data (penalized)"
        return f"Volume 24h: ${volume:,.0f} (score: {score:.0%})"

    @staticmethod
    def _reason_buy_pressure(
        buys: int | None, sells: int | None, score: float
    ) -> str:
        if buys is None or sells is None:
            return "Buy pressure: no data (penalized)"
        ratio = buys / sells if sells > 0 else float("inf")
        return f"Buy pressure: {buys}B/{sells}S ratio={ratio:.1f} (score: {score:.0%})"

    @staticmethod
    def _reason_token_age(created_at: datetime | None, score: float) -> str:
        if created_at is None:
            return "Token age: unknown (penalized)"
        now = datetime.now(tz=UTC)
        age_hours = (now - created_at).total_seconds() / 3600
        if age_hours < 48:
            return f"Token age: {age_hours:.0f}h old (score: {score:.0%})"
        days = age_hours / 24
        return f"Token age: {days:.1f}d old (score: {score:.0%})"

    @staticmethod
    def _reason_social_presence(
        website: str | None,
        twitter: str | None,
        telegram: str | None,
        score: float,
    ) -> str:
        links = []
        if website:
            links.append("website")
        if twitter:
            links.append("twitter")
        if telegram:
            links.append("telegram")
        if not links:
            return "Social: none found (penalized)"
        return f"Social: {', '.join(links)} (score: {score:.0%})"

    @staticmethod
    def _reason_price_trend(
        change_1h: float | None, change_24h: float | None, score: float
    ) -> str:
        change = change_1h if change_1h is not None else change_24h
        if change is None:
            return "Price trend: no data (penalized)"
        period = "1h" if change_1h is not None else "24h"
        direction = "+" if change >= 0 else ""
        return f"Price trend: {direction}{change:.1f}% ({period}) (score: {score:.0%})"
