"""Fixtures for backend/tests/llm/: chat_client wiring and the network-block guard."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.llm import create_chat_router
from app.market.cache import PriceCache
from app.market.seed_prices import SEED_PRICES
from tests.portfolio.test_trades import FakeMarketSource


@pytest.fixture
def chat_client(initialized_db, monkeypatch):
    """TestClient wired to a real temp-DB connection, a fake source, seeded
    cache, and LLM_MOCK forced on so no test ever reaches the network."""
    monkeypatch.setenv("LLM_MOCK", "true")
    conn = initialized_db
    source = FakeMarketSource()
    cache = PriceCache()
    for ticker, price in SEED_PRICES.items():
        cache.update(ticker, price)

    app = FastAPI()
    app.include_router(create_chat_router(lambda: conn, source, cache, mock=True))

    with TestClient(app) as client:
        yield client, conn, source, cache


@pytest.fixture(autouse=True)
def block_real_llm_calls(monkeypatch):
    """CI hermeticity guard: if mock mode ever regresses and a test path
    reaches litellm.completion, fail loudly instead of needing a real API key."""

    def _raise(*args, **kwargs):
        raise RuntimeError("litellm.completion() called in a test — mock mode regression")

    monkeypatch.setattr("litellm.completion", _raise)
