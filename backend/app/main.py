"""FastAPI application assembly for FinAlly."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import get_connection, insert_snapshot
from app.llm import router as chat_router
from app.market import (
    PriceCache,
    SimulatorDataSource,
    create_market_data_source,
    create_stream_router,
)
from app.portfolio import active_tickers, total_portfolio_value
from app.portfolio import router as portfolio_router
from app.watchlist import router as watchlist_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SNAPSHOT_INTERVAL_SECONDS = 30

# The Next.js static export is copied here by the Docker build.
STATIC_DIR = Path(__file__).resolve().parents[1] / "static"

health_router = APIRouter(prefix="/api", tags=["system"])


@health_router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe for Docker and deployment platforms."""
    return {"status": "ok"}


def _startup_tickers() -> list[str]:
    conn = get_connection()
    try:
        return active_tickers(conn)
    finally:
        conn.close()


def _record_snapshot(cache: PriceCache) -> None:
    conn = get_connection()
    try:
        insert_snapshot(conn, total_portfolio_value(conn, cache))
        conn.commit()
    finally:
        conn.close()


async def _snapshot_loop(cache: PriceCache, interval: float = SNAPSHOT_INTERVAL_SECONDS) -> None:
    """Record total portfolio value on a fixed cadence for the P&L chart."""
    while True:
        await asyncio.sleep(interval)
        try:
            await asyncio.to_thread(_record_snapshot, cache)
        except Exception:
            logger.exception("Portfolio snapshot failed")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start the market data source and the snapshot task; stop them on shutdown."""
    cache: PriceCache = app.state.price_cache

    async def _failover_to_simulator(tickers: list[str]) -> None:
        # PLAN.md section 6: on a permanent Massive failure, transfer its
        # tracked tickers to the simulator and make it the app's active
        # source. app.state.market_source is read fresh per-request by
        # app.dependencies.get_market_source, so this takes effect immediately.
        logger.warning(
            "Failing over to the GBM simulator for %d tickers", len(tickers)
        )
        simulator = SimulatorDataSource(price_cache=cache)
        await simulator.start(tickers)
        app.state.market_source = simulator

    source = create_market_data_source(cache, on_permanent_failure=_failover_to_simulator)
    app.state.market_source = source

    tickers = await asyncio.to_thread(_startup_tickers)
    await source.start(tickers)
    logger.info(
        "Market data started for %d tickers using %s",
        len(tickers),
        type(app.state.market_source).__name__,
    )

    snapshot_task = asyncio.create_task(_snapshot_loop(cache))
    yield

    snapshot_task.cancel()
    # Stop whatever is active now, not the original `source` — a failover may
    # have replaced it with the simulator.
    await app.state.market_source.stop()


def create_app(price_cache: PriceCache | None = None) -> FastAPI:
    """Build the application. Tests pass a pre-seeded cache for deterministic prices."""
    app = FastAPI(title="FinAlly", version="0.1.0", lifespan=lifespan)
    app.state.price_cache = price_cache or PriceCache()

    app.include_router(health_router)
    app.include_router(create_stream_router(app.state.price_cache))
    app.include_router(portfolio_router)
    app.include_router(watchlist_router)

    app.include_router(chat_router)

    if STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    else:
        logger.warning("No static directory at %s, serving API only", STATIC_DIR)

    return app


app = create_app()
