"""
Journal API — CRUD for learnings, cheat sheet, and trade notes.
All entries saved to database.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.journal import JournalEntry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/journal", tags=["journal"])


class JournalEntryCreate(BaseModel):
    category: str  # "trade_note", "learning", "cheatsheet"
    text: str
    tx_hash: str | None = None
    token_symbol: str | None = None
    chain: str | None = None


class JournalEntryResponse(BaseModel):
    id: int
    category: str
    text: str
    tx_hash: str | None
    token_symbol: str | None
    chain: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("/entries", response_model=list[JournalEntryResponse])
def get_entries(
    category: str = Query(default="all", description="all, trade_note, learning, cheatsheet"),
    db: Session = Depends(get_db),
):
    """Get journal entries, optionally filtered by category."""
    query = db.query(JournalEntry)
    if category != "all":
        query = query.filter(JournalEntry.category == category)
    return query.order_by(JournalEntry.created_at.desc()).all()


@router.post("/entries", response_model=JournalEntryResponse)
def create_entry(entry: JournalEntryCreate, db: Session = Depends(get_db)):
    """Create a new journal entry."""
    db_entry = JournalEntry(
        category=entry.category,
        text=entry.text,
        tx_hash=entry.tx_hash,
        token_symbol=entry.token_symbol,
        chain=entry.chain,
    )
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry


@router.delete("/entries/{entry_id}")
def delete_entry(entry_id: int, db: Session = Depends(get_db)):
    """Delete a journal entry."""
    entry = db.query(JournalEntry).get(entry_id)
    if entry:
        db.delete(entry)
        db.commit()
    return {"ok": True}


@router.get("/trade-notes")
def get_trade_notes(db: Session = Depends(get_db)):
    """Get all trade notes — returns a dict of tx_hash -> note text for quick lookup."""
    notes = db.query(JournalEntry).filter(JournalEntry.category == "trade_note").all()
    return {n.tx_hash: {"id": n.id, "text": n.text} for n in notes if n.tx_hash}
