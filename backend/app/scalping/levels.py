"""
Support/resistance level detection from real candles.

Replaces the invented-range Fibonacci estimate in analysis_service.py. Here
levels come from actual swing pivots in the candle series, clustered into
zones and scored by how many times price touched them, how much volume
transacted near them, and how recent the touches are.

The candle series is SPARSE (GeckoTerminal drops untraded minutes), so pivots
are detected by position in the series, not by wall-clock spacing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.scalping.models import Candle


@dataclass
class Zone:
    """A support or resistance zone: a price band, not a single line."""

    kind: str  # "support" | "resistance"
    center: float
    low: float
    high: float
    touches: int
    volume: float
    last_touch_ts: int
    score: float = 0.0
    touch_ts: list[int] = field(default_factory=list)

    def contains(self, price: float) -> bool:
        return self.low <= price <= self.high


def find_swing_pivots(
    candles: list[Candle], *, left: int = 3, right: int = 3
) -> tuple[list[int], list[int]]:
    """
    Find swing-high and swing-low indices.

    A swing high at index i has a high strictly greater than the `left` bars
    before and `right` bars after it (>= on ties to avoid duplicate flags).
    Returns (high_indices, low_indices) into `candles`.
    """
    highs: list[int] = []
    lows: list[int] = []
    n = len(candles)
    for i in range(left, n - right):
        window = candles[i - left : i + right + 1]
        pivot = candles[i]
        if pivot.high >= max(c.high for c in window) and _strictly_dominant(
            [c.high for c in window], pivot.high
        ):
            highs.append(i)
        if pivot.low <= min(c.low for c in window) and _strictly_dominant(
            [-c.low for c in window], -pivot.low
        ):
            lows.append(i)
    return highs, lows


def _strictly_dominant(values: list[float], pivot: float) -> bool:
    """True if pivot is the unique maximum in values (guards flat windows)."""
    return sum(1 for v in values if v >= pivot) == 1


def detect_zones(
    candles: list[Candle],
    *,
    left: int = 3,
    right: int = 3,
    cluster_pct: float = 0.6,
    max_zones_per_side: int = 6,
) -> list[Zone]:
    """
    Detect support/resistance zones from swing pivots.

    Args:
        cluster_pct: pivots within this percent of each other merge into one zone.
        max_zones_per_side: cap on returned zones per side (by score).

    Returns zones sorted by score descending.
    """
    if len(candles) < left + right + 1:
        return []

    high_idx, low_idx = find_swing_pivots(candles, left=left, right=right)

    res_pivots = [(candles[i].high, i) for i in high_idx]
    sup_pivots = [(candles[i].low, i) for i in low_idx]

    resistance = _cluster_pivots(candles, res_pivots, "resistance", cluster_pct)
    support = _cluster_pivots(candles, sup_pivots, "support", cluster_pct)

    _score_zones(resistance, candles)
    _score_zones(support, candles)

    resistance.sort(key=lambda z: z.score, reverse=True)
    support.sort(key=lambda z: z.score, reverse=True)

    return resistance[:max_zones_per_side] + support[:max_zones_per_side]


def _cluster_pivots(
    candles: list[Candle],
    pivots: list[tuple[float, int]],
    kind: str,
    cluster_pct: float,
) -> list[Zone]:
    """Merge nearby pivot prices into zones."""
    if not pivots:
        return []

    pivots = sorted(pivots, key=lambda p: p[0])
    zones: list[Zone] = []
    band = cluster_pct / 100.0

    cluster: list[tuple[float, int]] = [pivots[0]]
    for price, idx in pivots[1:]:
        anchor = cluster[0][0]
        if anchor > 0 and abs(price - anchor) / anchor <= band:
            cluster.append((price, idx))
        else:
            zones.append(_zone_from_cluster(candles, cluster, kind))
            cluster = [(price, idx)]
    zones.append(_zone_from_cluster(candles, cluster, kind))
    return zones


def _zone_from_cluster(
    candles: list[Candle], cluster: list[tuple[float, int]], kind: str
) -> Zone:
    prices = [p for p, _ in cluster]
    idxs = [i for _, i in cluster]
    center = sum(prices) / len(prices)
    # Volume near a pivot = the pivot bar's own volume (proxy for interest there).
    volume = sum(candles[i].volume for i in idxs)
    touch_ts = sorted(candles[i].ts for i in idxs)
    return Zone(
        kind=kind,
        center=center,
        low=min(prices),
        high=max(prices),
        touches=len(cluster),
        volume=volume,
        last_touch_ts=max(touch_ts),
        touch_ts=touch_ts,
    )


def _score_zones(zones: list[Zone], candles: list[Candle]) -> None:
    """
    Score = touches * volume_weight * recency_weight.

    Normalised so the numbers are comparable across zones on the same pair.
    A level tested many times, on heavy volume, recently, scores highest.
    """
    if not zones or not candles:
        return

    newest_ts = candles[-1].ts
    oldest_ts = candles[0].ts
    span = max(newest_ts - oldest_ts, 1)
    max_vol = max((z.volume for z in zones), default=1.0) or 1.0

    for z in zones:
        vol_weight = z.volume / max_vol  # 0..1
        recency = (z.last_touch_ts - oldest_ts) / span  # 0..1, newer = higher
        z.score = round(z.touches * (0.4 + 0.6 * vol_weight) * (0.5 + 0.5 * recency), 4)


def nearest_zones(
    zones: list[Zone], price: float
) -> tuple[Zone | None, Zone | None]:
    """Return (nearest support below price, nearest resistance above price)."""
    supports = [z for z in zones if z.kind == "support" and z.high < price]
    resistances = [z for z in zones if z.kind == "resistance" and z.low > price]
    support = max(supports, key=lambda z: z.center, default=None)
    resistance = min(resistances, key=lambda z: z.center, default=None)
    return support, resistance
