"""Fixtures for LLM chat tests: a temp database, a seeded price cache and a test app."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_connection, get_db
from app.dependencies import get_market_source, get_price_cache
from app.llm import router as chat_router
from app.market import MarketDataSource, PriceCache

SEED_PRICES = {"AAPL": 190.0, "GOOGL": 175.0, "MSFT": 420.0, "TSLA": 250.0}


class FakeSource(MarketDataSource):
    """Records ticker lifecycle calls without running a price loop."""

    def __init__(self, tickers):
        self.tickers = list(tickers)
        self.added: list[str] = []
        self.removed: list[str] = []

    async def start(self, tickers):
        self.tickers = list(tickers)

    async def stop(self):
        pass

    async def add_ticker(self, ticker):
        self.added.append(ticker)
        self.tickers.append(ticker)

    async def remove_ticker(self, ticker):
        self.removed.append(ticker)
        self.tickers.remove(ticker)

    def get_tickers(self):
        return list(self.tickers)


@pytest.fixture
def conn(tmp_path):
    connection = get_connection(str(tmp_path / "test.db"))
    yield connection
    connection.close()


@pytest.fixture
def price_cache():
    cache = PriceCache()
    for ticker, price in SEED_PRICES.items():
        cache.update(ticker, price)
    return cache


@pytest.fixture
def source(price_cache):
    return FakeSource(SEED_PRICES)


@pytest.fixture
def app(conn, price_cache, source):
    """App mounting only the chat router, with the shared singletons stubbed out."""
    application = FastAPI()
    application.include_router(chat_router)
    application.dependency_overrides[get_db] = lambda: conn
    application.dependency_overrides[get_price_cache] = lambda: price_cache
    application.dependency_overrides[get_market_source] = lambda: source
    return application


@pytest.fixture
def client(app, monkeypatch):
    """TestClient in mock LLM mode."""
    monkeypatch.setenv("LLM_MOCK", "true")
    with TestClient(app) as test_client:
        yield test_client
