"""The active ticker set: watchlist union open positions (PLAN.md section 6)."""

from __future__ import annotations

import sqlite3

from app.db import get_position, list_positions, list_watchlist
from app.market import MarketDataSource


def active_tickers(conn: sqlite3.Connection) -> list[str]:
    """Every ticker the market data source should be pricing."""
    tickers = {entry.ticker for entry in list_watchlist(conn)}
    tickers |= {position.ticker for position in list_positions(conn)}
    return sorted(tickers)


async def prune_ticker(
    conn: sqlite3.Connection, source: MarketDataSource, ticker: str
) -> None:
    """Stop pricing a ticker once it is neither watched nor held.

    A ticker dropped from the watchlist stays tracked while a position still
    references it, so P&L keeps updating until the position is closed.
    """
    if get_position(conn, ticker) is not None:
        return
    if any(entry.ticker == ticker for entry in list_watchlist(conn)):
        return
    await source.remove_ticker(ticker)
