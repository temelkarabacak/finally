"""Tests for default seed data correctness (app.db.seed)."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime

import pytest

from app.db import DEFAULT_WATCHLIST, get_active_tickers
from app.market.seed_prices import SEED_PRICES


class TestSeedDefaults:
    """FOUND-02: seed correctness for users_profile and watchlist."""

    def test_exactly_one_default_user_at_ten_thousand(self, initialized_db):
        conn = initialized_db
        rows = conn.execute("SELECT id, cash_balance FROM users_profile").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "default"
        assert rows[0][1] == 10000.0

    def test_exactly_ten_watchlist_rows_matching_default_and_seed_prices(self, initialized_db):
        conn = initialized_db
        rows = conn.execute("SELECT ticker FROM watchlist").fetchall()
        tickers = {row[0] for row in rows}

        assert len(rows) == 10
        assert tickers == set(DEFAULT_WATCHLIST)
        # Cross-check against the simulator's seed prices so the DB seed and
        # the simulator seed never drift apart.
        assert tickers == set(SEED_PRICES)

    def test_unique_user_ticker_enforced(self, initialized_db):
        conn = initialized_db
        now = datetime.now(UTC).isoformat()

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                (uuid.uuid4().hex, "default", "AAPL", now),
            )


class TestGetActiveTickers:
    """FOUND-04 support: watchlist UNION open positions, deduplicated."""

    def test_seeded_database_returns_ten_watchlist_tickers(self, initialized_db):
        conn = initialized_db
        tickers = get_active_tickers(conn)
        assert set(tickers) == set(DEFAULT_WATCHLIST)
        assert len(tickers) == 10

    def test_held_but_unwatched_ticker_extends_active_set(self, initialized_db):
        conn = initialized_db
        now = datetime.now(UTC).isoformat()

        conn.execute(
            "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (uuid.uuid4().hex, "default", "PYPL", 5.0, 60.0, now),
        )

        tickers = get_active_tickers(conn)
        assert len(tickers) == 11
        assert "PYPL" in tickers

    def test_watched_and_held_ticker_appears_once(self, initialized_db):
        conn = initialized_db
        now = datetime.now(UTC).isoformat()

        # AAPL is already in the seeded watchlist; holding it too must not
        # duplicate it in the UNION result.
        conn.execute(
            "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (uuid.uuid4().hex, "default", "AAPL", 3.0, 190.0, now),
        )

        tickers = get_active_tickers(conn)
        assert len(tickers) == 10
        assert tickers.count("AAPL") == 1

    def test_zero_quantity_position_excluded(self, initialized_db):
        conn = initialized_db
        now = datetime.now(UTC).isoformat()

        conn.execute(
            "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (uuid.uuid4().hex, "default", "PYPL", 0.0, 60.0, now),
        )

        tickers = get_active_tickers(conn)
        assert "PYPL" not in tickers
        assert len(tickers) == 10
