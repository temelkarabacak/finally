"""Watchlist REST endpoints."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from app.db import add_watchlist_ticker, get_db, list_watchlist, remove_watchlist_ticker
from app.dependencies import get_market_source, get_price_cache
from app.market import MarketDataSource, PriceCache
from app.portfolio import prune_ticker

from .schemas import TickerRequest, WatchlistItemOut

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


def _watchlist_view(conn: sqlite3.Connection, cache: PriceCache) -> list[dict]:
    items = []
    for entry in list_watchlist(conn):
        update = cache.get(entry.ticker)
        item = {"ticker": entry.ticker, "added_at": entry.added_at}
        if update:
            item |= {k: v for k, v in update.to_dict().items() if k != "timestamp"}
        items.append(item)
    return items


@router.get("", response_model=list[WatchlistItemOut])
def read_watchlist(
    conn: sqlite3.Connection = Depends(get_db),
    cache: PriceCache = Depends(get_price_cache),
) -> list[dict]:
    """Watched tickers with their latest prices."""
    return _watchlist_view(conn, cache)


@router.post("", response_model=list[WatchlistItemOut], status_code=201)
async def add_ticker(
    body: TickerRequest,
    conn: sqlite3.Connection = Depends(get_db),
    cache: PriceCache = Depends(get_price_cache),
    source: MarketDataSource = Depends(get_market_source),
) -> list[dict]:
    """Add a ticker and start pricing it immediately."""
    symbol = body.ticker.strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="Ticker must not be empty")
    if not add_watchlist_ticker(conn, symbol):
        raise HTTPException(status_code=409, detail=f"{symbol} is already on the watchlist")

    await source.add_ticker(symbol)
    conn.commit()  # See the note in app/portfolio/routes.py: get_db commits too late.
    return _watchlist_view(conn, cache)


@router.delete("/{ticker}", response_model=list[WatchlistItemOut])
async def remove_ticker(
    ticker: str,
    conn: sqlite3.Connection = Depends(get_db),
    cache: PriceCache = Depends(get_price_cache),
    source: MarketDataSource = Depends(get_market_source),
) -> list[dict]:
    """Remove a ticker. It keeps streaming while an open position holds it."""
    symbol = ticker.strip().upper()
    if not remove_watchlist_ticker(conn, symbol):
        raise HTTPException(status_code=404, detail=f"{symbol} is not on the watchlist")

    await prune_ticker(conn, source, symbol)
    conn.commit()  # See the note in app/portfolio/routes.py: get_db commits too late.
    return _watchlist_view(conn, cache)
