"""
Movement / choppiness analysis from candles.

A good scalp candidate needs two things at once:
  1. enough MOVEMENT to make a trade worth the cost (range, not a flat coin), and
  2. that movement should OSCILLATE rather than TREND -- mean-reversion needs
     price to come back, not run away.

These pull in opposite directions from a naive "avoid volatility" filter, which
is exactly the mistake that let PEPE (deep, inert) rank above swingier tokens.

Metrics (all computed from real candles):
  - avg_range_pct: mean (high-low)/close per bar -> raw wiggle per minute.
  - path_pct: sum of |close-to-close| moves -> total distance travelled.
  - net_drift_pct: |last close - first close| / first close -> net direction.
  - chop_ratio: path / net_drift. High = oscillates a lot for little net move
    (ranging, good). ~1 = straight-line trend (bad for mean-reversion).
  - directionality: net_drift / path, 0..1. Low = choppy, high = trending.

`is_scalp_worthy` combines a movement floor with a choppiness requirement.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.scalping.models import Candle


@dataclass
class MovementProfile:
    avg_range_pct: float
    path_pct: float
    net_drift_pct: float
    chop_ratio: float
    directionality: float
    bars: int

    def is_scalp_worthy(
        self,
        *,
        min_avg_range_pct: float = 0.25,
        max_directionality: float = 0.15,
    ) -> bool:
        """
        Worthy if bars move enough AND price oscillates rather than trends.

        min_avg_range_pct: each bar must, on average, swing at least this % --
            enough room for a scalp to clear costs.
        max_directionality: net drift may be at most this fraction of total
            path -- i.e. most of the movement cancels out (ranging).
        """
        return (
            self.avg_range_pct >= min_avg_range_pct
            and self.directionality <= max_directionality
        )


def analyze_movement(candles: list[Candle]) -> MovementProfile | None:
    traded = [c for c in candles if c.close > 0]
    if len(traded) < 30:
        return None

    range_pcts = [
        (c.high - c.low) / c.close * 100.0 for c in traded if c.close > 0
    ]
    avg_range = sum(range_pcts) / len(range_pcts) if range_pcts else 0.0

    path = 0.0
    for a, b in zip(traded, traded[1:]):
        if a.close > 0:
            path += abs(b.close - a.close) / a.close * 100.0

    first, last = traded[0].close, traded[-1].close
    net_drift = abs(last - first) / first * 100.0 if first > 0 else 0.0

    chop = path / net_drift if net_drift > 1e-9 else float("inf")
    directionality = net_drift / path if path > 1e-9 else 1.0

    return MovementProfile(
        avg_range_pct=round(avg_range, 4),
        path_pct=round(path, 2),
        net_drift_pct=round(net_drift, 2),
        chop_ratio=round(chop, 2) if chop != float("inf") else 9999.0,
        directionality=round(directionality, 4),
        bars=len(traded),
    )
