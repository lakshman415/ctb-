"""
Screener CLI: discover the most scalp-suitable token from live data, then
prove it with a candle backtest.

Usage (from backend/, venv active):

  # full screen across default chains
  python -m app.scalping.screen

  # wider net, more history, don't write candle files
  python -m app.scalping.screen --chains solana base ethereum --max-bars 4000 --no-persist

  # loosen the coarse filter if the funnel is too tight
  python -m app.scalping.screen --min-liq 80000 --min-vol 150000 --candidates 20
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from app.scalping.backtest import BacktestConfig
from app.scalping.screener import (
    MIN_TRADES_FOR_CONFIDENCE,
    ScalpScreenConfig,
    ScreenedToken,
    run_screen,
)


def _print_table(tokens: list[ScreenedToken]) -> None:
    if not tokens:
        print("\nNo tokens produced any trades. Try loosening the filter "
              "(--min-liq / --min-vol) or widening --chains.")
        return

    print("\n" + "=" * 92)
    print("SCALP SCREEN RESULTS (ranked by confidence-adjusted expectancy)")
    print("=" * 92)
    header = (
        f"{'#':>2}  {'SYMBOL':<10} {'CHAIN':<9} {'LIQ($)':>11} {'RNG%':>5} "
        f"{'DIR':>5} {'TRADES':>6} {'WIN%':>6} {'COST%':>6} {'EXP%':>8} {'CONF':>5}"
    )
    print(header)
    print("-" * 100)
    for i, t in enumerate(tokens, 1):
        conf = "yes" if t.has_confidence else "LOW"
        print(
            f"{i:>2}  {t.symbol[:10]:<10} {t.chain:<9} {t.liquidity_usd:>11,.0f} "
            f"{t.movement.avg_range_pct:>5.2f} {t.movement.directionality:>5.2f} "
            f"{t.result.n:>6} {t.result.win_rate*100:>5.1f} "
            f"{t.round_trip_cost_pct:>6.1f} {t.expectancy:>+8.3f} {conf:>5}"
        )
    print("-" * 100)

    # Winner = best rank_score that also has enough trades to be trusted.
    trusted = [t for t in tokens if t.has_confidence]
    best = trusted[0] if trusted else None

    if best is None:
        print(
            f"\nNo token cleared {MIN_TRADES_FOR_CONFIDENCE}+ trades AND positive "
            "expectancy. The top rows are low-confidence — not a green light."
        )
        return

    if best.expectancy <= 0:
        print(
            f"\nBest trustworthy token is {best.symbol} but its expectancy is "
            f"{best.expectancy:+.3f}% — still negative net of costs. No token here "
            "is worth trading with this rule set."
        )
        return

    print(f"\nWINNER: {best.symbol} on {best.chain}")
    print(f"  pool: {best.pair_address}  (GT network: {best.gt_network})")
    print(f"  liquidity: ${best.liquidity_usd:,.0f}   24h vol: ${best.volume_24h_usd:,.0f}")
    print(f"  candles backtested: {best.candle_count}")
    print("  " + best.result.summary().replace("\n", "\n  "))


def main() -> None:
    p = argparse.ArgumentParser(description="Scalp-suitability screen + backtest")
    p.add_argument("--chains", nargs="+", default=["solana", "base", "ethereum"])
    p.add_argument("--min-liq", type=float, default=300_000.0)
    p.add_argument("--max-liq", type=float, default=8_000_000.0)
    p.add_argument("--min-vol", type=float, default=300_000.0)
    p.add_argument("--min-range", type=float, default=0.25,
                   help="min avg per-bar high-low swing %% (movement floor)")
    p.add_argument("--max-dir", type=float, default=0.20,
                   help="max directionality 0..1 (lower = choppier, less trend)")
    p.add_argument("--candidates", type=int, default=12)
    p.add_argument("--max-bars", type=int, default=3000)
    p.add_argument("--no-persist", action="store_true", help="don't write candle files")
    p.add_argument(
        "--insecure",
        action="store_true",
        help="disable TLS verification (for corporate proxies that intercept SSL)",
    )
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    scfg = ScalpScreenConfig(
        min_liquidity_usd=args.min_liq,
        max_liquidity_usd=args.max_liq,
        min_volume_24h_usd=args.min_vol,
        min_avg_range_pct=args.min_range,
        max_directionality=args.max_dir,
        max_candidates_to_backtest=args.candidates,
        chains=tuple(args.chains),
        verify_ssl=not args.insecure,
    )
    tokens = asyncio.run(
        run_screen(
            screen_cfg=scfg,
            backtest_cfg=BacktestConfig(),
            max_bars=args.max_bars,
            persist=not args.no_persist,
        )
    )
    _print_table(tokens)


if __name__ == "__main__":
    main()
