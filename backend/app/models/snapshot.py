"""
Snapshot ORM model.

Represents a point-in-time capture of a token's market data.
Snapshots are never overwritten — they form a time-series history.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Snapshot(Base):
    """Immutable point-in-time market data for a token."""

    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    token_id: Mapped[int] = mapped_column(ForeignKey("tokens.id"), index=True)

    # Timing
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    # Price
    price: Mapped[float] = mapped_column(Float)

    # Volume at different intervals
    volume_5m: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_1h: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_6h: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_24h: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Trade activity
    buys: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sells: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Price movement
    price_change_5m: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_change_1h: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_change_6h: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_change_24h: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Liquidity at snapshot time
    liquidity: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships
    token: Mapped["Token"] = relationship("Token", back_populates="snapshots")

    def __repr__(self) -> str:
        return f"<Snapshot token_id={self.token_id} @ {self.timestamp}>"
