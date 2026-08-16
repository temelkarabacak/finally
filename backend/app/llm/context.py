"""Builds the live portfolio snapshot that is injected into the LLM prompt."""

from __future__ import annotations

import sqlite3
from typing import Any

from app.db import list_watchlist
from app.market import PriceCache
from app.portfolio import build_portfolio


def build_portfolio_context(conn: sqlite3.Connection, cache: PriceCache) -> dict[str, Any]:
    """The same view as GET /api/portfolio, plus the watchlist with live prices."""
    watchlist = []
    for entry in list_watchlist(conn):
        update = cache.get(entry.ticker)
        watchlist.append(
            {
                "ticker": entry.ticker,
                "price": update.price if update else None,
                "change_percent": round(update.change_percent, 2) if update else None,
            }
        )

    context = build_portfolio(conn, cache)
    context["watchlist"] = watchlist
    return context
