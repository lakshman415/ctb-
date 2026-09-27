"""
Alert evaluation service.

Runs after each scan: compares watched tokens against their alert thresholds
and marks alerts as triggered when conditions are met.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.watchlist import Alert, WatchlistItem
from app.schemas.scanner import RankedTokenResponse

logger = logging.getLogger(__name__)

# Maps alert metric names to RankedTokenResponse attributes
METRIC_MAP = {
    "market_cap": "market_cap",
    "price": "price",
    "volume_24h": "volume_24h",
    "liquidity": "liquidity",
    "price_change_1h": "price_change_1h",
    "price_change_24h": "price_change_24h",
    "buy_sell_ratio": "buy_sell_ratio",
}


class AlertService:
    """Evaluates alerts against fresh market data."""

    def __init__(self, db: Session):
        self._db = db

    def evaluate(self, tokens: list[RankedTokenResponse]) -> int:
        """
        Check all enabled, untriggered alerts against the latest token data.

        Args:
            tokens: Freshly scanned tokens with current metrics.

        Returns:
            Number of alerts newly triggered.
        """
        # Build a lookup: (chain, token_address) -> token data
        lookup: dict[tuple[str, str], RankedTokenResponse] = {}
        for t in tokens:
            lookup[(t.chain, t.token_address.lower())] = t

        alerts = (
            self._db.query(Alert)
            .filter(Alert.enabled.is_(True), Alert.triggered.is_(False))
            .all()
        )

        fired = 0
        for alert in alerts:
            item: WatchlistItem | None = alert.watchlist_item
            if item is None:
                continue

            token = lookup.get((item.chain, item.token_address.lower()))
            if token is None:
                continue  # Token not in this scan

            attr = METRIC_MAP.get(alert.metric)
            if attr is None:
                continue

            current = getattr(token, attr, None)
            if current is None:
                continue

            hit = (
                (alert.condition == "above" and current > alert.threshold)
                or (alert.condition == "below" and current < alert.threshold)
            )

            if hit:
                alert.triggered = True
                alert.triggered_at = datetime.now(tz=UTC)
                alert.triggered_value = float(current)
                fired += 1
                logger.info(
                    f"ALERT: {item.symbol} {alert.metric} {alert.condition} "
                    f"{alert.threshold} (now {current})"
                )

        if fired:
            self._db.commit()

        return fired
