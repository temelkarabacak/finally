"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.db.connection as db_connection
from app.db import init_db
from app.market.cache import PriceCache
from app.market.seed_prices import SEED_PRICES


@pytest.fixture
def tmp_db_path(tmp_path, monkeypatch):
    """Point FINALLY_DB_PATH at a fresh temp file so tests never touch the
    developer's real db/finally.db."""
    path = tmp_path / "finally.db"
    monkeypatch.setenv("FINALLY_DB_PATH", str(path))
    yield path


@pytest.fixture
def initialized_db(tmp_db_path):
    """init_db() against the temp path; yields the resulting connection.

    Resets the module-level connection singleton before and after so tests
    do not leak state into each other.
    """
    db_connection._connection = None
    init_db()
    conn = db_connection.get_db()
    yield conn
    conn.close()
    db_connection._connection = None


@pytest.fixture
def seeded_cache():
    """A PriceCache pre-populated with the ten SEED_PRICES entries."""
    cache = PriceCache()
    for ticker, price in SEED_PRICES.items():
        cache.update(ticker, price)
    return cache


@pytest.fixture
def client(tmp_db_path):
    """A TestClient used as a context manager so `lifespan` actually runs.

    A bare TestClient(app) without the `with` block skips startup entirely,
    which would let every wiring assertion silently pass without exercising
    anything.
    """
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
