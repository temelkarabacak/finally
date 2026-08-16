"""Portfolio REST endpoints."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from app.db import get_db, list_snapshots
from app.dependencies import get_market_source, get_price_cache
from app.market import MarketDataSource, PriceCache

from .active_tickers import prune_ticker
from .schemas import PortfolioOut, SnapshotOut, TradeRequest, TradeResultOut
from .service import TradeError, build_portfolio, execute_trade

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("", response_model=PortfolioOut)
def read_portfolio(
    conn: sqlite3.Connection = Depends(get_db),
    cache: PriceCache = Depends(get_price_cache),
) -> dict:
    """Cash, positions marked to market, and total value."""
    return build_portfolio(conn, cache)


@router.post("/trade", response_model=TradeResultOut)
async def post_trade(
    body: TradeRequest,
    conn: sqlite3.Connection = Depends(get_db),
    cache: PriceCache = Depends(get_price_cache),
    source: MarketDataSource = Depends(get_market_source),
) -> dict:
    """Execute a market order and return the fill plus the updated portfolio."""
    try:
        trade = execute_trade(conn, cache, body.ticker, body.side, body.quantity)
    except TradeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await prune_ticker(conn, source, trade.ticker)
    # Commit before responding: get_db's commit runs after the response is sent,
    # so a client refetching immediately would otherwise read pre-trade state.
    conn.commit()
    return {
        "trade": {
            "ticker": trade.ticker,
            "side": trade.side,
            "quantity": trade.quantity,
            "price": trade.price,
            "executed_at": trade.executed_at,
        },
        "portfolio": build_portfolio(conn, cache),
    }


@router.get("/history", response_model=list[SnapshotOut])
def read_history(conn: sqlite3.Connection = Depends(get_db)) -> list[dict]:
    """Portfolio value snapshots, oldest first, for the P&L chart."""
    return [
        {"total_value": s.total_value, "recorded_at": s.recorded_at}
        for s in list_snapshots(conn)
    ]
