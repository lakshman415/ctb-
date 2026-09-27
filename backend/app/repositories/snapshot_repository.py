"""
Snapshot repository.

Encapsulates all database queries related to the Snapshot model.
Snapshots are append-only — no updates or deletes in normal operation.
"""

from datetime import datetime

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.snapshot import Snapshot
from app.repositories.base import BaseRepository


class SnapshotRepository(BaseRepository[Snapshot]):
    """Data access layer for Snapshot records (time-series market data)."""

    def __init__(self, db: Session):
        super().__init__(Snapshot, db)

    def get_by_token_id(
        self, token_id: int, skip: int = 0, limit: int = 100
    ) -> list[Snapshot]:
        """Fetch snapshots for a specific token, most recent first."""
        return (
            self._db.query(Snapshot)
            .filter(Snapshot.token_id == token_id)
            .order_by(desc(Snapshot.timestamp))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_latest_by_token_id(self, token_id: int) -> Snapshot | None:
        """Get the most recent snapshot for a token."""
        return (
            self._db.query(Snapshot)
            .filter(Snapshot.token_id == token_id)
            .order_by(desc(Snapshot.timestamp))
            .first()
        )

    def get_in_time_range(
        self,
        token_id: int,
        start: datetime,
        end: datetime,
    ) -> list[Snapshot]:
        """Fetch snapshots for a token within a time window."""
        return (
            self._db.query(Snapshot)
            .filter(
                Snapshot.token_id == token_id,
                Snapshot.timestamp >= start,
                Snapshot.timestamp <= end,
            )
            .order_by(Snapshot.timestamp)
            .all()
        )
