"""
Backtest harness for the support/resistance scalping rules.

Purpose: answer one question with numbers, not opinion -- does the rule set
have positive expectancy on this pair once a realistic round-trip cost is
subtracted?

Method (long-only, one position at a time, walk-forward):
  * Rebuild support/resistance zones from a rolling lookback window as we
    step through the candles, so the backtest never sees the future.
  * ENTRY: price dips into a support zone and the bar closes back above the
    zone high (a rejection/bounce), with bar volume above the recent average.
  * STOP: below the support zone's low (invalidation).
  * TARGET: the next resistance zone above entry (fallback: fixed R multiple).
  * EXIT also on stop hit, target hit, or max-hold timeout.
  * COST: round_trip_cost_pct subtracted from every trade's gross return to
    account for LP fees + slippage on entry and exit combined.

The rules are deliberately simple. If they can't clear costs, a more elaborate
rule set on the same thin pool almost certainly can't either.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from app.scalping.levels import detect_zones, nearest_zones
from app.scalping.models import Candle


@dataclass
class Trade:
    entry_ts: int
    entry_price: float
    exit_ts: int
    exit_price: float
    gross_return_pct: float
    net_return_pct: float
    reason: str  # "target" | "stop" | "timeout"


@dataclass
class BacktestConfig:
    lookback: int = 300          # bars used to build zones at each step
    rebuild_every: int = 15      # recompute zones every N bars (speed)
    left: int = 3
    right: int = 3
    cluster_pct: float = 0.6
    vol_avg_window: int = 20     # bars for the volume-average entry filter
    vol_multiple: float = 1.2    # entry needs volume >= this * recent average
    max_hold_bars: int = 60      # timeout exit
    round_trip_cost_pct: float = 4.0   # LP fee + slippage, both sides combined
    fallback_r_multiple: float = 1.5   # target when no resistance zone exists


@dataclass
class BacktestResult:
    trades: list[Trade] = field(default_factory=list)
    round_trip_cost_pct: float = 0.0

    @property
    def n(self) -> int:
        return len(self.trades)

    @property
    def wins(self) -> list[Trade]:
        return [t for t in self.trades if t.net_return_pct > 0]

    @property
    def losses(self) -> list[Trade]:
        return [t for t in self.trades if t.net_return_pct <= 0]

    @property
    def win_rate(self) -> float:
        return len(self.wins) / self.n if self.n else 0.0

    @property
    def avg_win_pct(self) -> float:
        return statistics.mean(t.net_return_pct for t in self.wins) if self.wins else 0.0

    @property
    def avg_loss_pct(self) -> float:
        return statistics.mean(t.net_return_pct for t in self.losses) if self.losses else 0.0

    @property
    def expectancy_pct(self) -> float:
        """Average net return per trade. This is the number the gate turns on."""
        return statistics.mean(t.net_return_pct for t in self.trades) if self.trades else 0.0

    @property
    def total_net_pct(self) -> float:
        """Sum of net returns (naive, non-compounded)."""
        return sum(t.net_return_pct for t in self.trades)

    @property
    def exit_reasons(self) -> dict[str, int]:
        """Count of how trades closed: stop / target / timeout.

        A near-100% 'stop' share means the exits are too tight -- the strategy
        is being knocked out before targets are reached. That's a rules problem,
        not a token problem.
        """
        counts = {"stop": 0, "target": 0, "timeout": 0}
        for t in self.trades:
            counts[t.reason] = counts.get(t.reason, 0) + 1
        return counts

    def summary(self) -> str:
        if not self.trades:
            return (
                "No trades were triggered. Either the rules never fired on this "
                "history, or there isn't enough of it. Nothing to conclude yet."
            )
        exp = self.expectancy_pct
        verdict = (
            "POSITIVE expectancy -- worth pursuing an execution layer."
            if exp > 0
            else "NEGATIVE expectancy -- do NOT build execution against this as-is."
        )
        return (
            f"Trades: {self.n}\n"
            f"Win rate: {self.win_rate * 100:.1f}%\n"
            f"Avg win: {self.avg_win_pct:+.2f}%   Avg loss: {self.avg_loss_pct:+.2f}%\n"
            f"Round-trip cost applied: {self.round_trip_cost_pct:.2f}% per trade\n"
            f"Expectancy (avg net/trade): {exp:+.3f}%\n"
            f"Total net (non-compounded): {self.total_net_pct:+.2f}%\n"
            f"Exit reasons: {self.exit_reasons}\n"
            f"Verdict: {verdict}"
        )


def run_backtest(candles: list[Candle], config: BacktestConfig | None = None) -> BacktestResult:
    cfg = config or BacktestConfig()
    result = BacktestResult(round_trip_cost_pct=cfg.round_trip_cost_pct)

    n = len(candles)
    if n < cfg.lookback + 10:
        return result

    zones: list = []
    i = cfg.lookback
    in_position = False
    entry_price = entry_ts = 0.0
    stop_price = target_price = 0.0
    bars_held = 0

    while i < n:
        bar = candles[i]

        # Refresh zones periodically from the trailing window (no lookahead).
        if not in_position and (i % cfg.rebuild_every == 0 or not zones):
            window = candles[i - cfg.lookback : i]
            zones = detect_zones(
                window,
                left=cfg.left,
                right=cfg.right,
                cluster_pct=cfg.cluster_pct,
            )

        if in_position:
            bars_held += 1
            # Stop takes priority (worst case within the bar).
            if bar.low <= stop_price:
                result.trades.append(_close(entry_ts, entry_price, bar.ts, stop_price, cfg, "stop"))
                in_position = False
            elif bar.high >= target_price:
                result.trades.append(_close(entry_ts, entry_price, bar.ts, target_price, cfg, "target"))
                in_position = False
            elif bars_held >= cfg.max_hold_bars:
                result.trades.append(_close(entry_ts, entry_price, bar.ts, bar.close, cfg, "timeout"))
                in_position = False
            i += 1
            continue

        # --- Entry evaluation (flat) ---
        support, resistance = nearest_zones(zones, bar.close)
        if support is not None and _is_bounce(bar, support) and _volume_ok(candles, i, cfg):
            entry_price = bar.close
            entry_ts = bar.ts
            stop_price = support.low * (1 - 0.001)  # just below invalidation
            risk = entry_price - stop_price
            if risk <= 0:
                i += 1
                continue
            if resistance is not None and resistance.low > entry_price:
                target_price = resistance.low
            else:
                target_price = entry_price + cfg.fallback_r_multiple * risk
            in_position = True
            bars_held = 0

        i += 1

    return result


def _is_bounce(bar: Candle, support) -> bool:
    """Bar wicked into the support zone but closed back above it."""
    dipped_in = bar.low <= support.high
    closed_above = bar.close > support.high
    return dipped_in and closed_above


def _volume_ok(candles: list[Candle], i: int, cfg: BacktestConfig) -> bool:
    start = max(0, i - cfg.vol_avg_window)
    window = candles[start:i]
    if not window:
        return False
    avg = statistics.mean(c.volume for c in window)
    if avg <= 0:
        return False
    return candles[i].volume >= cfg.vol_multiple * avg


def _close(
    entry_ts: float,
    entry_price: float,
    exit_ts: int,
    exit_price: float,
    cfg: BacktestConfig,
    reason: str,
) -> Trade:
    gross = (exit_price - entry_price) / entry_price * 100.0
    net = gross - cfg.round_trip_cost_pct
    return Trade(
        entry_ts=int(entry_ts),
        entry_price=entry_price,
        exit_ts=int(exit_ts),
        exit_price=exit_price,
        gross_return_pct=round(gross, 4),
        net_return_pct=round(net, 4),
        reason=reason,
    )
