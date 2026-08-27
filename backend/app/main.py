"""FastAPI entry point: wires market data, database, and static frontend serving."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.db import get_active_tickers, get_db, init_db
from app.market import (
    FailoverMarketDataSource,
    PriceCache,
    create_market_data_source,
    create_stream_router,
)
from app.market.massive_client import MassiveDataSource
from app.portfolio import create_portfolio_router, start_snapshot_task, stop_snapshot_task
from app.watchlist import create_watchlist_router

logger = logging.getLogger(__name__)

# Exactly one PriceCache instance for the whole process. A second instance
# would silently split SSE reads from watchlist reads.
cache = PriceCache()
source = create_market_data_source(cache)

# A bare truthiness check is wrong here: the literal string "false" is
# truthy in Python. Mirrors app/market/factory.py's MASSIVE_API_KEY idiom.
llm_mock_enabled = os.environ.get("LLM_MOCK", "").strip().lower() == "true"

# Imported here, after market-source selection above, rather than in the
# top import block: importing litellm triggers python-dotenv loading the
# project-root .env file as a side effect (litellm/__init__.py), which
# would otherwise set MASSIVE_API_KEY from .env before
# create_market_data_source() reads the environment above -- making the
# chosen data source depend on import order instead of the explicitly-set
# environment.
from app.llm import create_chat_router  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the database and start the market data source."""
    init_db()
    conn = get_db()
    tickers = get_active_tickers(conn)

    await source.start(tickers)

    # Started unconditionally, never gated on a first trade (D-04): a
    # freshly launched app accumulates a flat $10,000 history from minute
    # one regardless of whether the user has traded yet.
    app.state.snapshot_task = start_snapshot_task(get_db, cache)

    app.state.cache = cache
    app.state.source = source
    app.state.db = conn

    logger.info("FinAlly backend started with %d active tickers", len(tickers))

    yield

    # Stopped before the source and the connection so the loop can never
    # touch a closed connection or a stopped cache.
    await stop_snapshot_task(app.state.snapshot_task)
    await source.stop()
    conn.close()
    logger.info("FinAlly backend shut down")


app = FastAPI(lifespan=lifespan, title="FinAlly")


@app.get("/api/health")
async def health() -> dict:
    """Liveness probe. Read-only: touches neither the database nor the source.

    Reports which market data source is currently active — read through
    FailoverMarketDataSource.active when the source is wrapped, so a
    completed failover is reported honestly instead of still claiming the
    provider it started with. Never reports the API key, a file path, or a
    version.
    """
    active_source = source.active if isinstance(source, FailoverMarketDataSource) else source
    market_source = "massive" if isinstance(active_source, MassiveDataSource) else "simulator"
    return {"status": "ok", "market_source": market_source}


app.include_router(create_watchlist_router(get_db, source, cache))
app.include_router(create_portfolio_router(get_db, source, cache))
app.include_router(create_chat_router(get_db, source, cache, mock=llm_mock_enabled))
app.include_router(create_stream_router(cache))

# Registered last: /api/* routes above always win because FastAPI resolves
# routes in registration order, and only unmatched paths fall through here.
app.frontend(
    "/",
    directory=Path(__file__).resolve().parents[1] / "static",
    fallback="index.html",
    check_dir=False,
)
