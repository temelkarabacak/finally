"""Tests for the SSE streaming endpoint (stream.py)."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from app.market.cache import PriceCache
from app.market.stream import _generate_events, create_stream_router


class FakeRequest:
    """Minimal stand-in for fastapi.Request, driving is_disconnected() by call count."""

    def __init__(self, disconnect_after: int | None = None) -> None:
        self._calls = 0
        self._disconnect_after = disconnect_after
        self.client = SimpleNamespace(host="127.0.0.1")

    async def is_disconnected(self) -> bool:
        self._calls += 1
        if self._disconnect_after is not None and self._calls > self._disconnect_after:
            return True
        return False


def _parse_data_frame(frame: str) -> dict:
    assert frame.startswith("data: ")
    return json.loads(frame[len("data: ") :].strip())


@pytest.mark.asyncio
class TestGenerateEvents:
    """Unit tests for _generate_events, the SSE async generator."""

    async def test_retry_frame_sent_first(self):
        cache = PriceCache()
        request = FakeRequest(disconnect_after=0)
        gen = _generate_events(cache, request, interval=0.01)

        first = await gen.__anext__()
        assert first == "retry: 1000\n\n"

    async def test_empty_cache_produces_no_data_frame(self):
        cache = PriceCache()
        request = FakeRequest(disconnect_after=1)

        events = [event async for event in _generate_events(cache, request, interval=0.01)]

        assert events == ["retry: 1000\n\n"]

    async def test_data_frame_emitted_once_when_version_unchanged(self):
        cache = PriceCache()
        cache.update("AAPL", 190.0)
        request = FakeRequest(disconnect_after=3)

        events = [event async for event in _generate_events(cache, request, interval=0.01)]

        data_events = [e for e in events if e.startswith("data:")]
        assert len(data_events) == 1
        payload = _parse_data_frame(data_events[0])
        assert payload["AAPL"]["price"] == 190.0

    async def test_data_frame_emitted_again_on_new_version(self):
        cache = PriceCache()
        cache.update("AAPL", 190.0)
        request = FakeRequest(disconnect_after=5)
        gen = _generate_events(cache, request, interval=0)

        assert await gen.__anext__() == "retry: 1000\n\n"

        first_data = await gen.__anext__()
        assert _parse_data_frame(first_data)["AAPL"]["price"] == 190.0

        cache.update("AAPL", 191.0)
        second_data = await gen.__anext__()
        assert _parse_data_frame(second_data)["AAPL"]["price"] == 191.0

    async def test_stops_on_disconnect(self):
        cache = PriceCache()
        cache.update("AAPL", 190.0)
        request = FakeRequest(disconnect_after=1)

        events = [event async for event in _generate_events(cache, request, interval=0.01)]

        # Generator must terminate on its own (list comprehension completes)
        # rather than looping forever.
        assert len(events) >= 1

    async def test_cancellation_is_handled_cleanly(self):
        """The generator catches CancelledError internally (to log a clean
        disconnect) rather than letting it propagate, so a cancelled consumer
        task completes normally instead of raising."""
        cache = PriceCache()
        request = FakeRequest(disconnect_after=None)
        gen = _generate_events(cache, request, interval=10)

        async def consume():
            async for _ in gen:
                pass

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.05)  # let it enter the sleep between ticks
        task.cancel()

        await asyncio.wait_for(task, timeout=1.0)
        assert not task.cancelled()


class TestCreateStreamRouter:
    """Regression tests for the router-per-call factory fix (was a module-level singleton)."""

    def test_returns_a_fresh_router_each_call(self):
        cache = PriceCache()
        router1 = create_stream_router(cache)
        router2 = create_stream_router(cache)

        assert router1 is not router2
        assert len(router1.routes) == 1
        assert len(router2.routes) == 1
