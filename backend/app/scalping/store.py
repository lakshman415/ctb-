"""
Local-file candle store.

Phase-1 persistence: candles for one pool/timeframe live in a single JSON
file under a data directory. No database. The store dedupes by timestamp and
keeps candles sorted, so re-running the backfill merges cleanly rather than
duplicating bars.

File layout:
  data/candles/<network>_<pool>_<timeframe>.json
  {
    "network": ..., "pool_address": ..., "timeframe": ...,
    "updated_at": <iso8601>,
    "candles": [ {ts, open, high, low, close, volume}, ... ]  # ascending
  }
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from app.scalping.models import Candle

logger = logging.getLogger(__name__)

# backend/data/candles
_DEFAULT_DIR = Path(__file__).resolve().parents[2] / "data" / "candles"


class CandleStore:
    """Reads and writes candle history to a local JSON file."""

    def __init__(
        self,
        network: str,
        pool_address: str,
        timeframe: str = "1m",
        *,
        base_dir: Path | None = None,
    ) -> None:
        self.network = network
        self.pool_address = pool_address
        self.timeframe = timeframe
        self._dir = base_dir or _DEFAULT_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        safe_pool = self.pool_address.lower()
        return self._dir / f"{self.network}_{safe_pool}_{self.timeframe}.json"

    def load(self) -> list[Candle]:
        """Load stored candles ascending by timestamp; empty list if none."""
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        candles = [Candle.from_dict(c) for c in payload.get("candles", [])]
        candles.sort(key=lambda c: c.ts)
        return candles

    def save(self, candles: list[Candle]) -> Path:
        """Overwrite the file with the given candles (sorted, de-duplicated)."""
        merged = self._dedupe_sort(candles)
        payload = {
            "network": self.network,
            "pool_address": self.pool_address,
            "timeframe": self.timeframe,
            "updated_at": datetime.now(tz=UTC).isoformat(),
            "candle_count": len(merged),
            "candles": [c.to_dict() for c in merged],
        }
        tmp = self.path.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        tmp.replace(self.path)  # atomic on same filesystem
        logger.info("saved %s candles to %s", len(merged), self.path)
        return self.path

    def merge(self, new_candles: list[Candle]) -> list[Candle]:
        """Merge new candles with what's on disk, persist, and return the result."""
        combined = self.load() + list(new_candles)
        merged = self._dedupe_sort(combined)
        self.save(merged)
        return merged

    @staticmethod
    def _dedupe_sort(candles: list[Candle]) -> list[Candle]:
        by_ts: dict[int, Candle] = {c.ts: c for c in candles}
        return sorted(by_ts.values(), key=lambda c: c.ts)
