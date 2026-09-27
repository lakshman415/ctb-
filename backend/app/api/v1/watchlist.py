"""
Watchlists, watchlist items, and alerts API.

Route ordering note: literal paths like `/alerts/triggered` and `/lists/reorder`
are declared before their `/{id}` counterparts so FastAPI doesn't try to parse
"triggered" or "reorder" as an integer id.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.core.database import get_db
from app.models.watchlist import DEFAULT_LIST_NAME, Alert, Watchlist, WatchlistItem
from app.schemas.watchlist import (
    AlertCreate,
    AlertResponse,
    WatchlistCreate,
    WatchlistItemCreate,
    WatchlistItemResponse,
    WatchlistRename,
    WatchlistReorder,
    WatchlistResponse,
    WatchlistTokenQuote,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/watchlist", tags=["watchlist"])


# ─── Helpers ───────────────────────────────────────────────

def _to_list_response(wl: Watchlist, item_count: int) -> WatchlistResponse:
    return WatchlistResponse(
        id=wl.id,
        name=wl.name,
        position=wl.position,
        created_at=wl.created_at,
        item_count=item_count,
    )


def _item_counts(db: Session) -> dict[int, int]:
    """Item count per watchlist id, in one query."""
    rows = db.execute(
        select(WatchlistItem.watchlist_id, func.count(WatchlistItem.id))
        .group_by(WatchlistItem.watchlist_id)
    ).all()
    return {wid: count for wid, count in rows if wid is not None}


def _ensure_default_list(db: Session) -> Watchlist:
    """
    Return the first watchlist, creating a default one when none exist.

    Lets a user add a token without having explicitly created a list first.
    """
    wl = db.execute(
        select(Watchlist).order_by(Watchlist.position, Watchlist.id).limit(1)
    ).scalar_one_or_none()

    if wl is None:
        wl = Watchlist(name=DEFAULT_LIST_NAME, position=0)
        db.add(wl)
        db.commit()
        db.refresh(wl)
        logger.info(f"Created default watchlist '{DEFAULT_LIST_NAME}'")

    return wl


# ═══════════════════════════════════════════════════════════
# LISTS
# ═══════════════════════════════════════════════════════════

@router.get("/lists", response_model=list[WatchlistResponse])
def list_watchlists(db: Session = Depends(get_db)):
    """All watchlists in user-defined order."""
    lists = db.execute(
        select(Watchlist).order_by(Watchlist.position, Watchlist.id)
    ).scalars().all()

    counts = _item_counts(db)
    return [_to_list_response(wl, counts.get(wl.id, 0)) for wl in lists]


@router.post("/lists", response_model=WatchlistResponse)
def create_watchlist(payload: WatchlistCreate, db: Session = Depends(get_db)):
    """Create a watchlist, appended to the end of the current order."""
    name = payload.name.strip()
    if not name:
        raise HTTPException(422, "Watchlist name cannot be empty")

    existing = db.execute(
        select(Watchlist).where(func.lower(Watchlist.name) == name.lower())
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(409, f"A watchlist named '{name}' already exists")

    next_pos = db.execute(
        select(func.coalesce(func.max(Watchlist.position) + 1, 0))
    ).scalar_one()

    wl = Watchlist(name=name, position=next_pos)
    db.add(wl)
    db.commit()
    db.refresh(wl)
    return _to_list_response(wl, 0)


@router.patch("/lists/reorder", response_model=list[WatchlistResponse])
def reorder_watchlists(payload: WatchlistReorder, db: Session = Depends(get_db)):
    """
    Persist a new watchlist order.

    Position is the index in the submitted array, so drag-and-drop survives
    reloads. Ids not included keep their relative order after the listed ones.
    """
    lists = db.execute(select(Watchlist)).scalars().all()
    by_id = {wl.id: wl for wl in lists}

    unknown = [i for i in payload.ids if i not in by_id]
    if unknown:
        raise HTTPException(404, f"Unknown watchlist id(s): {unknown}")

    for index, list_id in enumerate(payload.ids):
        by_id[list_id].position = index

    # Anything omitted goes after, keeping its previous relative order
    remaining = sorted(
        (wl for wl in lists if wl.id not in set(payload.ids)),
        key=lambda w: (w.position, w.id),
    )
    for offset, wl in enumerate(remaining):
        wl.position = len(payload.ids) + offset

    db.commit()

    counts = _item_counts(db)
    ordered = sorted(lists, key=lambda w: (w.position, w.id))
    return [_to_list_response(wl, counts.get(wl.id, 0)) for wl in ordered]


@router.patch("/lists/{list_id}", response_model=WatchlistResponse)
def rename_watchlist(list_id: int, payload: WatchlistRename, db: Session = Depends(get_db)):
    """Rename a watchlist."""
    wl = db.get(Watchlist, list_id)
    if not wl:
        raise HTTPException(404, "Watchlist not found")

    name = payload.name.strip()
    if not name:
        raise HTTPException(422, "Watchlist name cannot be empty")

    wl.name = name
    db.commit()
    db.refresh(wl)
    return _to_list_response(wl, _item_counts(db).get(wl.id, 0))


@router.delete("/lists/{list_id}")
def delete_watchlist(list_id: int, db: Session = Depends(get_db)):
    """Delete a watchlist and every token inside it."""
    wl = db.get(Watchlist, list_id)
    if wl:
        db.delete(wl)
        db.commit()
    return {"ok": True}


@router.get("/lists/{list_id}/tokens", response_model=list[WatchlistTokenQuote])
async def list_tokens(list_id: int, db: Session = Depends(get_db)):
    """
    Tokens in a watchlist, enriched with live market data.

    Returns current market cap, volume, age, and 5m/1h/24h price changes so the
    table reflects the market rather than the values captured at add time.
    """
    wl = db.get(Watchlist, list_id)
    if not wl:
        raise HTTPException(404, "Watchlist not found")

    items = db.execute(
        select(WatchlistItem)
        .options(selectinload(WatchlistItem.alerts))
        .where(WatchlistItem.watchlist_id == list_id)
        .order_by(WatchlistItem.position, WatchlistItem.id)
    ).scalars().all()

    if not items:
        return []

    from app.clients.dexscreener import DexScreenerClient
    from app.services.watchlist_quote_service import WatchlistQuoteService

    settings = get_settings()
    client = DexScreenerClient(
        base_url=settings.dexscreener_base_url,
        verify_ssl=settings.dexscreener_verify_ssl,
    )
    try:
        quotes = await WatchlistQuoteService(client).quote_items(list(items))
    finally:
        await client.close()

    _heal_pair_addresses(db, items, quotes)
    return quotes


def _heal_pair_addresses(
    db: Session, items: list[WatchlistItem], quotes: list[WatchlistTokenQuote]
) -> None:
    """
    Persist pair addresses corrected during quoting.

    Some items were stored with the token address in `pair_address` (trending
    data doesn't always include a pool), which produces broken chart links.
    Quoting resolves the real pool, so the fix is saved once and reused.
    """
    by_id = {item.id: item for item in items}
    changed = 0

    for quote in quotes:
        item = by_id.get(quote.item_id)
        if item and quote.pair_address and quote.pair_address != item.pair_address:
            item.pair_address = quote.pair_address
            changed += 1

    if changed:
        db.commit()
        logger.info(f"Corrected {changed} watchlist pair address(es)")


# ═══════════════════════════════════════════════════════════
# ITEMS
# ═══════════════════════════════════════════════════════════

@router.get("/items", response_model=list[WatchlistItemResponse])
def list_items(db: Session = Depends(get_db)):
    """
    Every watchlist item across all lists.

    Used by Trending/Scanner to render star state and show which lists a token
    already belongs to.
    """
    return db.execute(
        select(WatchlistItem)
        .options(selectinload(WatchlistItem.alerts))
        .order_by(WatchlistItem.created_at.desc())
    ).scalars().all()


@router.post("/items", response_model=WatchlistItemResponse)
def add_item(item: WatchlistItemCreate, db: Session = Depends(get_db)):
    """
    Add a token to a watchlist.

    Idempotent per list: adding a token that's already in the target list
    returns the existing row. The same token may live in multiple lists.
    """
    target_list_id = item.watchlist_id
    if target_list_id is None:
        target_list_id = _ensure_default_list(db).id
    elif not db.get(Watchlist, target_list_id):
        raise HTTPException(404, "Watchlist not found")

    existing = db.execute(
        select(WatchlistItem).where(
            WatchlistItem.watchlist_id == target_list_id,
            WatchlistItem.chain == item.chain,
            func.lower(WatchlistItem.token_address) == item.token_address.lower(),
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    next_pos = db.execute(
        select(func.coalesce(func.max(WatchlistItem.position) + 1, 0))
        .where(WatchlistItem.watchlist_id == target_list_id)
    ).scalar_one()

    payload = item.model_dump()
    payload["watchlist_id"] = target_list_id

    db_item = WatchlistItem(**payload, position=next_pos)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@router.delete("/items/{item_id}")
def remove_item(item_id: int, db: Session = Depends(get_db)):
    """Remove a token from its watchlist (cascades to its alerts)."""
    item = db.get(WatchlistItem, item_id)
    if item:
        db.delete(item)
        db.commit()
    return {"ok": True}


@router.patch("/items/{item_id}/note")
def update_note(item_id: int, note: str, db: Session = Depends(get_db)):
    """Update the note on a watchlist item."""
    item = db.get(WatchlistItem, item_id)
    if not item:
        raise HTTPException(404, "Watchlist item not found")
    item.note = note
    db.commit()
    return {"ok": True}


# ═══════════════════════════════════════════════════════════
# ALERTS
# ═══════════════════════════════════════════════════════════

@router.get("/alerts/triggered", response_model=list[AlertResponse])
def triggered_alerts(db: Session = Depends(get_db)):
    """All currently-triggered alerts."""
    return db.execute(select(Alert).where(Alert.triggered.is_(True))).scalars().all()


@router.post("/alerts", response_model=AlertResponse)
def create_alert(alert: AlertCreate, db: Session = Depends(get_db)):
    """Create a threshold alert on a watched token."""
    if not db.get(WatchlistItem, alert.watchlist_id):
        raise HTTPException(404, "Watchlist item not found")

    db_alert = Alert(**alert.model_dump())
    db.add(db_alert)
    db.commit()
    db.refresh(db_alert)
    return db_alert


@router.delete("/alerts/{alert_id}")
def delete_alert(alert_id: int, db: Session = Depends(get_db)):
    """Delete an alert."""
    a = db.get(Alert, alert_id)
    if a:
        db.delete(a)
        db.commit()
    return {"ok": True}


@router.patch("/alerts/{alert_id}/toggle")
def toggle_alert(alert_id: int, db: Session = Depends(get_db)):
    """Enable/disable an alert."""
    a = db.get(Alert, alert_id)
    if not a:
        raise HTTPException(404, "Alert not found")
    a.enabled = not a.enabled
    db.commit()
    return {"enabled": a.enabled}


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int, db: Session = Depends(get_db)):
    """Reset a triggered alert so it can fire again."""
    a = db.get(Alert, alert_id)
    if not a:
        raise HTTPException(404, "Alert not found")
    a.triggered = False
    a.triggered_at = None
    a.triggered_value = None
    db.commit()
    return {"ok": True}
