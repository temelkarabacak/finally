"""Default seed data for a freshly initialized database."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime

DEFAULT_USER_ID = "default"
DEFAULT_CASH_BALANCE = 10000.0

# Ten default watchlist tickers, per planning/PLAN.md section 7.
DEFAULT_WATCHLIST: list[str] = [
    "AAPL",
    "GOOGL",
    "MSFT",
    "AMZN",
    "TSLA",
    "NVDA",
    "META",
    "JPM",
    "V",
    "NFLX",
]


def seed_defaults(conn: sqlite3.Connection) -> None:
    """Insert the default user profile and watchlist rows.

    Uses INSERT OR IGNORE so a partially-seeded database converges to the
    full seed set rather than raising on a re-run.
    """
    now = datetime.now(UTC).isoformat()

    conn.execute(
        "INSERT OR IGNORE INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
        (DEFAULT_USER_ID, DEFAULT_CASH_BALANCE, now),
    )

    for ticker in DEFAULT_WATCHLIST:
        conn.execute(
            "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (uuid.uuid4().hex, DEFAULT_USER_ID, ticker, now),
        )
