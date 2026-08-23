"""Tests for lazy schema initialization (app.db.connection.init_db)."""

from __future__ import annotations

import sqlite3

import app.db.connection as db_connection
from app.db import init_db

EXPECTED_TABLES = {
    "users_profile",
    "watchlist",
    "positions",
    "trades",
    "portfolio_snapshots",
    "chat_messages",
}


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {row[0] for row in rows}


class TestInitDb:
    """FOUND-02: lazy schema creation and seed, never re-seeds an existing database."""

    def test_fresh_path_creates_file_and_all_six_tables(self, initialized_db):
        conn = initialized_db
        assert _table_names(conn) == EXPECTED_TABLES

    def test_journal_mode_is_wal(self, initialized_db):
        conn = initialized_db
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"

    def test_idempotent_double_init_leaves_counts_unchanged(self, tmp_db_path):
        db_connection._connection = None
        init_db()
        conn = db_connection.get_db()

        table_count_before = len(_table_names(conn))
        user_count_before = conn.execute("SELECT COUNT(*) FROM users_profile").fetchone()[0]
        watchlist_count_before = conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]

        init_db()
        conn = db_connection.get_db()

        assert len(_table_names(conn)) == table_count_before
        assert conn.execute("SELECT COUNT(*) FROM users_profile").fetchone()[0] == user_count_before
        assert (
            conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]
            == watchlist_count_before
        )

        conn.close()
        db_connection._connection = None

    def test_existing_database_is_never_reseeded_or_clobbered(self, initialized_db):
        conn = initialized_db

        conn.execute(
            "UPDATE users_profile SET cash_balance = 4242.0 WHERE id = 'default'"
        )
        conn.execute(
            "DELETE FROM watchlist WHERE ticker IN "
            "(SELECT ticker FROM watchlist ORDER BY added_at LIMIT 2)"
        )
        remaining = conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]
        assert remaining == 8

        init_db()
        conn = db_connection.get_db()

        cash_balance = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id = 'default'"
        ).fetchone()[0]
        assert cash_balance == 4242.0
        assert conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0] == 8

    def test_existing_but_empty_database_gets_full_schema_and_seed(self, tmp_db_path):
        # Create an empty file with zero tables (simulates a truncated/corrupt-but-present file).
        tmp_db_path.touch()

        db_connection._connection = None
        init_db()
        conn = db_connection.get_db()

        assert _table_names(conn) == EXPECTED_TABLES
        assert conn.execute("SELECT COUNT(*) FROM users_profile").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0] == 10

        conn.close()
        db_connection._connection = None
