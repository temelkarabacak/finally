"""Tests for portfolio trade execution (PORT-01/02/03/04)."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_active_tickers
from app.market.cache import PriceCache
from app.market.seed_prices import SEED_PRICES
from app.portfolio import TradeError, create_portfolio_router, execute_trade
from app.portfolio.trades import new_position_after_buy


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


class _RaisingOnTradesInsertProxy:
    """Delegates to a real sqlite3.Connection except execute(), which raises
    sqlite3.OperationalError on the statement that writes the trades row.

    sqlite3.Connection.execute cannot be monkeypatched (read-only on the
    instance, immutable on the C-level type), so this proxy stands in for
    the connection object passed to execute_trade instead.
    """

    def __init__(self, real_conn: sqlite3.Connection) -> None:
        self._real = real_conn

    def execute(self, sql, *args, **kwargs):
        if isinstance(sql, str) and sql.strip().startswith("INSERT INTO trades"):
            raise sqlite3.OperationalError("simulated failure")
        return self._real.execute(sql, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._real, name)


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


class TestPositionMath:
    """Weighted-average-cost formula, unit-level, no DB involved."""

    def test_first_ever_buy_sets_basis_to_purchase_price(self):
        assert new_position_after_buy(0.0, 0.0, 3.0, 50.0) == (3.0, 50.0)

    def test_second_buy_computes_weighted_average(self):
        assert new_position_after_buy(2.0, 100.0, 2.0, 200.0) == (4.0, 150.0)


class TestTradeValidation:
    """PORT-03: every rejection leaves positions/trades/cash_balance untouched."""

    def test_buy_over_budget_rejected_with_no_side_effects(self, portfolio_client):
        _client, conn, _source, cache = portfolio_client
        cash_before = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id = 'default'"
        ).fetchone()[0]

        with pytest.raises(TradeError) as exc_info:
            execute_trade(conn, cache, "AAPL", "buy", 100000)
        assert exc_info.value.code == "insufficient_cash"

        cash_after = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id = 'default'"
        ).fetchone()[0]
        assert cash_after == cash_before
        assert conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0
        assert (
            conn.execute("SELECT quantity FROM positions WHERE ticker = 'AAPL'").fetchone()
            is None
        )

    def test_buy_over_budget_returns_400_via_http(self, portfolio_client):
        client, _conn, _source, _cache = portfolio_client

        response = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 100000}
        )

        assert response.status_code == 400

    def test_sell_over_held_rejected_with_no_side_effects(self, portfolio_client):
        _client, conn, _source, cache = portfolio_client
        _insert_position(conn, "AAPL", 1.0, 100.0)
        cash_before = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id = 'default'"
        ).fetchone()[0]

        with pytest.raises(TradeError) as exc_info:
            execute_trade(conn, cache, "AAPL", "sell", 5.0)
        assert exc_info.value.code == "insufficient_shares"

        cash_after = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id = 'default'"
        ).fetchone()[0]
        assert cash_after == cash_before
        qty = conn.execute("SELECT quantity FROM positions WHERE ticker = 'AAPL'").fetchone()[0]
        assert qty == 1.0

    def test_sell_over_held_returns_400_via_http(self, portfolio_client):
        client, conn, _source, _cache = portfolio_client
        _insert_position(conn, "AAPL", 1.0, 100.0)

        response = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "side": "sell", "quantity": 5.0}
        )

        assert response.status_code == 400

    def test_no_cached_price_rejected(self, portfolio_client):
        _client, conn, _source, cache = portfolio_client

        with pytest.raises(TradeError) as exc_info:
            execute_trade(conn, cache, "ZZZZ", "buy", 1.0)
        assert exc_info.value.code == "no_price"

    def test_no_cached_price_returns_400_via_http(self, portfolio_client):
        client, _conn, _source, _cache = portfolio_client

        response = client.post(
            "/api/portfolio/trade", json={"ticker": "ZZZZ", "side": "buy", "quantity": 1.0}
        )

        assert response.status_code == 400


class TestTradeTransaction:
    """Transaction integrity: rollback, epsilon tolerance, and sequential trades."""

    def test_reopening_a_closed_position_resets_avg_cost(self, portfolio_client):
        _client, conn, _source, cache = portfolio_client
        cache.update("PYPL", 50.0)

        execute_trade(conn, cache, "PYPL", "buy", 2.0)
        execute_trade(conn, cache, "PYPL", "sell", 2.0)

        cache.update("PYPL", 60.0)
        execute_trade(conn, cache, "PYPL", "buy", 1.0)

        avg_cost = conn.execute(
            "SELECT avg_cost FROM positions WHERE ticker = 'PYPL'"
        ).fetchone()[0]
        assert avg_cost == pytest.approx(60.0)

    def test_sell_does_not_change_avg_cost(self, portfolio_client):
        _client, conn, _source, cache = portfolio_client
        execute_trade(conn, cache, "AAPL", "buy", 2.0)
        avg_cost_before = conn.execute(
            "SELECT avg_cost FROM positions WHERE ticker = 'AAPL'"
        ).fetchone()[0]

        execute_trade(conn, cache, "AAPL", "sell", 1.0)
        avg_cost_after = conn.execute(
            "SELECT avg_cost FROM positions WHERE ticker = 'AAPL'"
        ).fetchone()[0]

        assert avg_cost_after == avg_cost_before

    def test_epsilon_tolerant_full_close(self, portfolio_client):
        _client, conn, _source, cache = portfolio_client
        execute_trade(conn, cache, "AAPL", "buy", 1.1)
        execute_trade(conn, cache, "AAPL", "sell", 1.1)

        qty = conn.execute("SELECT quantity FROM positions WHERE ticker = 'AAPL'").fetchone()[0]
        assert qty == 0.0

    def test_full_close_leaves_active_tickers_unless_watchlisted(self, portfolio_client):
        _client, conn, _source, cache = portfolio_client
        cache.update("PYPL", 50.0)

        execute_trade(conn, cache, "PYPL", "buy", 2.0)
        assert "PYPL" in get_active_tickers(conn)

        execute_trade(conn, cache, "PYPL", "sell", 2.0)
        assert "PYPL" not in get_active_tickers(conn)

    def test_rollback_on_mid_transaction_failure_leaves_db_untouched(self, portfolio_client):
        _client, conn, _source, cache = portfolio_client
        cash_before = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id = 'default'"
        ).fetchone()[0]

        # sqlite3.Connection.execute is a read-only attribute on the C-level
        # type (cannot be monkeypatched on the instance or the class), so
        # wrap the real connection in a thin proxy that raises on the
        # statement that writes trades and delegates everything else --
        # execute_trade only needs .execute(), so this is a drop-in swap.
        proxy_conn = _RaisingOnTradesInsertProxy(conn)

        with pytest.raises(sqlite3.OperationalError):
            execute_trade(proxy_conn, cache, "AAPL", "buy", 1.0)

        cash_after = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id = 'default'"
        ).fetchone()[0]
        assert cash_after == cash_before
        assert (
            conn.execute("SELECT quantity FROM positions WHERE ticker = 'AAPL'").fetchone()
            is None
        )

    def test_two_sequential_buys_validate_against_reduced_balance(self, portfolio_client):
        _client, conn, _source, cache = portfolio_client
        aapl_price = SEED_PRICES["AAPL"]

        execute_trade(conn, cache, "AAPL", "buy", 3.0)
        cash_after_first = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id = 'default'"
        ).fetchone()[0]

        execute_trade(conn, cache, "AAPL", "buy", 3.0)
        cash_after_second = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id = 'default'"
        ).fetchone()[0]

        assert cash_after_first == pytest.approx(10000.0 - 3 * aapl_price)
        assert cash_after_second == pytest.approx(cash_after_first - 3 * aapl_price)
        qty = conn.execute("SELECT quantity FROM positions WHERE ticker = 'AAPL'").fetchone()[0]
        assert qty == 6.0

    def test_every_successful_trade_appends_exactly_one_snapshot(self, portfolio_client):
        _client, conn, _source, cache = portfolio_client

        execute_trade(conn, cache, "AAPL", "buy", 1.0)
        assert conn.execute("SELECT COUNT(*) FROM portfolio_snapshots").fetchone()[0] == 1

        execute_trade(conn, cache, "AAPL", "sell", 1.0)
        assert conn.execute("SELECT COUNT(*) FROM portfolio_snapshots").fetchone()[0] == 2
