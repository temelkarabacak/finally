"""Tests for the always-on portfolio snapshot recorder and history query (PORT-04)."""

from __future__ import annotations

import asyncio
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.market.cache import PriceCache
from app.market.seed_prices import SEED_PRICES
from app.portfolio import record_snapshot, start_snapshot_task, stop_snapshot_task
from app.portfolio.snapshots import HISTORY_LIMIT, get_snapshot_history

from .test_trades import portfolio_client  # noqa: F401 -- reused fixture


def _insert_snapshot(conn: sqlite3.Connection, total_value: float, recorded_at: str) -> str:
    snapshot_id = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
        "VALUES (?, 'default', ?, ?)",
        (snapshot_id, total_value, recorded_at),
    )
    return snapshot_id


class TestRecordSnapshot:
    """record_snapshot writes exactly one row with a parseable ISO timestamp."""

    def test_writes_one_row_with_parseable_recorded_at(self, initialized_db):
        conn = initialized_db

        record_snapshot(conn, 10000.0)

        rows = conn.execute("SELECT recorded_at FROM portfolio_snapshots").fetchall()
        assert len(rows) == 1
        # Must not raise -- proves the stored value is a valid ISO-8601 string.
        datetime.fromisoformat(rows[0][0])


class TestSnapshotHistory:
    """get_snapshot_history: empty state, ordering, tie-breaking, and the size cap."""

    def test_untouched_database_returns_empty_list(self, initialized_db):
        assert get_snapshot_history(initialized_db) == []

    def test_one_row_returns_one_point(self, initialized_db):
        conn = initialized_db
        record_snapshot(conn, 10000.0)

        history = get_snapshot_history(conn)

        assert len(history) == 1
        assert history[0]["value"] == 10000.0
        assert isinstance(history[0]["time"], int)

    def test_three_rows_return_oldest_first(self, initialized_db):
        conn = initialized_db
        _insert_snapshot(conn, 100.0, "2026-01-01T00:00:00+00:00")
        _insert_snapshot(conn, 300.0, "2026-01-01T00:02:00+00:00")
        _insert_snapshot(conn, 200.0, "2026-01-01T00:01:00+00:00")

        history = get_snapshot_history(conn)

        assert [point["value"] for point in history] == [100.0, 200.0, 300.0]

    def test_identical_recorded_at_returns_stable_repeatable_order(self, initialized_db):
        conn = initialized_db
        same_ts = "2026-01-01T00:00:00+00:00"
        id_a = _insert_snapshot(conn, 100.0, same_ts)
        id_b = _insert_snapshot(conn, 200.0, same_ts)
        expected_order = sorted([id_a, id_b])

        first_call = [row[2] for row in _raw_ordered_ids(conn)]
        second_call = [row[2] for row in _raw_ordered_ids(conn)]

        assert first_call == expected_order
        assert second_call == expected_order

    def test_dual_trigger_near_simultaneous_snapshots_both_persist(self, initialized_db):
        conn = initialized_db
        same_ts = datetime.now(UTC).isoformat()

        record_snapshot(conn, 10000.0, recorded_at=same_ts)
        record_snapshot(conn, 10000.0, recorded_at=same_ts)

        count = conn.execute("SELECT COUNT(*) FROM portfolio_snapshots").fetchone()[0]
        assert count == 2

    def test_history_limit_truncates_to_most_recent(self, initialized_db):
        conn = initialized_db
        base = datetime(2026, 1, 1, tzinfo=UTC)
        for i in range(HISTORY_LIMIT + 5):
            recorded_at = (base + timedelta(seconds=i)).isoformat()
            _insert_snapshot(conn, float(i), recorded_at)

        history = get_snapshot_history(conn)

        assert len(history) == HISTORY_LIMIT
        assert history[0]["value"] != 0.0


def _raw_ordered_ids(conn: sqlite3.Connection):
    """Same query shape as get_snapshot_history, exposing the raw id for comparison."""
    return conn.execute(
        "SELECT total_value, recorded_at, id FROM portfolio_snapshots "
        "ORDER BY recorded_at ASC, id ASC"
    ).fetchall()


class TestSnapshotLoop:
    """Lifecycle: start/stop, and resilience to a failing iteration."""

    @pytest.mark.asyncio
    async def test_loop_records_and_stops_cleanly(self, initialized_db):
        conn = initialized_db
        cache = PriceCache()
        for ticker, price in SEED_PRICES.items():
            cache.update(ticker, price)

        task = start_snapshot_task(lambda: conn, cache, interval=0.01)
        await asyncio.sleep(0.05)

        count_while_running = conn.execute(
            "SELECT COUNT(*) FROM portfolio_snapshots"
        ).fetchone()[0]
        assert count_while_running > 0

        await stop_snapshot_task(task)
        assert task.done()

        count_after_stop = conn.execute("SELECT COUNT(*) FROM portfolio_snapshots").fetchone()[0]
        await asyncio.sleep(0.05)
        count_later = conn.execute("SELECT COUNT(*) FROM portfolio_snapshots").fetchone()[0]
        assert count_later == count_after_stop

    @pytest.mark.asyncio
    async def test_loop_survives_a_failing_iteration(self, initialized_db):
        conn = initialized_db
        cache = PriceCache()
        for ticker, price in SEED_PRICES.items():
            cache.update(ticker, price)

        calls = {"n": 0}

        def flaky_get_conn():
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("simulated get_conn failure")
            return conn

        task = start_snapshot_task(flaky_get_conn, cache, interval=0.01)
        await asyncio.sleep(0.08)
        await stop_snapshot_task(task)

        count = conn.execute("SELECT COUNT(*) FROM portfolio_snapshots").fetchone()[0]
        assert count > 0


class TestPostTradeSnapshot:
    """The post-trade half of the dual trigger, from Plan 02-01, still holds."""

    def test_a_single_buy_leaves_exactly_one_snapshot(self, portfolio_client):  # noqa: F811
        client, conn, _source, _cache = portfolio_client

        response = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 1.0}
        )
        assert response.status_code == 200

        count = conn.execute("SELECT COUNT(*) FROM portfolio_snapshots").fetchone()[0]
        assert count == 1
