"""
Journal ORM model.

Stores trade notes, learnings, and cheat sheet entries persistently.
"""

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class JournalEntry(Base):
    """A journal entry — trade note, learning, or cheat sheet item."""

    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(50), index=True)  # "trade_note", "learning", "cheatsheet"
    text: Mapped[str] = mapped_column(Text)
    tx_hash: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)  # Links note to a specific trade
    token_symbol: Mapped[str | None] = mapped_column(String(50), nullable=True)
    chain: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
