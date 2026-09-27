"""
Lightweight SQLite schema migrations.

The project uses `Base.metadata.create_all()` for SQLite, which creates missing
tables but never alters existing ones. When a column is added to a model that
already has a table on disk, it has to be patched in manually.

Every step here is idempotent, so this runs safely on every startup.
For Postgres, use Alembic instead — this module is SQLite-only by design.
"""

import logging

from sqlalchemy import Engine, inspect, text

logger = logging.getLogger(__name__)


def _columns(engine: Engine, table: str) -> set[str]:
    """Column names present on a table, or empty set if the table is absent."""
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return set()
    return {c["name"] for c in inspector.get_columns(table)}


def _add_column(engine: Engine, table: str, column: str, ddl_type: str) -> bool:
    """
    Add a column if it's missing. Returns True when a change was made.

    SQLite's ALTER TABLE ADD COLUMN is safe and preserves existing rows.
    """
    if column in _columns(engine, table):
        return False

    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))
    logger.info(f"Migration: added {table}.{column}")
    return True


def run_sqlite_migrations(engine: Engine) -> None:
    """
    Bring an existing SQLite file up to date with the current models.

    Steps:
        1. Add `watchlist_id` and `position` to the watchlist items table.
        2. Move any items that predate multi-list support into a default list,
           so nothing silently disappears from the UI.
        3. Rewrite short chain slugs ("sol", "eth") to canonical ids. Rows saved
           from trending data carried GMGN's slugs, which DexScreener rejects —
           those tokens could never be quoted or linked.
    """
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    if "watchlist" not in tables:
        return  # Fresh database — create_all already built the current schema

    _add_column(engine, "watchlist", "watchlist_id", "INTEGER")
    _add_column(engine, "watchlist", "position", "INTEGER DEFAULT 0")

    _backfill_default_list(engine)
    _normalize_chain_ids(engine, tables)


def _backfill_default_list(engine: Engine) -> None:
    """Assign orphaned watchlist items (watchlist_id IS NULL) to a default list."""
    from app.models.watchlist import DEFAULT_LIST_NAME

    with engine.begin() as conn:
        orphans = conn.execute(
            text("SELECT COUNT(*) FROM watchlist WHERE watchlist_id IS NULL")
        ).scalar_one()

        if not orphans:
            return

        # Reuse the default list if a previous run already created it
        list_id = conn.execute(
            text("SELECT id FROM watchlists WHERE name = :name ORDER BY id LIMIT 1"),
            {"name": DEFAULT_LIST_NAME},
        ).scalar_one_or_none()

        if list_id is None:
            next_pos = conn.execute(
                text("SELECT COALESCE(MAX(position) + 1, 0) FROM watchlists")
            ).scalar_one()
            list_id = conn.execute(
                text(
                    "INSERT INTO watchlists (name, position, created_at) "
                    "VALUES (:name, :position, CURRENT_TIMESTAMP) RETURNING id"
                ),
                {"name": DEFAULT_LIST_NAME, "position": next_pos},
            ).scalar_one()
            logger.info(f"Migration: created default watchlist '{DEFAULT_LIST_NAME}'")

        conn.execute(
            text("UPDATE watchlist SET watchlist_id = :lid WHERE watchlist_id IS NULL"),
            {"lid": list_id},
        )

    logger.info(f"Migration: moved {orphans} existing token(s) into '{DEFAULT_LIST_NAME}'")


def _normalize_chain_ids(engine: Engine, tables: set[str]) -> None:
    """
    Rewrite short chain slugs to canonical ids in stored rows.

    Trending data comes from GMGN, which uses "sol"/"eth". Anything saved with
    those values can't be looked up on DexScreener, so the token shows up with
    empty metrics and a dead chart link. Fixing the stored value repairs it.
    """
    aliases = {"sol": "solana", "eth": "ethereum", "bnb": "bsc", "binance": "bsc"}
    targets = [t for t in ("watchlist", "tokens") if t in tables]

    for table in targets:
        if "chain" not in _columns(engine, table):
            continue

        with engine.begin() as conn:
            for old, new in aliases.items():
                updated = conn.execute(
                    text(f"UPDATE {table} SET chain = :new WHERE LOWER(chain) = :old"),
                    {"new": new, "old": old},
                ).rowcount
                if updated:
                    logger.info(
                        f"Migration: {table}.chain '{old}' -> '{new}' ({updated} row(s))"
                    )
