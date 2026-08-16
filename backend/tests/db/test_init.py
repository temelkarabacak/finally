"""Schema creation, seeding and lazy-init idempotency."""

import sqlite3
from pathlib import Path

import pytest

from app.db import DEFAULT_USER_ID, database_path, get_connection, get_db

EXPECTED_TABLES = {
    "users_profile",
    "watchlist",
    "positions",
    "trades",
    "portfolio_snapshots",
    "chat_messages",
}
SEED_TICKERS = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]


def _tables(conn):
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {r["name"] for r in rows}


def test_creates_schema_from_missing_file(db_path):
    assert not Path(db_path).exists()
    conn = get_connection(db_path)
    assert EXPECTED_TABLES <= _tables(conn)
    conn.close()


def test_creates_parent_directory(tmp_path):
    nested = str(tmp_path / "nested" / "dir" / "finally.db")
    conn = get_connection(nested)
    conn.close()
    assert Path(nested).exists()


def test_seeds_profile_and_watchlist(conn):
    profile = conn.execute("SELECT * FROM users_profile").fetchall()
    assert len(profile) == 1
    assert profile[0]["id"] == DEFAULT_USER_ID
    assert profile[0]["cash_balance"] == 10000.0
    assert profile[0]["created_at"]

    rows = conn.execute("SELECT ticker, user_id, id FROM watchlist").fetchall()
    assert sorted(r["ticker"] for r in rows) == sorted(SEED_TICKERS)
    assert all(r["user_id"] == DEFAULT_USER_ID for r in rows)
    assert all(len(r["id"]) == 36 for r in rows)


def test_reinit_does_not_reseed_or_lose_data(db_path):
    first = get_connection(db_path)
    first.execute("UPDATE users_profile SET cash_balance = 42.0")
    first.execute("DELETE FROM watchlist WHERE ticker = 'AAPL'")
    first.commit()
    first.close()

    second = get_connection(db_path)
    assert second.execute("SELECT cash_balance FROM users_profile").fetchone()[0] == 42.0
    assert second.execute("SELECT count(*) FROM watchlist").fetchone()[0] == 9
    second.close()


def test_empty_tables_are_reseeded(db_path):
    """A file whose profile row is gone counts as uninitialised."""
    first = get_connection(db_path)
    first.execute("DELETE FROM users_profile")
    first.execute("DELETE FROM watchlist")
    first.commit()
    first.close()

    second = get_connection(db_path)
    assert second.execute("SELECT count(*) FROM watchlist").fetchone()[0] == 10
    second.close()


def test_database_path_env_override(monkeypatch):
    monkeypatch.setenv("FINALLY_DB_PATH", "/tmp/custom.db")
    assert database_path() == "/tmp/custom.db"


def test_database_path_default_is_project_root_db(monkeypatch):
    monkeypatch.delenv("FINALLY_DB_PATH", raising=False)
    path = Path(database_path())
    assert path.name == "finally.db"
    assert path.parent.name == "db"
    assert (path.parents[1] / "backend").is_dir()


def test_get_db_commits_on_success(db_path, monkeypatch):
    monkeypatch.setenv("FINALLY_DB_PATH", db_path)
    gen = get_db()
    conn = next(gen)
    conn.execute("UPDATE users_profile SET cash_balance = 55.0")
    with pytest.raises(StopIteration):
        next(gen)

    check = sqlite3.connect(db_path)
    assert check.execute("SELECT cash_balance FROM users_profile").fetchone()[0] == 55.0
    check.close()


def test_get_db_rolls_back_on_error(db_path, monkeypatch):
    monkeypatch.setenv("FINALLY_DB_PATH", db_path)
    gen = get_db()
    conn = next(gen)
    conn.execute("UPDATE users_profile SET cash_balance = 77.0")
    with pytest.raises(RuntimeError):
        gen.throw(RuntimeError("handler failed"))

    check = sqlite3.connect(db_path)
    assert check.execute("SELECT cash_balance FROM users_profile").fetchone()[0] == 10000.0
    check.close()
