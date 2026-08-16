"""CRUD helper behaviour and UNIQUE constraint enforcement."""

import sqlite3

import pytest

from app.db import (
    add_watchlist_ticker,
    delete_position,
    get_cash_balance,
    get_position,
    insert_chat_message,
    insert_snapshot,
    insert_trade,
    list_positions,
    list_recent_chat_messages,
    list_snapshots,
    list_trades,
    list_watchlist,
    remove_watchlist_ticker,
    update_cash_balance,
    upsert_position,
)

# --- users_profile ---------------------------------------------------------


def test_cash_balance_roundtrip(conn):
    assert get_cash_balance(conn) == 10000.0
    update_cash_balance(conn, 8123.45)
    assert get_cash_balance(conn) == 8123.45


def test_cash_balance_unknown_user(conn):
    with pytest.raises(ValueError):
        get_cash_balance(conn, user_id="nobody")
    with pytest.raises(ValueError):
        update_cash_balance(conn, 1.0, user_id="nobody")


# --- watchlist -------------------------------------------------------------


def test_list_watchlist_returns_seeded_entries(conn):
    entries = list_watchlist(conn)
    assert len(entries) == 10
    assert {e.ticker for e in entries} == {
        "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"
    }


def test_add_and_remove_watchlist_ticker(conn):
    assert add_watchlist_ticker(conn, "PYPL") is True
    assert "PYPL" in {e.ticker for e in list_watchlist(conn)}
    assert remove_watchlist_ticker(conn, "PYPL") is True
    assert "PYPL" not in {e.ticker for e in list_watchlist(conn)}


def test_add_watchlist_ticker_is_idempotent(conn):
    assert add_watchlist_ticker(conn, "AAPL") is False
    assert len(list_watchlist(conn)) == 10


def test_watchlist_ticker_is_normalised(conn):
    assert add_watchlist_ticker(conn, " pypl ") is True
    assert "PYPL" in {e.ticker for e in list_watchlist(conn)}
    assert add_watchlist_ticker(conn, "pypl") is False


def test_remove_missing_watchlist_ticker(conn):
    assert remove_watchlist_ticker(conn, "ZZZZ") is False


def test_watchlist_unique_constraint(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            ("dup", "default", "AAPL", "2026-01-01T00:00:00Z"),
        )


def test_watchlist_is_per_user(conn):
    assert add_watchlist_ticker(conn, "AAPL", user_id="other") is True
    assert len(list_watchlist(conn, user_id="other")) == 1
    assert len(list_watchlist(conn)) == 10


# --- positions -------------------------------------------------------------


def test_upsert_position_inserts_then_updates(conn):
    created = upsert_position(conn, "AAPL", 10.0, 190.0)
    assert created.quantity == 10.0
    assert created.avg_cost == 190.0

    updated = upsert_position(conn, "AAPL", 15.5, 192.25)
    assert updated.id == created.id
    assert updated.quantity == 15.5
    assert updated.avg_cost == 192.25
    assert len(list_positions(conn)) == 1


def test_get_position_missing(conn):
    assert get_position(conn, "AAPL") is None


def test_position_supports_fractional_quantity(conn):
    position = upsert_position(conn, "nvda", 0.25, 800.5)
    assert position.ticker == "NVDA"
    assert position.quantity == 0.25


def test_delete_position(conn):
    upsert_position(conn, "TSLA", 3.0, 250.0)
    assert delete_position(conn, "TSLA") is True
    assert delete_position(conn, "TSLA") is False
    assert list_positions(conn) == []


def test_positions_unique_constraint(conn):
    upsert_position(conn, "AAPL", 1.0, 190.0)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            ("dup", "default", "AAPL", 2.0, 191.0, "2026-01-01T00:00:00Z"),
        )


def test_list_positions_sorted_by_ticker(conn):
    upsert_position(conn, "TSLA", 1.0, 250.0)
    upsert_position(conn, "AAPL", 1.0, 190.0)
    assert [p.ticker for p in list_positions(conn)] == ["AAPL", "TSLA"]


# --- trades ----------------------------------------------------------------


def test_insert_and_list_trades(conn):
    insert_trade(conn, "AAPL", "buy", 10.0, 190.0)
    insert_trade(conn, "AAPL", "sell", 4.5, 195.0)

    trades = list_trades(conn)
    assert [t.side for t in trades] == ["sell", "buy"]
    assert trades[0].quantity == 4.5
    assert trades[0].price == 195.0
    assert trades[0].executed_at


def test_list_trades_limit(conn):
    for _ in range(3):
        insert_trade(conn, "MSFT", "buy", 1.0, 400.0)
    assert len(list_trades(conn, limit=2)) == 2


def test_trade_side_is_constrained(conn):
    with pytest.raises(sqlite3.IntegrityError):
        insert_trade(conn, "AAPL", "hold", 1.0, 190.0)


# --- portfolio_snapshots ---------------------------------------------------


def test_snapshots_returned_oldest_first(conn):
    for value in (10000.0, 10100.0, 10200.0):
        insert_snapshot(conn, value)
    assert [s.total_value for s in list_snapshots(conn)] == [10000.0, 10100.0, 10200.0]


def test_snapshot_limit_keeps_most_recent(conn):
    for value in (1.0, 2.0, 3.0, 4.0):
        insert_snapshot(conn, value)
    assert [s.total_value for s in list_snapshots(conn, limit=2)] == [3.0, 4.0]


# --- chat_messages ---------------------------------------------------------


def test_insert_chat_message_without_actions(conn):
    message = insert_chat_message(conn, "user", "How is my portfolio?")
    assert message.actions is None
    assert list_recent_chat_messages(conn)[0].content == "How is my portfolio?"


def test_chat_actions_roundtrip_as_json(conn):
    actions = {"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 5}]}
    insert_chat_message(conn, "assistant", "Bought 5 AAPL.", actions=actions)
    assert list_recent_chat_messages(conn)[0].actions == actions


def test_recent_chat_messages_oldest_first_and_capped(conn):
    for i in range(25):
        insert_chat_message(conn, "user", f"message {i}")
    recent = list_recent_chat_messages(conn, limit=20)
    assert len(recent) == 20
    assert recent[0].content == "message 5"
    assert recent[-1].content == "message 24"


def test_chat_role_is_constrained(conn):
    with pytest.raises(sqlite3.IntegrityError):
        insert_chat_message(conn, "system", "nope")
