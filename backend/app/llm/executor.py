"""Applies the actions the assistant asked for: market orders and watchlist edits.

Trades run through app.portfolio.execute_trade, the same path as manual trades, so
validation and snapshotting stay identical. A rejection is reported back in the chat
reply instead of failing the whole turn.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from app.db import add_watchlist_ticker, remove_watchlist_ticker
from app.market import MarketDataSource, PriceCache
from app.portfolio import TradeError, prune_ticker
from app.portfolio import execute_trade as execute_market_order

from .schema import TradeInstruction, WatchlistChange


def execute_trade(
    conn: sqlite3.Connection, cache: PriceCache, instruction: TradeInstruction
) -> dict[str, Any]:
    """Execute one market order. Returns a result dict with status executed or rejected."""
    ticker = instruction.ticker.strip().upper()
    result: dict[str, Any] = {
        "ticker": ticker,
        "side": instruction.side,
        "quantity": instruction.quantity,
    }
    try:
        trade = execute_market_order(
            conn, cache, ticker, instruction.side, instruction.quantity
        )
    except TradeError as error:
        return _rejected(result, str(error))

    result.update(price=trade.price, status="executed", error=None)
    return result


async def apply_watchlist_change(
    conn: sqlite3.Connection, source: MarketDataSource, change: WatchlistChange
) -> dict[str, Any]:
    """Add or remove a watchlist ticker, keeping the market data source in step."""
    ticker = change.ticker.strip().upper()
    result: dict[str, Any] = {"ticker": ticker, "action": change.action}

    if change.action == "add":
        if not add_watchlist_ticker(conn, ticker):
            return _rejected(result, f"{ticker} is already on the watchlist")
        await source.add_ticker(ticker)
    else:
        if not remove_watchlist_ticker(conn, ticker):
            return _rejected(result, f"{ticker} is not on the watchlist")
        await prune_ticker(conn, source, ticker)

    result.update(status="executed", error=None)
    return result


def _rejected(result: dict[str, Any], error: str) -> dict[str, Any]:
    result.update(status="rejected", error=error)
    return result
