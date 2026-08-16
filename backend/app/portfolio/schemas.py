"""Request and response models for the portfolio endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class PositionOut(BaseModel):
    ticker: str
    quantity: float
    avg_cost: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    pct_change: float


class PortfolioOut(BaseModel):
    cash_balance: float
    positions: list[PositionOut]
    positions_value: float
    total_value: float
    unrealized_pnl: float


class TradeRequest(BaseModel):
    ticker: str
    quantity: float
    side: Literal["buy", "sell"]


class TradeOut(BaseModel):
    ticker: str
    side: str
    quantity: float
    price: float
    executed_at: str


class TradeResultOut(BaseModel):
    trade: TradeOut
    portfolio: PortfolioOut


class SnapshotOut(BaseModel):
    total_value: float
    recorded_at: str
