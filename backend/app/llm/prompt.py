"""System prompt and per-turn message assembly for the chat call.

The portfolio context is rebuilt fresh every turn and sent as its own
message, never folded into SYSTEM_PROMPT (which stays static and
cacheable) and never persisted to chat_messages history -- only
role/content conversational turns are replayed (see persistence.py).
"""

from __future__ import annotations

import sqlite3

from app.db import get_watchlist_tickers
from app.market import PriceCache
from app.portfolio.valuation import portfolio_view

SYSTEM_PROMPT = """You are FinAlly, an AI trading assistant embedded in a simulated \
trading terminal. You analyze portfolio composition, concentration risk, and P&L; \
suggest trades with clear reasoning; execute trades when the user asks or agrees; \
manage the watchlist on request; and stay concise and data-driven -- never use \
urgency, scarcity, or shaming language. Report every action outcome exactly as the \
system reports it back to you, never assuming an action succeeded. Respond only with \
JSON matching this schema, with no extra commentary outside the JSON:

{"message": "Your cash is $10,000.00 with no open positions.", "trades": [], \
"watchlist_changes": []}
"""


def build_portfolio_context(conn: sqlite3.Connection, price_cache: PriceCache) -> dict:
    """Compact dict of this turn's live cash, positions+P&L, and watchlist prices.

    Reuses portfolio_view() for the cash/position arithmetic -- never
    recomputed here -- so the chat context can never disagree with
    GET /api/portfolio or a trade response.
    """
    view = portfolio_view(conn, price_cache)
    watchlist = []
    for ticker in get_watchlist_tickers(conn):
        price = price_cache.get_price(ticker)
        watchlist.append({"ticker": ticker, "price": price})

    return {
        "cash_balance": view["cash_balance"],
        "total_value": view["total_value"],
        "unrealized_pnl": view["unrealized_pnl"],
        "positions": [
            {
                "ticker": p["ticker"],
                "quantity": p["quantity"],
                "avg_cost": p["avg_cost"],
                "current_price": p["current_price"],
                "unrealized_pnl": p["unrealized_pnl"],
            }
            for p in view["positions"]
        ],
        "watchlist": watchlist,
    }


def build_messages(
    system_prompt: str,
    portfolio_ctx: dict,
    history: list[dict],
    user_text: str,
) -> list[dict]:
    """Assemble the OpenAI-shaped messages list for this turn.

    Order: static system prompt, then this turn's fresh portfolio context
    as its own message, then replayed history (role/content only), then
    the new user turn last.
    """
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    messages.append({"role": "system", "content": f"Current portfolio: {portfolio_ctx}"})
    for row in history:
        messages.append({"role": row["role"], "content": row["content"]})
    messages.append({"role": "user", "content": user_text})
    return messages
