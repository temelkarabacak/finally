"""Tests for GET /api/health (FOUND-01)."""

from __future__ import annotations


class TestHealth:
    """FOUND-01: health check is a truthful, read-only liveness probe."""

    def test_returns_200_and_reports_simulator_under_empty_environment(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["market_source"] == "simulator"

    def test_ten_sequential_calls_all_succeed_and_leave_watchlist_unchanged(self, client):
        watchlist_before = client.get("/api/watchlist").json()

        for _ in range(10):
            response = client.get("/api/health")
            assert response.status_code == 200
            body = response.json()
            assert body["status"] == "ok"
            assert body["market_source"] == "simulator"

        watchlist_after = client.get("/api/watchlist").json()
        assert len(watchlist_after) == len(watchlist_before)
