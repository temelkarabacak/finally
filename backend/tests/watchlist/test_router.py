"""Tests for the watchlist router (WATCH-01/02/03)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.market.cache import PriceCache
from app.watchlist import create_watchlist_router


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


_WATCHLIST_ENTRY_KEYS = {
    "ticker",
    "price",
    "previous_price",
    "change",
    "change_percent",
    "direction",
}


def _insert_position(conn, ticker: str, quantity: float = 1.0) -> None:
    conn.execute(
        "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
        "VALUES (?, 'default', ?, ?, 100.0, ?)",
        (uuid.uuid4().hex, ticker, quantity, datetime.now(UTC).isoformat()),
    )


@pytest.fixture
def watchlist_client(initialized_db):
    """TestClient wired to a real temp-DB connection, a fake source, and a fresh cache."""
    conn = initialized_db
    source = FakeMarketSource()
    cache = PriceCache()

    app = FastAPI()
    app.include_router(create_watchlist_router(lambda: conn, source, cache))

    with TestClient(app) as client:
        yield client, conn, source, cache


class TestWatchlistRouter:
    """WATCH-01/02/03: watchlist CRUD end to end."""

    def test_post_adds_ticker_normalized_and_to_source(self, watchlist_client):
        client, conn, source, _cache = watchlist_client

        response = client.post("/api/watchlist", json={"ticker": "pypl"})

        assert response.status_code == 201
        body = response.json()
        assert set(body.keys()) == _WATCHLIST_ENTRY_KEYS
        assert body["ticker"] == "PYPL"
        row = conn.execute("SELECT ticker FROM watchlist WHERE ticker = 'PYPL'").fetchone()
        assert row is not None
        assert "PYPL" in source.get_tickers()

    def test_post_duplicate_ticker_returns_409_and_keeps_one_row(self, watchlist_client):
        client, conn, _source, _cache = watchlist_client

        first = client.post("/api/watchlist", json={"ticker": "PYPL"})
        assert first.status_code == 201

        second = client.post("/api/watchlist", json={"ticker": "PYPL"})
        assert second.status_code == 409
        assert isinstance(second.json()["detail"], str)
        assert second.json()["detail"]

        count = conn.execute("SELECT COUNT(*) FROM watchlist WHERE ticker = 'PYPL'").fetchone()[
            0
        ]
        assert count == 1

    def test_post_empty_ticker_returns_422_no_row_no_source_call(self, watchlist_client):
        client, conn, source, _cache = watchlist_client

        response = client.post("/api/watchlist", json={"ticker": "   "})

        assert response.status_code == 422
        count = conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]
        assert count == 10  # unchanged from seed
        assert source.add_calls == []

    def test_post_ticker_with_invalid_characters_returns_422(self, watchlist_client):
        client, conn, source, _cache = watchlist_client

        response = client.post("/api/watchlist", json={"ticker": "PY$PL"})

        assert response.status_code == 422
        count = conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]
        assert count == 10  # unchanged from seed
        assert source.add_calls == []

    def test_post_normalizes_before_duplicate_check(self, watchlist_client):
        client, _conn, _source, _cache = watchlist_client

        # AAPL is already in the default seeded watchlist.
        response = client.post("/api/watchlist", json={"ticker": "  aapl  "})

        assert response.status_code == 409

    def test_delete_with_no_open_position_removes_from_everything(self, watchlist_client):
        client, conn, source, cache = watchlist_client
        cache.update("AAPL", 190.0)
        source._tickers = ["AAPL"]

        response = client.delete("/api/watchlist/AAPL")

        assert response.status_code == 204
        assert response.content == b""
        row = conn.execute("SELECT 1 FROM watchlist WHERE ticker = 'AAPL'").fetchone()
        assert row is None
        assert "AAPL" not in source.get_tickers()
        assert source.remove_calls == ["AAPL"]

    def test_delete_with_open_position_keeps_streaming(self, watchlist_client):
        client, conn, source, cache = watchlist_client
        _insert_position(conn, "AAPL", quantity=5.0)
        cache.update("AAPL", 190.0)
        source._tickers = ["AAPL"]

        response = client.delete("/api/watchlist/AAPL")

        assert response.status_code == 204
        row = conn.execute("SELECT 1 FROM watchlist WHERE ticker = 'AAPL'").fetchone()
        assert row is None
        assert "AAPL" in source.get_tickers()
        assert cache.get("AAPL") is not None
        assert source.remove_calls == []

    def test_delete_unknown_ticker_returns_404_no_source_call(self, watchlist_client):
        client, _conn, source, _cache = watchlist_client

        response = client.delete("/api/watchlist/ZZZZ")

        assert response.status_code == 404
        assert source.remove_calls == []

    def test_delete_twice_returns_204_then_404_source_called_once(self, watchlist_client):
        client, _conn, source, cache = watchlist_client
        cache.update("AAPL", 190.0)
        source._tickers = ["AAPL"]

        first = client.delete("/api/watchlist/AAPL")
        second = client.delete("/api/watchlist/AAPL")

        assert first.status_code == 204
        assert second.status_code == 404
        assert source.remove_calls == ["AAPL"]

    def test_get_returns_one_entry_per_row_with_null_price_for_unseen_ticker(
        self, watchlist_client
    ):
        client, _conn, _source, _cache = watchlist_client

        response = client.get("/api/watchlist")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 10  # seeded default watchlist
        aapl_entry = next(entry for entry in data if entry["ticker"] == "AAPL")
        assert set(aapl_entry.keys()) == _WATCHLIST_ENTRY_KEYS
        assert aapl_entry["price"] is None
        assert aapl_entry["previous_price"] is None
        assert aapl_entry["change"] is None
        assert aapl_entry["change_percent"] is None
        assert aapl_entry["direction"] is None
