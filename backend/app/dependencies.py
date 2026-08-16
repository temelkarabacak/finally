"""FastAPI dependencies for the app-wide market data singletons."""

from __future__ import annotations

from fastapi import Request

from app.market import MarketDataSource, PriceCache


def get_price_cache(request: Request) -> PriceCache:
    """The shared price cache that the market data source writes into."""
    return request.app.state.price_cache


def get_market_source(request: Request) -> MarketDataSource:
    """The running market data source (simulator or Massive)."""
    return request.app.state.market_source
