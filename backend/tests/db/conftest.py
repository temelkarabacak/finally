"""Fixtures for database tests. Every test gets its own temporary SQLite file."""

import pytest

from app.db import get_connection


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def conn(db_path):
    connection = get_connection(db_path)
    yield connection
    connection.close()
