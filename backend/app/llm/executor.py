"""Executes LLM-proposed trades and watchlist changes through the exact
validated code paths the manual trade bar and watchlist panel use.

The reported actions payload is built exclusively from these functions'
return values -- never from the model's proposed trades/watchlist_changes
list -- so a claimed-but-not-executed action is structurally unrepresentable
(AI-SPEC EV-1, T-03-11). Neither function opens an outer BEGIN: execute_trade()
already owns its own transaction (see app/portfolio/trades.py's module
docstring and 03-RESEARCH.md Pitfall 1) -- wrapping it in a surrounding BEGIN
would nest and SQLite raises sqlite3.OperationalError: cannot start a
transaction within a transaction.
"""

from __future__ import annotations

import logging
import sqlite3

from app.db import add_watchlist_ticker, remove_watchlist_ticker, ticker_has_open_position
from app.market import MarketDataSource, PriceCache
from app.market.interface import normalize_ticker
from app.portfolio import TradeError, execute_trade

from .schemas import ChatResponse, TradeAction, WatchlistChange

logger = logging.getLogger(__name__)


async def apply_watchlist_change(
    conn: sqlite3.Connection,
    market_source: MarketDataSource,
    change: WatchlistChange,
) -> dict:
    """Mirror watchlist/router.py's add/remove handlers exactly (lines
    79-115) so the chat path can never diverge from the manual endpoint's
    rejection/idempotency rules. Database write first, source call second --
    the same ordering the manual endpoint uses.
    """
    ticker = normalize_ticker(change.ticker)

    if change.action == "add":
        inserted = add_watchlist_ticker(conn, ticker)
        if not inserted:
            return {
                "success": False,
                "ticker": ticker,
                "action": "add",
                "reason": "Already on watchlist",
            }
        await market_source.add_ticker(ticker)
        return {"success": True, "ticker": ticker, "action": "add"}

    removed = remove_watchlist_ticker(conn, ticker)
    if not removed:
        return {
            "success": False,
            "ticker": ticker,
            "action": "remove",
            "reason": "Not on watchlist",
        }
    if not ticker_has_open_position(conn, ticker):
        await market_source.remove_ticker(ticker)
    return {"success": True, "ticker": ticker, "action": "remove"}


async def _execute_one_trade(
    conn: sqlite3.Connection,
    price_cache: PriceCache,
    market_source: MarketDataSource,
    trade: TradeAction,
) -> dict:
    """Bare call into execute_trade() -- it already owns its own transaction."""
    try:
        result = execute_trade(conn, price_cache, trade.ticker, trade.side, trade.quantity)
    except TradeError as err:
        return {
            "success": False,
            "ticker": trade.ticker,
            "side": trade.side,
            "quantity": trade.quantity,
            "reason": err.detail,
        }

    if trade.side == "buy":
        try:
            await market_source.add_ticker(result["ticker"])
        except Exception:
            logger.exception(
                "add_ticker failed after a chat-executed buy of %s", result["ticker"]
            )

    return {
        "success": True,
        "ticker": result["ticker"],
        "side": result["side"],
        "quantity": result["quantity"],
        "price": result["price"],
        "cash_balance": result["cash_balance"],
        "total_value": result["total_value"],
    }


async def execute_actions(
    conn: sqlite3.Connection,
    price_cache: PriceCache,
    market_source: MarketDataSource,
    parsed: ChatResponse,
) -> dict:
    """Execute every trade/watchlist_change the model proposed through the
    same validated paths the manual trade bar and watchlist panel call.

    Returns {"trades": [...], "watchlist_changes": [...]} built entirely
    from execution results -- the only channel through which the router and
    the persisted chat_messages.actions JSON learn what actually happened.
    """
    trade_results = [
        await _execute_one_trade(conn, price_cache, market_source, trade)
        for trade in parsed.trades
    ]
    watchlist_results = [
        await apply_watchlist_change(conn, market_source, change)
        for change in parsed.watchlist_changes
    ]

    return {"trades": trade_results, "watchlist_changes": watchlist_results}
