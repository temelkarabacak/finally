"""FastAPI entry point: wires market data, database, and static frontend serving."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.db import get_active_tickers, get_db, get_watchlist_tickers, init_db
from app.market import PriceCache, create_market_data_source, create_stream_router

logger = logging.getLogger(__name__)

# Exactly one PriceCache instance for the whole process. A second instance
# would silently split SSE reads from watchlist reads.
cache = PriceCache()
source = create_market_data_source(cache)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the database and start the market data source."""
    init_db()
    conn = get_db()
    tickers = get_active_tickers(conn)

    await source.start(tickers)

    app.state.cache = cache
    app.state.source = source
    app.state.db = conn

    logger.info("FinAlly backend started with %d active tickers", len(tickers))

    yield

    await source.stop()
    conn.close()
    logger.info("FinAlly backend shut down")


app = FastAPI(lifespan=lifespan, title="FinAlly")


@app.get("/api/health")
async def health() -> dict:
    """Liveness probe. Read-only: touches neither the database nor the source."""
    return {"status": "ok"}


@app.get("/api/watchlist")
async def get_watchlist() -> list[dict]:
    """Return watchlist tickers with their latest cached prices.

    Plan 01-02 moves this into app/watchlist/router.py and adds the
    mutation routes (POST/DELETE).
    """
    conn = get_db()
    tickers = get_watchlist_tickers(conn)

    result = []
    for ticker in tickers:
        update = cache.get(ticker)
        if update is None:
            result.append(
                {
                    "ticker": ticker,
                    "price": None,
                    "previous_price": None,
                    "change": None,
                    "change_percent": None,
                    "direction": None,
                }
            )
        else:
            data = update.to_dict()
            result.append(
                {
                    "ticker": data["ticker"],
                    "price": data["price"],
                    "previous_price": data["previous_price"],
                    "change": data["change"],
                    "change_percent": data["change_percent"],
                    "direction": data["direction"],
                }
            )
    return result


app.include_router(create_stream_router(cache))

# Registered last: /api/* routes above always win because FastAPI resolves
# routes in registration order, and only unmatched paths fall through here.
app.frontend(
    "/",
    directory=Path(__file__).resolve().parents[1] / "static",
    fallback="index.html",
    check_dir=False,
)
