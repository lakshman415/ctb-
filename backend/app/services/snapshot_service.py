"""
Snapshot service.

Handles the creation and retrieval of point-in-time market snapshots.
Ensures snapshots are always appended (never overwritten) to preserve history.
"""

import logging
from datetime import datetime

from app.models.snapshot import Snapshot
from app.repositories.snapshot_repository import SnapshotRepository
from app.schemas.snapshot import SnapshotBase

logger = logging.getLogger(__name__)


class SnapshotService:
    """Manages snapshot lifecycle — creation and historical lookups."""

    def __init__(self, snapshot_repo: SnapshotRepository):
        """
        Args:
            snapshot_repo: Snapshot data access layer.
        """
        self._snapshot_repo = snapshot_repo

    def create_snapshot(self, token_id: int, data: SnapshotBase) -> Snapshot:
        """
        Persist a new market data snapshot for a token.

        Snapshots are append-only — never updates existing records.

        Args:
            token_id: The token this snapshot belongs to.
            data: Snapshot market data (price, volume, buys, sells, etc.).

        Returns:
            The persisted Snapshot record with id and timestamp populated.
        """
        snapshot = Snapshot(
            token_id=token_id,
            price=data.price,
            volume_5m=data.volume_5m,
            volume_1h=data.volume_1h,
            volume_6h=data.volume_6h,
            volume_24h=data.volume_24h,
            buys=data.buys,
            sells=data.sells,
            price_change_5m=data.price_change_5m,
            price_change_1h=data.price_change_1h,
            price_change_6h=data.price_change_6h,
            price_change_24h=data.price_change_24h,
            liquidity=data.liquidity,
        )

        created = self._snapshot_repo.create(snapshot)
        logger.debug(f"Created snapshot for token_id={token_id}, price={data.price}")
        return created

    def get_token_history(
        self,
        token_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 100,
    ) -> list[Snapshot]:
        """
        Retrieve historical snapshots for a token.

        Args:
            token_id: Target token.
            start: Optional start of time range.
            end: Optional end of time range.
            limit: Max records to return.

        Returns:
            List of snapshots ordered by timestamp (most recent first).
        """
        if start is not None and end is not None:
            return self._snapshot_repo.get_in_time_range(token_id, start, end)
        return self._snapshot_repo.get_by_token_id(token_id, limit=limit)

    def get_latest_snapshot(self, token_id: int) -> Snapshot | None:
        """Get the most recent snapshot for a token."""
        return self._snapshot_repo.get_latest_by_token_id(token_id)
