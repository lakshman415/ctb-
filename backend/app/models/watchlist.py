"""
Watchlist, WatchlistItem, and Alert ORM models.

Structure:
    Watchlist      — a named collection ("Runners", "Long term", ...). Ordered by `position`.
    WatchlistItem  — a token inside one watchlist.
    Alert          — a threshold notification on a watched token.

Table naming note: the items table is `watchlist` (singular) for historical
reasons — it predates multi-list support. The lists table is `watchlists`.
Renaming the items table would break the `alerts.watchlist_id` foreign key,
so the original name is kept and the ORM class names carry the meaning.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

DEFAULT_LIST_NAME = "My Watchlist"


class Watchlist(Base):
    """A named, user-ordered collection of tokens."""

    __tablename__ = "watchlists"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))

    # Display order — persisted so drag-to-reorder survives reloads
    position: Mapped[int] = mapped_column(Integer, default=0, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list["WatchlistItem"]] = relationship(
        "WatchlistItem",
        back_populates="watchlist",
        cascade="all, delete-orphan",
        order_by="WatchlistItem.position",
    )


class WatchlistItem(Base):
    """A token tracked inside a watchlist."""

    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    watchlist_id: Mapped[int | None] = mapped_column(
        ForeignKey("watchlists.id"), index=True, nullable=True
    )

    chain: Mapped[str] = mapped_column(String(50), index=True)
    token_address: Mapped[str] = mapped_column(String(255), index=True)
    pair_address: Mapped[str] = mapped_column(String(255))
    symbol: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))

    # Snapshot at time of adding — the entry reference for alerts and P&L framing
    added_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    added_market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)

    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    watchlist: Mapped["Watchlist | None"] = relationship("Watchlist", back_populates="items")

    alerts: Mapped[list["Alert"]] = relationship(
        "Alert", back_populates="watchlist_item", cascade="all, delete-orphan"
    )


class Alert(Base):
    """A threshold alert on a watched token."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Points at a WatchlistItem, not a Watchlist — named before multi-list support.
    watchlist_id: Mapped[int] = mapped_column(ForeignKey("watchlist.id"), index=True)

    # Alert config
    metric: Mapped[str] = mapped_column(String(50))       # market_cap, price, volume_24h, liquidity, price_change_1h
    condition: Mapped[str] = mapped_column(String(10))    # "above" | "below"
    threshold: Mapped[float] = mapped_column(Float)

    # State
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    triggered_value: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    watchlist_item: Mapped["WatchlistItem"] = relationship("WatchlistItem", back_populates="alerts")
