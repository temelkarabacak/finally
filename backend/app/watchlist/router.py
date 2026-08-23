"""REST router for watchlist CRUD: GET/POST/DELETE /api/watchlist."""

from __future__ import annotations

import logging
import re
import sqlite3
from collections.abc import Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.db import add_watchlist_ticker, get_watchlist_tickers, remove_watchlist_ticker
from app.db import ticker_has_open_position as db_ticker_has_open_position
from app.market import MarketDataSource, PriceCache
from app.market.interface import normalize_ticker

logger = logging.getLogger(__name__)

_TICKER_PATTERN = re.compile(r"^[A-Z.\-]+$")


class AddTickerRequest(BaseModel):
    """Request body for POST /api/watchlist."""

    ticker: str = Field(min_length=1)

    @field_validator("ticker")
    @classmethod
    def _normalize_and_validate(cls, value: str) -> str:
        normalized = normalize_ticker(value)
        if not normalized or not _TICKER_PATTERN.match(normalized):
            raise ValueError("ticker must contain only letters, '.', and '-'")
        return normalized


def _entry_for(ticker: str, price_cache: PriceCache) -> dict:
    """Build a watchlist entry dict for ticker, null pricing when unseen."""
    update = price_cache.get(ticker)
    if update is None:
        return {
            "ticker": ticker,
            "price": None,
            "previous_price": None,
            "change": None,
            "change_percent": None,
            "direction": None,
        }
    data = update.to_dict()
    return {
        "ticker": data["ticker"],
        "price": data["price"],
        "previous_price": data["previous_price"],
        "change": data["change"],
        "change_percent": data["change_percent"],
        "direction": data["direction"],
    }


def create_watchlist_router(
    get_conn: Callable[[], sqlite3.Connection],
    market_source: MarketDataSource,
    price_cache: PriceCache,
) -> APIRouter:
    """Create the watchlist router with injected DB connection, source, and cache.

    Factory pattern (mirrors create_stream_router): returns a fresh APIRouter
    per call so tests can build it repeatedly without routes piling up.
    """
    router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

    @router.get("")
    async def list_watchlist() -> list[dict]:
        """Return watchlist tickers with their latest cached prices."""
        conn = get_conn()
        tickers = get_watchlist_tickers(conn)
        return [_entry_for(ticker, price_cache) for ticker in tickers]

    @router.post("", status_code=201)
    async def add_to_watchlist(request: AddTickerRequest) -> dict:
        """Add a ticker to the watchlist and the market data source.

        Database write happens first: if the source call fails, the row
        still reflects intent and the next startup reconciles from
        get_active_tickers().
        """
        conn = get_conn()
        ticker = normalize_ticker(request.ticker)

        inserted = add_watchlist_ticker(conn, ticker)
        if not inserted:
            raise HTTPException(status_code=409, detail="Ticker already on watchlist")

        await market_source.add_ticker(ticker)
        return _entry_for(ticker, price_cache)

    @router.delete("/{ticker}", status_code=204)
    async def remove_from_watchlist(ticker: str) -> None:
        """Remove a ticker from the watchlist.

        The market source only stops tracking the ticker when no open
        position still references it; re-evaluated from the database on
        every call, so a second DELETE hits the 404 branch and never
        reaches the source a second time.
        """
        conn = get_conn()
        normalized = normalize_ticker(ticker)

        removed = remove_watchlist_ticker(conn, normalized)
        if not removed:
            raise HTTPException(status_code=404, detail="Ticker not on watchlist")

        if not db_ticker_has_open_position(conn, normalized):
            await market_source.remove_ticker(normalized)

    return router
