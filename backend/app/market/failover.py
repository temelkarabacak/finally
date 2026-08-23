"""Permanent failover wrapper: swaps a failing MassiveDataSource for the simulator."""

from __future__ import annotations

import asyncio
import logging

from .cache import PriceCache
from .interface import MarketDataSource
from .massive_client import MassiveDataSource
from .simulator import SimulatorDataSource

logger = logging.getLogger(__name__)


class FailoverMarketDataSource(MarketDataSource):
    """Wraps a MassiveDataSource and transparently swaps to the simulator
    the first time it permanently fails.

    Keeps massive_client.py and simulator.py mutually unaware of each other:
    this module is the only place that imports both, preserving the existing
    one-directional import graph (factory -> simulator/massive_client; both
    -> interface/cache/models).

    The swap is a one-way trip and is idempotent: a doubled or concurrent
    permanent-failure callback starts no second simulator and leaves
    `.active` unchanged after the first swap completes.
    """

    def __init__(self, primary: MassiveDataSource, price_cache: PriceCache) -> None:
        self._active: MarketDataSource = primary
        self._cache = price_cache
        self._failed_over = False
        self._lock = asyncio.Lock()
        primary._on_permanent_failure = self._on_permanent_failure

    @property
    def active(self) -> MarketDataSource:
        """The currently serving source: the Massive primary, or the simulator
        once failover has occurred."""
        return self._active

    @property
    def failed_over(self) -> bool:
        """Whether the permanent swap to the simulator has occurred."""
        return self._failed_over

    async def start(self, tickers: list[str]) -> None:
        await self._active.start(tickers)

    async def stop(self) -> None:
        await self._active.stop()

    async def add_ticker(self, ticker: str) -> None:
        await self._active.add_ticker(ticker)

    async def remove_ticker(self, ticker: str) -> None:
        await self._active.remove_ticker(ticker)

    def get_tickers(self) -> list[str]:
        return self._active.get_tickers()

    async def _on_permanent_failure(self) -> None:
        """Swap the active source to a freshly seeded simulator, exactly once.

        The simulator seeds the transferred tickers from its own
        SEED_PRICES/DEFAULT_PARAMS, so the ticker set carries over but the
        price level does not — a visible price jump at the moment of
        failover is the defined contract, not a defect.
        """
        async with self._lock:
            if self._failed_over:
                return
            self._failed_over = True

            tickers = self._active.get_tickers()
            await self._active.stop()

            simulator = SimulatorDataSource(self._cache)
            await simulator.start(tickers)
            self._active = simulator

            logger.error(
                "Massive data source permanently failed over to the simulator "
                "with %d tickers transferred; prices restart from simulator seed "
                "values, this is a defined discontinuity, not a defect",
                len(tickers),
            )
