"""
Volume profile and VWAP from real candles.

These are the "volume zones" that could not be computed from the aggregate
volume buckets in the snapshots table. Here volume is attributed to the price
at which it traded (using each bar's typical price), producing:

  - a volume-by-price histogram
  - POC (point of control): the price bin with the most volume
  - value area (VAH/VAL): the contiguous band around the POC holding ~70%
    of total volume
  - session VWAP with standard-deviation bands

Each bar's volume is assigned to a single bin at its typical price
(H+L+C)/3. That is an approximation -- a bar spans a range -- but with 1m bars
on a thin pool the per-bar range is small and this stays close enough to be
useful. A tick/swap feed would let us distribute volume across the bar's range.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.scalping.models import Candle


@dataclass
class VolumeProfile:
    poc: float
    value_area_low: float
    value_area_high: float
    bins: list[tuple[float, float]]  # (bin_center_price, volume)
    total_volume: float

    def in_value_area(self, price: float) -> bool:
        return self.value_area_low <= price <= self.value_area_high


@dataclass
class VWAPResult:
    vwap: float
    upper_1sd: float
    lower_1sd: float
    upper_2sd: float
    lower_2sd: float


def _typical_price(c: Candle) -> float:
    return (c.high + c.low + c.close) / 3.0


def compute_volume_profile(
    candles: list[Candle], *, bins: int = 50, value_area_pct: float = 0.70
) -> VolumeProfile | None:
    """
    Build a volume-by-price profile.

    Args:
        bins: number of price buckets between the series low and high.
        value_area_pct: fraction of total volume that defines the value area.
    """
    traded = [c for c in candles if c.volume > 0]
    if len(traded) < 2:
        return None

    lo = min(c.low for c in traded)
    hi = max(c.high for c in traded)
    if hi <= lo:
        return None

    width = (hi - lo) / bins
    volumes = [0.0] * bins

    for c in traded:
        tp = _typical_price(c)
        idx = int((tp - lo) / width)
        idx = min(max(idx, 0), bins - 1)
        volumes[idx] += c.volume

    total = sum(volumes)
    if total <= 0:
        return None

    poc_idx = max(range(bins), key=lambda i: volumes[i])
    poc_price = lo + (poc_idx + 0.5) * width

    # Grow a window outward from the POC until it holds value_area_pct of volume.
    target = total * value_area_pct
    lo_idx = hi_idx = poc_idx
    captured = volumes[poc_idx]
    while captured < target and (lo_idx > 0 or hi_idx < bins - 1):
        left_vol = volumes[lo_idx - 1] if lo_idx > 0 else -1.0
        right_vol = volumes[hi_idx + 1] if hi_idx < bins - 1 else -1.0
        if right_vol >= left_vol:
            hi_idx += 1
            captured += max(right_vol, 0.0)
        else:
            lo_idx -= 1
            captured += max(left_vol, 0.0)

    val = lo + lo_idx * width
    vah = lo + (hi_idx + 1) * width

    bin_pairs = [(lo + (i + 0.5) * width, volumes[i]) for i in range(bins)]

    return VolumeProfile(
        poc=poc_price,
        value_area_low=val,
        value_area_high=vah,
        bins=bin_pairs,
        total_volume=total,
    )


def compute_vwap(candles: list[Candle]) -> VWAPResult | None:
    """
    Volume-weighted average price with 1 and 2 standard-deviation bands.

    Bands use the volume-weighted variance of typical price around VWAP.
    """
    traded = [c for c in candles if c.volume > 0]
    if len(traded) < 2:
        return None

    vol_sum = sum(c.volume for c in traded)
    if vol_sum <= 0:
        return None

    vwap = sum(_typical_price(c) * c.volume for c in traded) / vol_sum
    variance = sum(c.volume * (_typical_price(c) - vwap) ** 2 for c in traded) / vol_sum
    sd = math.sqrt(max(variance, 0.0))

    return VWAPResult(
        vwap=vwap,
        upper_1sd=vwap + sd,
        lower_1sd=vwap - sd,
        upper_2sd=vwap + 2 * sd,
        lower_2sd=vwap - 2 * sd,
    )
