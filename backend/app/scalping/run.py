"""
Phase-1 runner: backfill -> analyze -> backtest -> report.

Usage (from backend/, venv active):

  # pull history to a local file, then analyze + backtest
  python -m app.scalping.run --backfill --max-bars 6000

  # re-use whatever is already stored (no network)
  python -m app.scalping.run

  # tune the round-trip cost assumption
  python -m app.scalping.run --cost 3.0

Defaults target the INU/AAPL bankr-robinhood pool.
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from app.scalping.backtest import BacktestConfig, run_backtest
from app.scalping.client import GeckoTerminalClient
from app.scalping.levels import detect_zones, nearest_zones
from app.scalping.models import Candle
from app.scalping.store import CandleStore
from app.scalping.volume_profile import compute_volume_profile, compute_vwap

# INU / AAPL on bankr-robinhood (deepest active pool for this token)
DEFAULT_NETWORK = "robinhood"
DEFAULT_POOL = "0x7e271c400427ecb727f5fbb27dec69254bce7c4219e95e3535d0ed128f79648a"
DEFAULT_TIMEFRAME = "1m"


def _fmt(p: float) -> str:
    return f"{p:.8f}".rstrip("0").rstrip(".")


async def backfill(store: CandleStore, network: str, pool: str, timeframe: str, max_bars: int) -> list[Candle]:
    async with GeckoTerminalClient() as client:
        history = await client.fetch_ohlcv_history(
            network, pool, timeframe=timeframe, max_bars=max_bars
        )
    if not history:
        print("Backfill returned no candles.")
        return store.load()
    merged = store.merge(history)
    print(f"Backfill: fetched {len(history)}, store now holds {len(merged)} candles.")
    return merged


def report_analysis(candles: list[Candle]) -> None:
    if len(candles) < 10:
        print("Not enough candles to analyze.")
        return

    first, last = candles[0], candles[-1]
    span_hours = (last.ts - first.ts) / 3600
    print("\n=== DATA ===")
    print(f"Candles: {len(candles)}  spanning {span_hours:.1f}h")
    print(f"First: {first.dt.isoformat()}  Last: {last.dt.isoformat()}")
    print(f"Last price: {_fmt(last.close)}")

    zones = detect_zones(candles)
    support, resistance = nearest_zones(zones, last.close)
    print("\n=== LEVELS (top zones by score) ===")
    for z in sorted(zones, key=lambda z: z.score, reverse=True)[:8]:
        marker = ""
        if support and z is support:
            marker = "  <- nearest support"
        if resistance and z is resistance:
            marker = "  <- nearest resistance"
        print(
            f"  {z.kind:10s} {_fmt(z.low)}–{_fmt(z.high)}  "
            f"touches={z.touches} score={z.score}{marker}"
        )

    profile = compute_volume_profile(candles)
    if profile:
        print("\n=== VOLUME PROFILE ===")
        print(f"  POC: {_fmt(profile.poc)}")
        print(f"  Value area: {_fmt(profile.value_area_low)} – {_fmt(profile.value_area_high)}")

    vwap = compute_vwap(candles)
    if vwap:
        print("\n=== VWAP ===")
        print(f"  VWAP: {_fmt(vwap.vwap)}")
        print(f"  +/-1sd: {_fmt(vwap.lower_1sd)} – {_fmt(vwap.upper_1sd)}")


def report_backtest(candles: list[Candle], cost: float) -> None:
    cfg = BacktestConfig(round_trip_cost_pct=cost)
    # If we don't have many candles, shrink the lookback so trades can form.
    if len(candles) < cfg.lookback + 50:
        cfg.lookback = max(50, len(candles) // 3)
    result = run_backtest(candles, cfg)
    print("\n=== BACKTEST (support-bounce / resistance-target, long-only) ===")
    print(f"(lookback={cfg.lookback} bars, max_hold={cfg.max_hold_bars} bars)")
    print(result.summary())


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase-1 scalping analysis + backtest")
    parser.add_argument("--backfill", action="store_true", help="fetch fresh candles first")
    parser.add_argument("--max-bars", type=int, default=6000)
    parser.add_argument("--cost", type=float, default=4.0, help="round-trip cost %% per trade")
    parser.add_argument("--network", default=DEFAULT_NETWORK)
    parser.add_argument("--pool", default=DEFAULT_POOL)
    parser.add_argument("--timeframe", default=DEFAULT_TIMEFRAME)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    store = CandleStore(args.network, args.pool, args.timeframe)

    if args.backfill:
        candles = asyncio.run(
            backfill(store, args.network, args.pool, args.timeframe, args.max_bars)
        )
    else:
        candles = store.load()
        if not candles:
            print("No stored candles. Run with --backfill first.")
            return
        print(f"Loaded {len(candles)} candles from {store.path}")

    report_analysis(candles)
    report_backtest(candles, args.cost)


if __name__ == "__main__":
    main()
