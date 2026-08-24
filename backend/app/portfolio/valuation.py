"""Shared portfolio valuation: positions, total value, and the /api/portfolio body.

This is the single place portfolio arithmetic lives. GET /api/portfolio, the
trade response, and the snapshot recorder all call these functions rather
than repeating the formula, so the three surfaces can never disagree.
"""

from __future__ import annotations

import sqlite3

from app.db import DEFAULT_USER_ID
from app.market import PriceCache

POSITION_EPSILON = 1e-9  # quantities at or below this are treated as zero
QUANTITY_PRECISION = 8  # decimal places quantity and avg_cost are rounded to on write


def position_views(
    conn: sqlite3.Connection, cache: PriceCache, user_id: str = DEFAULT_USER_ID
) -> list[dict]:
    """Return one dict per open position, valued against the live price cache.

    A ticker with no cached price falls back to avg_cost for valuation and
    reports current_price: None, so a position never shows blank or NaN P&L.
    """
    rows = conn.execute(
        "SELECT ticker, quantity, avg_cost FROM positions "
        "WHERE user_id = ? AND quantity > ? ORDER BY ticker",
        (user_id, POSITION_EPSILON),
    ).fetchall()

    views = []
    for ticker, quantity, avg_cost in rows:
        current_price = cache.get_price(ticker)
        effective_price = current_price if current_price is not None else avg_cost
        market_value = quantity * effective_price
        unrealized_pnl = (effective_price - avg_cost) * quantity
        unrealized_pnl_percent = (
            0.0 if avg_cost == 0 else (effective_price - avg_cost) / avg_cost * 100
        )
        views.append(
            {
                "ticker": ticker,
                "quantity": round(quantity, QUANTITY_PRECISION),
                "avg_cost": round(avg_cost, 2),
                "current_price": current_price,
                "market_value": round(market_value, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "unrealized_pnl_percent": round(unrealized_pnl_percent, 2),
            }
        )
    return views


def compute_total_value(
    conn: sqlite3.Connection, cache: PriceCache, user_id: str = DEFAULT_USER_ID
) -> float:
    """Cash balance plus the market value of every open position."""
    cash = conn.execute(
        "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
    ).fetchone()[0]
    holdings_value = sum(view["market_value"] for view in position_views(conn, cache, user_id))
    return round(cash + holdings_value, 2)


def portfolio_view(
    conn: sqlite3.Connection, cache: PriceCache, user_id: str = DEFAULT_USER_ID
) -> dict:
    """Assemble the GET /api/portfolio response body.

    holdings_value and unrealized_pnl are derived from the same
    position_views list returned here, so the three numbers can never
    disagree with each other.
    """
    cash = conn.execute(
        "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
    ).fetchone()[0]
    positions = position_views(conn, cache, user_id)
    holdings_value = round(sum(view["market_value"] for view in positions), 2)
    unrealized_pnl = round(sum(view["unrealized_pnl"] for view in positions), 2)
    total_value = round(cash + holdings_value, 2)
    return {
        "cash_balance": round(cash, 2),
        "holdings_value": holdings_value,
        "total_value": total_value,
        "unrealized_pnl": unrealized_pnl,
        "positions": positions,
    }
