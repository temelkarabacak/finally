"""REST router for portfolio reads and trade execution: GET/POST /api/portfolio."""

from __future__ import annotations

import logging
import re
import sqlite3
from collections.abc import Callable
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.market import MarketDataSource, PriceCache
from app.market.interface import normalize_ticker

from .snapshots import get_snapshot_history
from .trades import TradeError, execute_trade
from .valuation import portfolio_view

logger = logging.getLogger(__name__)

_TICKER_PATTERN = re.compile(r"^[A-Z.\-]+$")


class TradeRequest(BaseModel):
    """Request body for POST /api/portfolio/trade."""

    ticker: str = Field(min_length=1)
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0)

    @field_validator("ticker")
    @classmethod
    def _normalize_and_validate(cls, value: str) -> str:
        normalized = normalize_ticker(value)
        if not normalized or not _TICKER_PATTERN.match(normalized):
            raise ValueError("ticker must contain only letters, '.', and '-'")
        return normalized


def create_portfolio_router(
    get_conn: Callable[[], sqlite3.Connection],
    market_source: MarketDataSource,
    price_cache: PriceCache,
) -> APIRouter:
    """Create the portfolio router with injected DB connection, source, and cache.

    Factory pattern (mirrors create_watchlist_router): returns a fresh
    APIRouter per call so tests can build it repeatedly.
    """
    router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

    @router.get("")
    async def get_portfolio() -> dict:
        """Return cash balance, positions, holdings value, total value, and unrealized P&L."""
        conn = get_conn()
        return portfolio_view(conn, price_cache)

    @router.get("/history")
    async def get_history() -> list[dict]:
        """Return recorded portfolio value snapshots, oldest first.

        200 with [] when nothing has been recorded yet -- an empty history
        is a valid state, not a missing resource.
        """
        conn = get_conn()
        return get_snapshot_history(conn)

    @router.post("/trade")
    async def trade(request: TradeRequest) -> dict:
        """Execute a market order. Rejections return 400 with a human-readable reason."""
        conn = get_conn()

        try:
            result = execute_trade(
                conn, price_cache, request.ticker, request.side, request.quantity
            )
        except TradeError as err:
            raise HTTPException(status_code=400, detail=err.detail) from err

        if request.side == "buy":
            try:
                await market_source.add_ticker(request.ticker)
            except Exception:
                logger.exception(
                    "add_ticker failed after a committed buy of %s", request.ticker
                )

        return result

    return router
