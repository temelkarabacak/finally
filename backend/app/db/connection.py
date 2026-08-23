"""SQLite connection management: lazy schema init and active-ticker queries."""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path

from .seed import DEFAULT_USER_ID, seed_defaults

logger = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"

_connection: sqlite3.Connection | None = None


def resolve_db_path() -> Path:
    """Resolve the SQLite file path.

    Uses FINALLY_DB_PATH if set, otherwise defaults to <repo-root>/db/finally.db.
    Creates the parent directory if it doesn't exist.
    """
    env_path = os.environ.get("FINALLY_DB_PATH", "").strip()
    if env_path:
        path = Path(env_path)
    else:
        # backend/app/db/connection.py -> parents[3] is the repo root
        path = Path(__file__).resolve().parents[3] / "db" / "finally.db"

    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def init_db(db_path: str | Path | None = None) -> None:
    """Lazily create the schema and seed default data.

    Every schema statement is CREATE TABLE IF NOT EXISTS, so running this
    against an existing database is a no-op for table creation. Seeding only
    happens when users_profile is empty, so an existing populated database
    is never re-seeded or clobbered.
    """
    global _connection

    path = Path(db_path) if db_path is not None else resolve_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path), check_same_thread=False, autocommit=True)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript(_SCHEMA_PATH.read_text())

    row_count = conn.execute("SELECT COUNT(*) FROM users_profile").fetchone()[0]
    if row_count == 0:
        seed_defaults(conn)
        logger.info("Database seeded with default user and watchlist at %s", path)

    _connection = conn


def get_db() -> sqlite3.Connection:
    """Return the module-level singleton connection. Call init_db() first."""
    if _connection is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _connection


def get_active_tickers(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> list[str]:
    """Return the active ticker set: watchlist UNION open positions.

    UNION (not UNION ALL) deduplicates a ticker that is both watched and held.
    """
    rows = conn.execute(
        """
        SELECT ticker FROM watchlist WHERE user_id = ?
        UNION
        SELECT ticker FROM positions WHERE user_id = ? AND quantity > 0
        """,
        (user_id, user_id),
    ).fetchall()
    return [row[0] for row in rows]


def get_watchlist_tickers(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> list[str]:
    """Return watchlist tickers for a user, ordered by when they were added."""
    rows = conn.execute(
        "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY added_at",
        (user_id,),
    ).fetchall()
    return [row[0] for row in rows]
