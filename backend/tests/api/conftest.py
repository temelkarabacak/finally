"""Fixtures for API tests: a temp database, seeded prices and a fake data source."""

import pytest
from fastapi.testclient import TestClient

from app.db import get_connection, get_db
from app.main import create_app
from app.market import MarketDataSource, PriceCache

SEED_PRICES = {"AAPL": 100.0, "GOOGL": 200.0, "MSFT": 400.0}


class FakeMarketDataSource(MarketDataSource):
    """Records add/remove calls instead of producing prices."""

    def __init__(self, tickers: list[str] | None = None) -> None:
        self._tickers = list(tickers or [])
        self.started = False

    async def start(self, tickers: list[str]) -> None:
        self._tickers = list(tickers)
        self.started = True

    async def stop(self) -> None:
        self.started = False

    async def add_ticker(self, ticker: str) -> None:
        if ticker not in self._tickers:
            self._tickers.append(ticker)

    async def remove_ticker(self, ticker: str) -> None:
        if ticker in self._tickers:
            self._tickers.remove(ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def conn(db_path):
    """The single connection the app uses for every request in a test."""
    connection = get_connection(db_path)
    yield connection
    connection.close()


@pytest.fixture
def cache():
    price_cache = PriceCache()
    for ticker, price in SEED_PRICES.items():
        price_cache.update(ticker, price)
    return price_cache


@pytest.fixture
def source(cache):
    return FakeMarketDataSource(sorted(cache.get_all()))


@pytest.fixture
def client(conn, cache, source):
    """TestClient with the lifespan skipped, so no real simulator runs.

    The request transaction is emulated by committing after each handler.
    """
    app = create_app(price_cache=cache)
    app.state.market_source = source

    def override_get_db():
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)
