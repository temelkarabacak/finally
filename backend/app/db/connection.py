"""SQLite connection handling and lazy schema initialisation."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path

_SQL_DIR = Path(__file__).resolve().parents[2] / "db"
_SCHEMA_SQL = _SQL_DIR / "schema.sql"
_SEED_SQL = _SQL_DIR / "seed.sql"

# Runtime database lives at <project root>/db/finally.db (the Docker volume mount target).
_DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / "db" / "finally.db"


def database_path() -> str:
    """Resolved path of the SQLite file. Override with the FINALLY_DB_PATH env var."""
    return os.getenv("FINALLY_DB_PATH") or str(_DEFAULT_DB_PATH)


def initialize_database(conn: sqlite3.Connection) -> None:
    """Create any missing tables and seed defaults if the database has no user profile.

    Idempotent: the schema uses CREATE TABLE IF NOT EXISTS and seeding is skipped
    once a users_profile row exists.
    """
    conn.executescript(_SCHEMA_SQL.read_text())
    seeded = conn.execute("SELECT 1 FROM users_profile LIMIT 1").fetchone()
    if not seeded:
        conn.executescript(_SEED_SQL.read_text())
    conn.commit()


def get_connection(path: str | None = None) -> sqlite3.Connection:
    """Open a connection to the database, initialising the schema if needed.

    The caller owns the connection and must close it.
    """
    db_path = path or database_path()
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    if db_path != ":memory:":
        conn.execute("PRAGMA journal_mode=WAL")
    initialize_database(conn)
    return conn


def get_db() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency yielding a per-request connection.

    The request is one transaction: it commits when the handler returns and rolls
    back if it raises, so multi-step writes (a trade updating cash, position and
    trade log) are atomic without the query helpers committing individually.
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
