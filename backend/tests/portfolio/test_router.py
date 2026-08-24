"""HTTP-level tests for the portfolio routes: status codes and response shapes (TEST-01)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.market.cache import PriceCache
from app.market.seed_prices import SEED_PRICES
from app.portfolio import create_portfolio_router

from .test_trades import FakeMarketSource

_TRADE_RESPONSE_KEYS = {
    "ticker",
    "side",
    "quantity",
    "price",
    "executed_at",
    "cash_balance",
    "total_value",
    "position",
}

_PORTFOLIO_RESPONSE_KEYS = {
    "cash_balance",
    "holdings_value",
    "total_value",
    "unrealized_pnl",
    "positions",
}


@pytest.fixture
def portfolio_client(initialized_db):
    """TestClient wired to a real temp-DB connection, a fake source, and a seeded cache.

    Re-declared locally rather than imported from test_trades, per plan
    guidance -- either is acceptable, but a local declaration avoids
    shadowing/redefinition noise across the two test modules.
    """
    conn = initialized_db
    source = FakeMarketSource()
    cache = PriceCache()
    for ticker, price in SEED_PRICES.items():
        cache.update(ticker, price)

    app = FastAPI()
    app.include_router(create_portfolio_router(lambda: conn, source, cache))

    with TestClient(app) as client:
        yield client, conn, source, cache


class TestGetPortfolio:
    def test_fresh_database_returns_seeded_cash_and_empty_positions(self, portfolio_client):
        client, _conn, _source, _cache = portfolio_client

        response = client.get("/api/portfolio")

        assert response.status_code == 200
        body = response.json()
        assert set(body.keys()) == _PORTFOLIO_RESPONSE_KEYS
        assert body["cash_balance"] == 10000.0
        assert body["total_value"] == 10000.0
        assert body["unrealized_pnl"] == 0.0
        assert body["positions"] == []


class TestGetHistory:
    def test_returns_200_and_array_in_every_state(self, portfolio_client):
        client, _conn, _source, _cache = portfolio_client

        empty_response = client.get("/api/portfolio/history")
        assert empty_response.status_code == 200
        assert isinstance(empty_response.json(), list)
        assert empty_response.json() == []

        client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 1.0}
        )

        populated_response = client.get("/api/portfolio/history")
        assert populated_response.status_code == 200
        assert isinstance(populated_response.json(), list)
        assert len(populated_response.json()) == 1


class TestPostTradeValidation:
    """422 (request validation, never reaches the handler) vs 400 (business rule)."""

    def test_zero_quantity_returns_422(self, portfolio_client):
        client, _conn, _source, _cache = portfolio_client

        response = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 0}
        )

        assert response.status_code == 422

    def test_negative_quantity_returns_422(self, portfolio_client):
        client, _conn, _source, _cache = portfolio_client

        response = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": -1}
        )

        assert response.status_code == 422

    def test_invalid_side_returns_422(self, portfolio_client):
        client, _conn, _source, _cache = portfolio_client

        response = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "side": "hold", "quantity": 1}
        )

        assert response.status_code == 422

    def test_ticker_with_invalid_characters_returns_422(self, portfolio_client):
        client, _conn, _source, _cache = portfolio_client

        response = client.post(
            "/api/portfolio/trade", json={"ticker": "AA$PL", "side": "buy", "quantity": 1}
        )

        assert response.status_code == 422

    def test_insufficient_cash_returns_400_with_detail(self, portfolio_client):
        client, _conn, _source, _cache = portfolio_client

        response = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 100000}
        )

        assert response.status_code == 400
        assert isinstance(response.json()["detail"], str)


class TestPostTradeSuccess:
    def test_lowercase_ticker_normalizes_to_uppercase(self, portfolio_client):
        client, conn, _source, _cache = portfolio_client

        response = client.post(
            "/api/portfolio/trade", json={"ticker": "aapl", "side": "buy", "quantity": 1.0}
        )

        assert response.status_code == 200
        assert response.json()["ticker"] == "AAPL"
        row = conn.execute("SELECT ticker FROM trades WHERE ticker = 'AAPL'").fetchone()
        assert row is not None

    def test_successful_buy_returns_full_response_shape(self, portfolio_client):
        client, _conn, _source, _cache = portfolio_client

        response = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 1.0}
        )

        assert response.status_code == 200
        body = response.json()
        assert set(body.keys()) == _TRADE_RESPONSE_KEYS
        for key in _TRADE_RESPONSE_KEYS - {"position"}:
            assert body[key] is not None
        assert body["position"] is not None
