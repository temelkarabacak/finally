"""Tests for portfolio trade execution (PORT-01/02/03/04)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.market.cache import PriceCache
from app.market.seed_prices import SEED_PRICES
from app.portfolio import create_portfolio_router


class FakeMarketSource:
    """Records add_ticker/remove_ticker calls instead of running a real simulator."""

    def __init__(self, tickers: list[str] | None = None) -> None:
        self._tickers = list(tickers or [])
        self.add_calls: list[str] = []
        self.remove_calls: list[str] = []

    async def start(self, tickers: list[str]) -> None:
        self._tickers = list(tickers)

    async def stop(self) -> None:
        pass

    async def add_ticker(self, ticker: str) -> None:
        self.add_calls.append(ticker)
        if ticker not in self._tickers:
            self._tickers.append(ticker)

    async def remove_ticker(self, ticker: str) -> None:
        self.remove_calls.append(ticker)
        self._tickers = [t for t in self._tickers if t != ticker]

    def get_tickers(self) -> list[str]:
        return list(self._tickers)


def _insert_position(conn, ticker: str, quantity: float, avg_cost: float) -> None:
    conn.execute(
        "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
        "VALUES (?, 'default', ?, ?, ?, ?)",
        (uuid.uuid4().hex, ticker, quantity, avg_cost, datetime.now(UTC).isoformat()),
    )


@pytest.fixture
def portfolio_client(initialized_db):
    """TestClient wired to a real temp-DB connection, a fake source, and a seeded cache."""
    conn = initialized_db
    source = FakeMarketSource()
    cache = PriceCache()
    for ticker, price in SEED_PRICES.items():
        cache.update(ticker, price)

    app = FastAPI()
    app.include_router(create_portfolio_router(lambda: conn, source, cache))

    with TestClient(app) as client:
        yield client, conn, source, cache


class TestTradeHappyPath:
    """PORT-01/02/04: buy fills, persists, and revalues; a matching sell closes it out."""

    def test_buy_fills_persists_and_tracks_ticker(self, portfolio_client):
        client, conn, source, _cache = portfolio_client
        aapl_price = SEED_PRICES["AAPL"]

        cash_before = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id = 'default'"
        ).fetchone()[0]

        response = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 1.5}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["ticker"] == "AAPL"
        assert body["quantity"] == 1.5
        assert body["price"] == aapl_price

        cash_after = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id = 'default'"
        ).fetchone()[0]
        assert cash_after == pytest.approx(cash_before - 1.5 * aapl_price)

        position = conn.execute(
            "SELECT quantity FROM positions WHERE user_id = 'default' AND ticker = 'AAPL'"
        ).fetchone()
        assert position is not None
        assert position[0] == 1.5

        trades_count = conn.execute(
            "SELECT COUNT(*) FROM trades WHERE ticker = 'AAPL'"
        ).fetchone()[0]
        assert trades_count == 1

        snapshots_count = conn.execute("SELECT COUNT(*) FROM portfolio_snapshots").fetchone()[0]
        assert snapshots_count == 1

        assert "AAPL" in source.add_calls

    def test_get_portfolio_reports_position_with_live_price(self, portfolio_client):
        client, _conn, _source, _cache = portfolio_client
        aapl_price = SEED_PRICES["AAPL"]

        client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 1.5}
        )
        response = client.get("/api/portfolio")

        assert response.status_code == 200
        body = response.json()
        aapl = next(p for p in body["positions"] if p["ticker"] == "AAPL")
        assert aapl["current_price"] == aapl_price
        assert body["total_value"] == pytest.approx(
            body["cash_balance"] + aapl["market_value"]
        )

    def test_selling_full_position_empties_it_and_restores_cash(self, portfolio_client):
        client, _conn, _source, _cache = portfolio_client

        client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 1.5}
        )
        original_cash = client.get("/api/portfolio").json()["cash_balance"]

        response = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "side": "sell", "quantity": 1.5}
        )
        assert response.status_code == 200

        portfolio = client.get("/api/portfolio").json()
        assert portfolio["positions"] == []
        assert portfolio["cash_balance"] == pytest.approx(10000.0)
        assert portfolio["cash_balance"] != original_cash
