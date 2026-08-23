"""Watchlist subsystem for FinAlly.

Public API:
    create_watchlist_router - Factory returning the /api/watchlist APIRouter
    AddTickerRequest        - Pydantic request body for POST /api/watchlist
"""

from .router import AddTickerRequest, create_watchlist_router

__all__ = [
    "create_watchlist_router",
    "AddTickerRequest",
]
