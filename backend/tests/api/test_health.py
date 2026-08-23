"""Tests for GET /api/health (FOUND-01)."""

from __future__ import annotations


class TestHealth:
    """FOUND-01: health check is a truthful, read-only liveness probe."""

    def test_returns_200_and_exact_body(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_ten_sequential_calls_all_succeed_and_leave_watchlist_unchanged(self, client):
        watchlist_before = client.get("/api/watchlist").json()

        for _ in range(10):
            response = client.get("/api/health")
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}

        watchlist_after = client.get("/api/watchlist").json()
        assert len(watchlist_after) == len(watchlist_before)
