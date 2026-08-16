"""CRUD helpers for the FinAlly tables.

None of these commit; the caller (normally the get_db request transaction) does.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from typing import Any

from .models import ChatMessage, PortfolioSnapshot, Position, Trade, WatchlistEntry

DEFAULT_USER_ID = "default"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _new_id() -> str:
    return str(uuid.uuid4())


def _norm(ticker: str) -> str:
    return ticker.strip().upper()


# --- users_profile ---------------------------------------------------------


def get_cash_balance(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> float:
    row = conn.execute(
        "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"No user profile for id {user_id!r}")
    return row["cash_balance"]


def update_cash_balance(
    conn: sqlite3.Connection, cash_balance: float, user_id: str = DEFAULT_USER_ID
) -> None:
    """Set the cash balance to an absolute value."""
    cursor = conn.execute(
        "UPDATE users_profile SET cash_balance = ? WHERE id = ?", (cash_balance, user_id)
    )
    if cursor.rowcount == 0:
        raise ValueError(f"No user profile for id {user_id!r}")


# --- watchlist -------------------------------------------------------------


def list_watchlist(
    conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID
) -> list[WatchlistEntry]:
    rows = conn.execute(
        "SELECT * FROM watchlist WHERE user_id = ? ORDER BY added_at, ticker", (user_id,)
    ).fetchall()
    return [WatchlistEntry.from_row(r) for r in rows]


def add_watchlist_ticker(
    conn: sqlite3.Connection, ticker: str, user_id: str = DEFAULT_USER_ID
) -> bool:
    """Add a ticker. Returns False if it was already on the watchlist."""
    cursor = conn.execute(
        "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
        (_new_id(), user_id, _norm(ticker), _now()),
    )
    return cursor.rowcount > 0


def remove_watchlist_ticker(
    conn: sqlite3.Connection, ticker: str, user_id: str = DEFAULT_USER_ID
) -> bool:
    """Remove a ticker. Returns False if it was not on the watchlist."""
    cursor = conn.execute(
        "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?", (user_id, _norm(ticker))
    )
    return cursor.rowcount > 0


# --- positions -------------------------------------------------------------


def get_position(
    conn: sqlite3.Connection, ticker: str, user_id: str = DEFAULT_USER_ID
) -> Position | None:
    row = conn.execute(
        "SELECT * FROM positions WHERE user_id = ? AND ticker = ?", (user_id, _norm(ticker))
    ).fetchone()
    return Position.from_row(row) if row else None


def list_positions(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> list[Position]:
    rows = conn.execute(
        "SELECT * FROM positions WHERE user_id = ? ORDER BY ticker", (user_id,)
    ).fetchall()
    return [Position.from_row(r) for r in rows]


def upsert_position(
    conn: sqlite3.Connection,
    ticker: str,
    quantity: float,
    avg_cost: float,
    user_id: str = DEFAULT_USER_ID,
) -> Position:
    """Insert or overwrite the position for a ticker with the given quantity and average cost."""
    symbol = _norm(ticker)
    conn.execute(
        """
        INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (user_id, ticker) DO UPDATE SET
            quantity = excluded.quantity,
            avg_cost = excluded.avg_cost,
            updated_at = excluded.updated_at
        """,
        (_new_id(), user_id, symbol, quantity, avg_cost, _now()),
    )
    row = conn.execute(
        "SELECT * FROM positions WHERE user_id = ? AND ticker = ?", (user_id, symbol)
    ).fetchone()
    return Position.from_row(row)


def delete_position(
    conn: sqlite3.Connection, ticker: str, user_id: str = DEFAULT_USER_ID
) -> bool:
    """Remove a position, e.g. when it is fully sold. False if there was none."""
    cursor = conn.execute(
        "DELETE FROM positions WHERE user_id = ? AND ticker = ?", (user_id, _norm(ticker))
    )
    return cursor.rowcount > 0


# --- trades ----------------------------------------------------------------


def insert_trade(
    conn: sqlite3.Connection,
    ticker: str,
    side: str,
    quantity: float,
    price: float,
    user_id: str = DEFAULT_USER_ID,
) -> Trade:
    """Append a filled trade to the log. side is 'buy' or 'sell'."""
    trade = Trade(
        id=_new_id(),
        user_id=user_id,
        ticker=_norm(ticker),
        side=side,
        quantity=quantity,
        price=price,
        executed_at=_now(),
    )
    conn.execute(
        """
        INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (trade.id, trade.user_id, trade.ticker, trade.side, trade.quantity, trade.price,
         trade.executed_at),
    )
    return trade


def list_trades(
    conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID, limit: int | None = None
) -> list[Trade]:
    """Trades newest first, optionally capped at limit."""
    sql = "SELECT * FROM trades WHERE user_id = ? ORDER BY executed_at DESC, rowid DESC"
    params: tuple[Any, ...] = (user_id,)
    if limit is not None:
        sql += " LIMIT ?"
        params += (limit,)
    return [Trade.from_row(r) for r in conn.execute(sql, params).fetchall()]


# --- portfolio_snapshots ---------------------------------------------------


def insert_snapshot(
    conn: sqlite3.Connection, total_value: float, user_id: str = DEFAULT_USER_ID
) -> PortfolioSnapshot:
    snapshot = PortfolioSnapshot(
        id=_new_id(), user_id=user_id, total_value=total_value, recorded_at=_now()
    )
    conn.execute(
        """
        INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at)
        VALUES (?, ?, ?, ?)
        """,
        (snapshot.id, snapshot.user_id, snapshot.total_value, snapshot.recorded_at),
    )
    return snapshot


def list_snapshots(
    conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID, limit: int | None = None
) -> list[PortfolioSnapshot]:
    """Snapshots oldest first (chart order). limit keeps the most recent N."""
    if limit is None:
        rows = conn.execute(
            "SELECT * FROM portfolio_snapshots WHERE user_id = ? ORDER BY recorded_at, rowid",
            (user_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM (
                SELECT *, rowid AS seq FROM portfolio_snapshots WHERE user_id = ?
                ORDER BY recorded_at DESC, seq DESC LIMIT ?
            ) ORDER BY recorded_at, seq
            """,
            (user_id, limit),
        ).fetchall()
    return [PortfolioSnapshot.from_row(r) for r in rows]


# --- chat_messages ---------------------------------------------------------


def insert_chat_message(
    conn: sqlite3.Connection,
    role: str,
    content: str,
    actions: Any | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> ChatMessage:
    """Append a chat message. role is 'user' or 'assistant'; actions is JSON-serialisable."""
    message = ChatMessage(
        id=_new_id(),
        user_id=user_id,
        role=role,
        content=content,
        actions=actions,
        created_at=_now(),
    )
    conn.execute(
        """
        INSERT INTO chat_messages (id, user_id, role, content, actions, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (message.id, message.user_id, message.role, message.content,
         json.dumps(actions) if actions is not None else None, message.created_at),
    )
    return message


def list_recent_chat_messages(
    conn: sqlite3.Connection, limit: int = 20, user_id: str = DEFAULT_USER_ID
) -> list[ChatMessage]:
    """The most recent messages, returned oldest first for LLM context."""
    rows = conn.execute(
        """
        SELECT * FROM (
            SELECT *, rowid AS seq FROM chat_messages WHERE user_id = ?
            ORDER BY created_at DESC, seq DESC LIMIT ?
        ) ORDER BY created_at, seq
        """,
        (user_id, limit),
    ).fetchall()
    return [ChatMessage.from_row(r) for r in rows]
