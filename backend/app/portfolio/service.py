"""Portfolio valuation and market order execution.

All functions take the request's connection and never commit: the caller's
transaction (get_db) makes a trade's cash, position and log writes atomic.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from app.db import (
    Position,
    Trade,
    delete_position,
    get_cash_balance,
    get_position,
    insert_snapshot,
    insert_trade,
    list_positions,
    update_cash_balance,
    upsert_position,
)
from app.market import PriceCache

# Tolerance for float comparison on fractional share quantities and cash.
EPSILON = 1e-9


class TradeError(ValueError):
    """A trade rejected by validation. Rejected outright, never clamped."""


def _price_for(position: Position, cache: PriceCache) -> float:
    """Live price for a held ticker, falling back to cost basis if unpriced."""
    return cache.get_price(position.ticker) or position.avg_cost


def position_view(position: Position, cache: PriceCache) -> dict[str, Any]:
    """A position marked to market, with unrealized P&L."""
    price = _price_for(position, cache)
    market_value = position.quantity * price
    cost_basis = position.quantity * position.avg_cost
    unrealized_pnl = market_value - cost_basis
    return {
        "ticker": position.ticker,
        "quantity": position.quantity,
        "avg_cost": round(position.avg_cost, 4),
        "current_price": round(price, 2),
        "market_value": round(market_value, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "pct_change": round(unrealized_pnl / cost_basis * 100, 2) if cost_basis else 0.0,
    }


def build_portfolio(conn: sqlite3.Connection, cache: PriceCache) -> dict[str, Any]:
    """Cash, marked-to-market positions and totals for GET /api/portfolio."""
    cash = get_cash_balance(conn)
    positions = [position_view(p, cache) for p in list_positions(conn)]
    positions_value = sum(p["market_value"] for p in positions)
    return {
        "cash_balance": round(cash, 2),
        "positions": positions,
        "positions_value": round(positions_value, 2),
        "total_value": round(cash + positions_value, 2),
        "unrealized_pnl": round(sum(p["unrealized_pnl"] for p in positions), 2),
    }


def total_portfolio_value(conn: sqlite3.Connection, cache: PriceCache) -> float:
    """Cash plus the market value of every open position."""
    total = get_cash_balance(conn) + sum(
        p.quantity * _price_for(p, cache) for p in list_positions(conn)
    )
    return round(total, 2)


def execute_trade(
    conn: sqlite3.Connection,
    cache: PriceCache,
    ticker: str,
    side: str,
    quantity: float,
) -> Trade:
    """Fill a market order at the current cached price and snapshot the portfolio.

    Raises TradeError on a positive-quantity, sufficient-cash or sufficient-shares
    violation, which rolls the request transaction back with nothing written.
    """
    symbol = ticker.strip().upper()
    if side not in ("buy", "sell"):
        raise TradeError(f"Unknown side {side!r}, expected 'buy' or 'sell'")
    if quantity <= 0:
        raise TradeError("Quantity must be greater than zero")

    price = cache.get_price(symbol)
    if price is None:
        raise TradeError(f"No live price for {symbol}, add it to the watchlist first")

    cash = get_cash_balance(conn)
    position = get_position(conn, symbol)
    held = position.quantity if position else 0.0

    if side == "buy":
        cost = quantity * price
        if cost > cash + EPSILON:
            raise TradeError(
                f"Insufficient cash: buying {quantity} {symbol} costs {cost:.2f}, "
                f"available {cash:.2f}"
            )
        new_quantity = held + quantity
        cost_basis = held * position.avg_cost + cost if position else cost
        upsert_position(conn, symbol, new_quantity, cost_basis / new_quantity)
        update_cash_balance(conn, round(cash - cost, 2))
    else:
        if quantity > held + EPSILON:
            raise TradeError(
                f"Insufficient shares: selling {quantity} {symbol} exceeds the {held} held"
            )
        new_quantity = held - quantity
        if new_quantity <= EPSILON:
            delete_position(conn, symbol)
        else:
            upsert_position(conn, symbol, new_quantity, position.avg_cost)
        update_cash_balance(conn, round(cash + quantity * price, 2))

    trade = insert_trade(conn, symbol, side, quantity, price)
    insert_snapshot(conn, total_portfolio_value(conn, cache))
    return trade
