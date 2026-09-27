"""
Token ORM model.

Represents a unique token discovered by the scanner.
One token can have many snapshots over time.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Token(Base):
    """Persistent record of a token pair discovered on-chain."""

    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    pair_address: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    token_address: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(255))
    symbol: Mapped[str] = mapped_column(String(50))
    chain: Mapped[str] = mapped_column(String(50), index=True)
    price: Mapped[float] = mapped_column(Float, nullable=True)
    market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    fdv: Mapped[float | None] = mapped_column(Float, nullable=True)
    liquidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    pair_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Social links
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    twitter: Mapped[str | None] = mapped_column(String(500), nullable=True)
    telegram: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    snapshots: Mapped[list["Snapshot"]] = relationship(
        "Snapshot", back_populates="token", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Token {self.symbol} ({self.chain}) @ {self.pair_address[:10]}...>"
