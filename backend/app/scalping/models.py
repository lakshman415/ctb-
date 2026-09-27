"""
Plain data types for the scalping slice.

Deliberately dependency-free (stdlib dataclasses) so the store, client,
level detection and backtest can all share them without pulling in ORM or
pydantic. A DB-backed Candle model can wrap this later without changing callers.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class Candle:
    """
    One OHLCV bar.

    `ts` is the bar's open time as a unix epoch (seconds, UTC). GeckoTerminal
    emits a bar only for periods that actually traded, so consecutive candles
    are NOT guaranteed to be one interval apart. Treat the series as sparse.
    """

    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def dt(self) -> datetime:
        return datetime.fromtimestamp(self.ts, tz=UTC)

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Candle":
        return cls(
            ts=int(d["ts"]),
            open=float(d["open"]),
            high=float(d["high"]),
            low=float(d["low"]),
            close=float(d["close"]),
            volume=float(d["volume"]),
        )

    @classmethod
    def from_geckoterminal_row(cls, row: list[float]) -> "Candle":
        """
        Parse one GeckoTerminal OHLCV list entry.

        GeckoTerminal order is: [timestamp, open, high, low, close, volume].
        """
        return cls(
            ts=int(row[0]),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
        )
