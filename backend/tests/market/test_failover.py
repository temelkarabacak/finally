"""Tests for permanent Massive failover (PORT-05)."""

from __future__ import annotations

import asyncio
import logging
import os
from unittest.mock import patch

import pytest

from app.market.cache import PriceCache
from app.market.factory import create_market_data_source
from app.market.failover import FailoverMarketDataSource
from app.market.massive_client import MassiveDataSource
from app.market.simulator import SimulatorDataSource


@pytest.mark.asyncio
class TestMassivePermanentFailureGuard:
    """MassiveDataSource's own one-way trip guard."""

    async def test_first_poll_failure_trips_permanently_failed_and_invokes_callback_once(self):
        cache = PriceCache()
        calls: list[None] = []

        async def on_permanent_failure() -> None:
            calls.append(None)

        source = MassiveDataSource(
            api_key="test-key",
            price_cache=cache,
            poll_interval=60.0,
            on_permanent_failure=on_permanent_failure,
        )
        source._tickers = ["AAPL"]
        source._client = object()

        with patch.object(source, "_fetch_snapshots", side_effect=Exception("boom")):
            await source._poll_once()

        assert source.permanently_failed is True
        assert len(calls) == 1

    async def test_no_further_fetch_calls_after_trip_across_multiple_intervals(self):
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=0.0)
        source._tickers = ["AAPL"]
        source._client = object()

        call_count = 0

        def _raise():
            nonlocal call_count
            call_count += 1
            raise Exception("boom")

        with patch.object(source, "_fetch_snapshots", side_effect=_raise):
            await source._poll_once()  # trips permanent failure
            assert call_count == 1

            # Simulate several more poll cycles directly -- _poll_once is a
            # no-op once tripped, so the fetch count must not advance.
            await source._poll_once()
            await source._poll_once()
            await source._poll_once()

        assert call_count == 1

    async def test_poll_loop_terminates_after_permanent_failure(self):
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=0.0)
        source._tickers = ["AAPL"]
        source._client = object()

        with patch.object(source, "_fetch_snapshots", side_effect=Exception("boom")):
            task = asyncio.create_task(source._poll_loop())
            await asyncio.wait_for(task, timeout=1.0)

        assert source.permanently_failed is True
        assert task.done()

    async def test_exception_message_embedding_api_key_never_reaches_log(self, caplog):
        cache = PriceCache()
        source = MassiveDataSource(
            api_key="super-secret-key", price_cache=cache, poll_interval=60.0
        )
        source._tickers = ["AAPL"]
        source._client = object()

        with caplog.at_level(logging.DEBUG):
            with patch.object(
                source,
                "_fetch_snapshots",
                side_effect=Exception("auth failed for key super-secret-key"),
            ):
                await source._poll_once()

        for record in caplog.records:
            assert "super-secret-key" not in record.getMessage()


@pytest.mark.asyncio
class TestFailoverMarketDataSource:
    """The FailoverMarketDataSource wrapper's swap behavior."""

    def _make_wrapper(self, cache: PriceCache) -> FailoverMarketDataSource:
        massive = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)
        return FailoverMarketDataSource(primary=massive, price_cache=cache)

    async def test_starts_with_massive_active_and_not_failed_over(self):
        cache = PriceCache()
        wrapper = self._make_wrapper(cache)

        assert isinstance(wrapper.active, MassiveDataSource)
        assert wrapper.failed_over is False

    async def test_failure_swaps_active_to_simulator_and_transfers_tickers(self):
        cache = PriceCache()
        wrapper = self._make_wrapper(cache)
        massive = wrapper.active
        massive._tickers = ["AAPL", "GOOGL"]
        massive._client = object()

        with patch.object(massive, "_fetch_snapshots", side_effect=Exception("boom")):
            await massive._poll_once()

        assert wrapper.failed_over is True
        assert isinstance(wrapper.active, SimulatorDataSource)
        assert set(wrapper.get_tickers()) == {"AAPL", "GOOGL"}

    async def test_second_and_concurrent_failure_callback_is_a_no_op(self):
        cache = PriceCache()
        wrapper = self._make_wrapper(cache)
        massive = wrapper.active
        massive._tickers = ["AAPL"]
        massive._client = object()

        with patch.object(massive, "_fetch_snapshots", side_effect=Exception("boom")):
            await massive._poll_once()

        first_active = wrapper.active
        assert isinstance(first_active, SimulatorDataSource)

        # Direct second call.
        await wrapper._on_permanent_failure()
        assert wrapper.active is first_active

        # Concurrent calls.
        await asyncio.gather(
            wrapper._on_permanent_failure(),
            wrapper._on_permanent_failure(),
        )
        assert wrapper.active is first_active

    async def test_after_failover_add_remove_stop_route_to_simulator_not_massive(self):
        cache = PriceCache()
        wrapper = self._make_wrapper(cache)
        massive = wrapper.active
        massive._tickers = ["AAPL"]
        massive._client = object()

        with patch.object(massive, "_fetch_snapshots", side_effect=Exception("boom")):
            await massive._poll_once()

        simulator = wrapper.active
        assert isinstance(simulator, SimulatorDataSource)

        with (
            patch.object(simulator, "add_ticker", wraps=simulator.add_ticker) as sim_add,
            patch.object(massive, "add_ticker") as massive_add,
        ):
            await wrapper.add_ticker("TSLA")
            sim_add.assert_called_once_with("TSLA")
            massive_add.assert_not_called()

        with (
            patch.object(simulator, "remove_ticker", wraps=simulator.remove_ticker) as sim_remove,
            patch.object(massive, "remove_ticker") as massive_remove,
        ):
            await wrapper.remove_ticker("TSLA")
            sim_remove.assert_called_once_with("TSLA")
            massive_remove.assert_not_called()

        with (
            patch.object(simulator, "stop", wraps=simulator.stop) as sim_stop,
            patch.object(massive, "stop") as massive_stop,
        ):
            await wrapper.stop()
            sim_stop.assert_called_once()
            massive_stop.assert_not_called()

    async def test_price_cache_receives_updates_after_swap(self):
        cache = PriceCache()
        wrapper = self._make_wrapper(cache)
        massive = wrapper.active
        massive._tickers = ["AAPL"]
        massive._client = object()

        with patch.object(massive, "_fetch_snapshots", side_effect=Exception("boom")):
            await massive._poll_once()

        simulator = wrapper.active
        assert isinstance(simulator, SimulatorDataSource)
        # Simulator seeds the cache on start(); the stream never goes silent.
        assert cache.get("AAPL") is not None

        # A further step continues to push updates through the same cache.
        prices = simulator._sim.step()
        for ticker, price in prices.items():
            cache.update(ticker, price)
        assert cache.get("AAPL") is not None

    async def test_factory_created_source_fails_over_end_to_end(self):
        cache = PriceCache()
        with patch.dict(os.environ, {"MASSIVE_API_KEY": "test-key"}, clear=True):
            source = create_market_data_source(cache)

        assert isinstance(source, FailoverMarketDataSource)
        massive = source.active
        massive._tickers = ["AAPL"]
        massive._client = object()

        with patch.object(massive, "_fetch_snapshots", side_effect=Exception("boom")):
            await massive._poll_once()

        assert source.failed_over is True
        assert isinstance(source.active, SimulatorDataSource)
