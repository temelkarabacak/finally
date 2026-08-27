"""Tests for portfolio P&L arithmetic (TEST-01, PORT-01)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.market.cache import PriceCache
from app.portfolio.valuation import (
    POSITION_EPSILON,
    compute_total_value,
    portfolio_view,
    position_views,
)


def _insert_position(conn, ticker: str, quantity: float, avg_cost: float) -> None:
    conn.execute(
        "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
        "VALUES (?, 'default', ?, ?, ?, ?)",
        (uuid.uuid4().hex, ticker, quantity, avg_cost, datetime.now(UTC).isoformat()),
    )


class TestComputeTotalValue:
    def test_no_positions_equals_cash_balance_exactly(self, initialized_db):
        conn = initialized_db
        cache = PriceCache()

        cash = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id = 'default'"
        ).fetchone()[0]

        assert compute_total_value(conn, cache) == cash


class TestPositionViews:
    def test_profitable_position_reports_exact_pnl_and_percent(self, initialized_db):
        conn = initialized_db
        cache = PriceCache()
        cache.update("AAPL", 150.0)
        _insert_position(conn, "AAPL", 2.0, 100.0)

        views = position_views(conn, cache)

        assert len(views) == 1
        view = views[0]
        assert view["market_value"] == 300.00
        assert view["unrealized_pnl"] == 100.00
        assert view["unrealized_pnl_percent"] == 50.00

    def test_losing_position_reports_exact_negative_pnl_and_percent(self, initialized_db):
        conn = initialized_db
        cache = PriceCache()
        cache.update("AAPL", 50.0)
        _insert_position(conn, "AAPL", 2.0, 100.0)

        views = position_views(conn, cache)

        view = views[0]
        assert view["unrealized_pnl"] == -100.00
        assert view["unrealized_pnl_percent"] == -50.00

    def test_position_with_no_cached_price_values_at_avg_cost_and_reports_zero_pnl(
        self, initialized_db
    ):
        conn = initialized_db
        cache = PriceCache()  # AAPL never updated -- no cache entry
        _insert_position(conn, "AAPL", 2.0, 100.0)

        views = position_views(conn, cache)

        view = views[0]
        assert view["current_price"] is None
        assert view["market_value"] == 200.00  # 2 * avg_cost
        assert view["unrealized_pnl"] == 0.00
        assert view["unrealized_pnl_percent"] == 0.00

    def test_position_at_or_below_epsilon_is_excluded(self, initialized_db):
        conn = initialized_db
        cache = PriceCache()
        cache.update("AAPL", 150.0)
        _insert_position(conn, "AAPL", POSITION_EPSILON, 100.0)

        views = position_views(conn, cache)

        assert views == []


class TestPortfolioView:
    def test_total_value_equals_cash_plus_holdings_value(self, initialized_db):
        conn = initialized_db
        cache = PriceCache()
        cache.update("AAPL", 150.0)
        cache.update("GOOGL", 200.0)
        _insert_position(conn, "AAPL", 2.0, 100.0)
        _insert_position(conn, "GOOGL", 1.0, 180.0)

        view = portfolio_view(conn, cache)

        expected_holdings = sum(p["market_value"] for p in view["positions"])
        assert view["holdings_value"] == expected_holdings
        assert view["total_value"] == view["cash_balance"] + view["holdings_value"]

    def test_epsilon_position_contributes_nothing_to_holdings_value(self, initialized_db):
        conn = initialized_db
        cache = PriceCache()
        cache.update("AAPL", 150.0)
        _insert_position(conn, "AAPL", POSITION_EPSILON, 100.0)

        view = portfolio_view(conn, cache)

        assert view["holdings_value"] == 0.0
        assert view["positions"] == []
