"""Tests for lifespan startup wiring (FOUND-04)."""

from __future__ import annotations

import app.db.connection as db_connection
from app.db import DEFAULT_WATCHLIST
from app.main import app as main_app
from app.market.simulator import SimulatorDataSource


class TestAppStartup:
    """FOUND-04: the market source starts during lifespan with watchlist UNION positions."""

    def test_source_starts_with_seeded_watchlist(self, client):
        tickers = sorted(main_app.state.source.get_tickers())
        assert tickers == sorted(DEFAULT_WATCHLIST)

    def test_state_cache_is_the_module_scope_cache(self, client):
        import app.main as main

        assert main_app.state.cache is main.cache

    def test_simulator_selected_under_empty_environment(self, client):
        assert isinstance(main_app.state.source, SimulatorDataSource)

    def test_empty_watchlist_still_starts_with_zero_tickers(self, tmp_db_path):
        from app.db import init_db

        db_connection._connection = None
        init_db()
        conn = db_connection.get_db()
        conn.execute("DELETE FROM watchlist")
        conn.close()
        db_connection._connection = None

        from fastapi.testclient import TestClient

        with TestClient(main_app) as test_client:
            response = test_client.get("/api/health")
            assert response.status_code == 200
            assert main_app.state.source.get_tickers() == []
