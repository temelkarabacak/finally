"""Pydantic contract for the chat API and the LLM structured-output response.

Mirrors the TradeRequest/AddTickerRequest convention in
app/portfolio/router.py and app/watchlist/router.py: the ticker field
validator normalizes and rejects anything outside _TICKER_PATTERN, and
quantity is constrained at the field level rather than in a handler.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.market.interface import normalize_ticker

_TICKER_PATTERN = re.compile(r"^[A-Z.\-]+$")


class ChatRequest(BaseModel):
    """Request body for POST /api/chat."""

    message: str = Field(min_length=1)


class TradeAction(BaseModel):
    """One trade the model wants auto-executed."""

    ticker: str
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0)

    @field_validator("ticker")
    @classmethod
    def _normalize_and_validate(cls, value: str) -> str:
        normalized = normalize_ticker(value)
        if not normalized or not _TICKER_PATTERN.match(normalized):
            raise ValueError("ticker must contain only letters, '.', and '-'")
        return normalized


class WatchlistChange(BaseModel):
    """One watchlist add/remove the model wants auto-executed."""

    ticker: str
    action: Literal["add", "remove"]

    @field_validator("ticker")
    @classmethod
    def _normalize_and_validate(cls, value: str) -> str:
        normalized = normalize_ticker(value)
        if not normalized or not _TICKER_PATTERN.match(normalized):
            raise ValueError("ticker must contain only letters, '.', and '-'")
        return normalized


class ChatResponse(BaseModel):
    """The LLM's structured-output contract, also produced by mock.py.

    default_factory (not a bare `= []`) is what makes an omitted field
    parse to an empty list rather than None -- a null trades/watchlist_changes
    would otherwise crash the auto-execution loop in plan 03-02.
    """

    message: str
    trades: list[TradeAction] = Field(default_factory=list)
    watchlist_changes: list[WatchlistChange] = Field(default_factory=list)
