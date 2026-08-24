"""Trade execution: the transactional core of the portfolio subsystem.

The shared connection is opened with autocommit=True
(backend/app/db/connection.py:51), under which Connection.commit() and
Connection.rollback() are documented no-ops and each execute() commits on
its own. execute_trade therefore wraps its writes in an explicit SQL
BEGIN/COMMIT (ROLLBACK on any exception) so a trade's four writes land as
one unit or not at all -- without this, a failure between the position
write and the cash write would leave the user holding shares they never
paid for.

Every SQLite call in this function is synchronous and direct -- no
thread-pool offload, no coroutine awaited between BEGIN and COMMIT. On a
single-threaded event loop a coroutine only yields at an await point, so a
block with no await inside it is what serializes this trade against a
concurrent trade request and against the periodic snapshot writer.
Introducing an await mid-transaction would reopen exactly the interleaving
window the transaction exists to close, so no asyncio.Lock is needed.
"""

from __future__ import annotations

import logging
import math
import sqlite3
import uuid
from datetime import UTC, datetime

from app.db import DEFAULT_USER_ID
from app.market import PriceCache
from app.market.interface import normalize_ticker

from .snapshots import record_snapshot
from .valuation import POSITION_EPSILON, QUANTITY_PRECISION, compute_total_value, portfolio_view

logger = logging.getLogger(__name__)


class TradeError(Exception):
    """Raised when a trade is rejected outright, before any write occurs."""

    def __init__(self, detail: str, code: str) -> None:
        super().__init__(detail)
        self.detail = detail
        self.code = code


def new_position_after_buy(
    old_qty: float, old_avg_cost: float, buy_qty: float, price: float
) -> tuple[float, float]:
    """Weighted-average cost after adding buy_qty shares at price.

    No zero-quantity branch: when old_qty is 0 the first term vanishes and
    the result is exactly price, which is the correct basis for a freshly
    (re)opened position. A special case here would be dead code that could
    drift from the general formula.
    """
    new_qty = old_qty + buy_qty
    new_avg_cost = (old_qty * old_avg_cost + buy_qty * price) / new_qty
    return new_qty, new_avg_cost


def execute_trade(
    conn: sqlite3.Connection,
    cache: PriceCache,
    ticker: str,
    side: str,
    quantity: float,
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    """Validate and execute a market order, writing positions/trades/cash/snapshot as one unit.

    Every rejection happens before any write: the request is refused in
    full, and the requested quantity is never reduced to whatever the
    balance or holding could afford.
    """
    ticker = normalize_ticker(ticker)

    if side not in ("buy", "sell"):
        raise TradeError(f"Invalid trade side {side!r}.", "invalid_side")
    if not math.isfinite(quantity) or quantity <= 0:
        raise TradeError("Quantity must be a positive, finite number.", "invalid_quantity")

    price = cache.get_price(ticker)
    if price is None:
        raise TradeError(
            f"No live price for {ticker} yet — add it to your watchlist first.", "no_price"
        )

    row = conn.execute(
        "SELECT quantity, avg_cost FROM positions WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    ).fetchone()
    old_qty, old_avg_cost = (row[0], row[1]) if row else (0.0, 0.0)
    cash = conn.execute(
        "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
    ).fetchone()[0]

    if side == "buy":
        cost = quantity * price
        if cost > cash + POSITION_EPSILON:
            raise TradeError(
                f"Not enough cash to buy {quantity} {ticker} — try a smaller quantity.",
                "insufficient_cash",
            )
        new_qty, new_avg_cost = new_position_after_buy(old_qty, old_avg_cost, quantity, price)
        new_cash = cash - cost
    else:  # sell
        if quantity > old_qty + POSITION_EPSILON:
            raise TradeError(
                f"You only hold {old_qty} shares of {ticker} — try a smaller quantity.",
                "insufficient_shares",
            )
        new_qty = old_qty - quantity
        new_avg_cost = old_avg_cost  # a sale does not change the basis of shares still held
        new_cash = cash + quantity * price

    if new_qty <= POSITION_EPSILON:
        new_qty = 0.0  # float drift must not leave a dust position alive forever
    new_qty = round(new_qty, QUANTITY_PRECISION)
    new_avg_cost = round(new_avg_cost, QUANTITY_PRECISION)
    new_cash = round(new_cash, 2)

    now_iso = datetime.now(UTC).isoformat()

    conn.execute("BEGIN")
    try:
        conn.execute(
            "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id, ticker) DO UPDATE SET quantity=excluded.quantity, "
            "avg_cost=excluded.avg_cost, updated_at=excluded.updated_at",
            (uuid.uuid4().hex, user_id, ticker, new_qty, new_avg_cost, now_iso),
        )
        conn.execute(
            "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (uuid.uuid4().hex, user_id, ticker, side, quantity, price, now_iso),
        )
        conn.execute(
            "UPDATE users_profile SET cash_balance = ? WHERE id = ?", (new_cash, user_id)
        )
        record_snapshot(conn, compute_total_value(conn, cache, user_id), user_id, now_iso)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    view = portfolio_view(conn, cache, user_id)
    position = next((p for p in view["positions"] if p["ticker"] == ticker), None)

    return {
        "ticker": ticker,
        "side": side,
        "quantity": quantity,
        "price": price,
        "executed_at": now_iso,
        "cash_balance": view["cash_balance"],
        "total_value": view["total_value"],
        "position": position,
    }
