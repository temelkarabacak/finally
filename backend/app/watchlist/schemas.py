"""Request and response models for the watchlist endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class TickerRequest(BaseModel):
    ticker: str


class WatchlistItemOut(BaseModel):
    """A watched ticker with its latest cached price. Price fields are null
    until the market data source has published a first tick."""

    ticker: str
    added_at: str
    price: float | None = None
    previous_price: float | None = None
    change: float | None = None
    change_percent: float | None = None
    direction: str | None = None
