# Market Data Backend — Detailed Design

Implementation-ready design for FinAlly's market data subsystem: the unified source interface,
the thread-safe price cache, the GBM simulator, the Massive (Polygon.io) REST client, the SSE
streaming endpoint, and the FastAPI integration layer that wires it all into the app.

**Status of this document**: `backend/app/market/` (the interface, cache, simulator, Massive
client, factory, and SSE endpoint) is built and tested — 73 tests passing, see
`MARKET_DATA_SUMMARY.md`. Every code block in §1–§9 below is the actual, current source, not a
proposal. §10–§12 (FastAPI lifespan wiring, permanent Massive failover, watchlist coordination)
describe integration points that belong to `backend/app/main.py` and the watchlist API, neither
of which exists yet — those sections are the design for the next phase of backend work and are
marked accordingly.

Related docs: `MARKET_INTERFACE.md`, `MARKET_SIMULATOR.md`, `MASSIVE_API.md` (research/rationale
this design draws from), `planning/archive/MARKET_DATA_DESIGN.md` (an earlier draft of this
document, superseded by this one), `MARKET_DATA_SUMMARY.md` (test/coverage summary).

---

## Table of Contents

1. [Architecture](#1-architecture)
2. [File Structure](#2-file-structure)
3. [Data Model — `models.py`](#3-data-model)
4. [Price Cache — `cache.py`](#4-price-cache)
5. [Abstract Interface — `interface.py`](#5-abstract-interface)
6. [Seed Prices & Correlation — `seed_prices.py`](#6-seed-prices--correlation)
7. [GBM Simulator — `simulator.py`](#7-gbm-simulator)
8. [Massive API Client — `massive_client.py`](#8-massive-api-client)
9. [Factory & SSE Endpoint — `factory.py`, `stream.py`](#9-factory--sse-endpoint)
10. [FastAPI Lifecycle Integration (design)](#10-fastapi-lifecycle-integration-design)
11. [Permanent Massive Failover (design)](#11-permanent-massive-failover-design)
12. [Watchlist Coordination (design)](#12-watchlist-coordination-design)
13. [Testing Strategy](#13-testing-strategy)
14. [Error Handling & Edge Cases](#14-error-handling--edge-cases)
15. [Configuration Summary](#15-configuration-summary)

---

## 1. Architecture

```
                       MarketDataSource (ABC)
                      /                      \
          SimulatorDataSource            MassiveDataSource
          (GBM, in-process,               (REST poll,
           always available)               MASSIVE_API_KEY set)
                      \                      /
                       v                    v
                          PriceCache
                       (thread-safe, in-memory,
                        one writer, many readers)
                       /        |         \
                      v         v          v
             SSE stream   Portfolio    Trade execution
             endpoint     valuation    (backend/app/api, not yet built)
```

Both data sources implement one abstract contract (`MarketDataSource`) and push into one shared
cache (`PriceCache`). Nothing downstream — SSE streaming, portfolio math, trade execution — ever
branches on which source is active; it only ever reads from the cache. This is a straightforward
strategy pattern plus a shared mutable store as the seam between producer and consumers, chosen
so that:

- The simulator (500ms ticks) and Massive (15s+ polls) can have wildly different update cadences
  without either one leaking into the SSE layer's own cadence.
- A future permanent failover from Massive to the simulator (§11) is just "swap which object
  writes to the cache" — no downstream code changes.
- A future multi-user version could give each user session its own `PriceCache` while still
  sharing one upstream poller, without changing this interface (see `MARKET_INTERFACE.md`).

## 2. File Structure

```
backend/
  app/
    market/
      __init__.py             # Re-exports: PriceUpdate, PriceCache, MarketDataSource,
                               #             create_market_data_source, create_stream_router
      models.py                # PriceUpdate dataclass
      cache.py                 # PriceCache (thread-safe in-memory store)
      interface.py              # MarketDataSource ABC
      seed_prices.py            # SEED_PRICES, TICKER_PARAMS, DEFAULT_PARAMS, CORRELATION_GROUPS
      simulator.py               # GBMSimulator + SimulatorDataSource
      massive_client.py          # MassiveDataSource
      factory.py                  # create_market_data_source()
      stream.py                    # SSE endpoint (FastAPI router factory)
  tests/
    market/
      test_models.py            # 11 tests
      test_cache.py              # 13 tests
      test_simulator.py           # 17 tests (GBMSimulator math)
      test_simulator_source.py     # 10 tests (SimulatorDataSource integration)
      test_factory.py               # 7 tests
      test_massive.py                # 13 tests (MassiveDataSource, mocked client)
  market_data_demo.py            # Rich terminal dashboard, `uv run market_data_demo.py`
```

Each module has a single responsibility; `__init__.py` re-exports the public surface so the rest
of the backend imports from `app.market` rather than reaching into submodules.

---

## 3. Data Model

**File: `backend/app/market/models.py`**

`PriceUpdate` is the only type that leaves the market data layer. SSE payloads, portfolio
valuation, and trade execution all consume it, never raw floats.

```python
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PriceUpdate:
    """Immutable snapshot of a single ticker's price at a point in time."""

    ticker: str
    price: float
    previous_price: float
    timestamp: float = field(default_factory=time.time)  # Unix seconds

    @property
    def change(self) -> float:
        """Absolute price change from previous update."""
        return round(self.price - self.previous_price, 4)

    @property
    def change_percent(self) -> float:
        """Percentage change from previous update."""
        if self.previous_price == 0:
            return 0.0
        return round((self.price - self.previous_price) / self.previous_price * 100, 4)

    @property
    def direction(self) -> str:
        """'up', 'down', or 'flat'."""
        if self.price > self.previous_price:
            return "up"
        elif self.price < self.previous_price:
            return "down"
        return "flat"

    def to_dict(self) -> dict:
        """Serialize for JSON / SSE transmission."""
        return {
            "ticker": self.ticker,
            "price": self.price,
            "previous_price": self.previous_price,
            "timestamp": self.timestamp,
            "change": self.change,
            "change_percent": self.change_percent,
            "direction": self.direction,
        }
```

**Design decisions**

- `frozen=True` — a price update is a value object, not something mutated in place; every price
  change produces a new instance, so it is safe to hand references across async tasks without
  defensive copying.
- `slots=True` — many of these are created per second (10 tickers × 2 ticks/sec minimum); slots
  avoid the per-instance `__dict__` overhead.
- `change` / `change_percent` / `direction` are computed properties, not stored fields — there is
  exactly one definition of what "up" means, and no code path can write a `PriceUpdate` with a
  stale direction.
- `to_dict()` is the single serialization point, shared by the SSE endpoint (§9) and (later) any
  REST endpoint that returns price data directly.

---

## 4. Price Cache

**File: `backend/app/market/cache.py`**

The cache is the seam between producer (whichever `MarketDataSource` is active) and consumers
(SSE endpoint, portfolio valuation, trade execution). It must be thread-safe: the Massive client's
synchronous call runs inside `asyncio.to_thread()`, i.e. a real OS thread, so an `asyncio.Lock`
would not protect it — `threading.Lock` works correctly from both a sync thread and the event loop.

```python
from __future__ import annotations

import time
from threading import Lock

from .models import PriceUpdate


class PriceCache:
    """Thread-safe in-memory cache of the latest price for each ticker.

    Writers: SimulatorDataSource or MassiveDataSource (one at a time).
    Readers: SSE streaming endpoint, portfolio valuation, trade execution.
    """

    def __init__(self) -> None:
        self._prices: dict[str, PriceUpdate] = {}
        self._lock = Lock()
        self._version: int = 0  # Monotonically increasing; bumped on every update

    def update(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate:
        """Record a new price for a ticker. Returns the created PriceUpdate.

        Automatically computes direction and change from the previous price.
        If this is the first update for the ticker, previous_price == price (direction='flat').
        """
        with self._lock:
            ts = timestamp or time.time()
            prev = self._prices.get(ticker)
            previous_price = prev.price if prev else price

            update = PriceUpdate(
                ticker=ticker,
                price=round(price, 2),
                previous_price=round(previous_price, 2),
                timestamp=ts,
            )
            self._prices[ticker] = update
            self._version += 1
            return update

    def get(self, ticker: str) -> PriceUpdate | None:
        """Get the latest price for a single ticker, or None if unknown."""
        with self._lock:
            return self._prices.get(ticker)

    def get_all(self) -> dict[str, PriceUpdate]:
        """Snapshot of all current prices. Returns a shallow copy."""
        with self._lock:
            return dict(self._prices)

    def get_price(self, ticker: str) -> float | None:
        """Convenience: get just the price float, or None."""
        update = self.get(ticker)
        return update.price if update else None

    def remove(self, ticker: str) -> None:
        """Remove a ticker from the cache (e.g., when removed from watchlist)."""
        with self._lock:
            self._prices.pop(ticker, None)

    @property
    def version(self) -> int:
        """Current version counter. Useful for SSE change detection."""
        return self._version

    def __len__(self) -> int:
        with self._lock:
            return len(self._prices)

    def __contains__(self, ticker: str) -> bool:
        with self._lock:
            return ticker in self._prices
```

**Why a version counter.** The SSE loop (§9) polls the cache every ~500ms. Without a version
counter it would serialize and push every tracked ticker on every tick even when nothing changed
— wasteful in general, and actively misleading while Massive is active, since Massive only
updates every 15s and a constant stream of "new" events would make the frontend's flash animation
fire for prices that never moved. The counter turns "did anything change" into an integer
comparison instead of a dict diff:

```python
last_version = -1
while True:
    if price_cache.version != last_version:
        last_version = price_cache.version
        yield format_sse(price_cache.get_all())
    await asyncio.sleep(0.5)
```

`update()` looks up the ticker's existing entry to compute `previous_price` itself — callers only
ever supply the new price, never a delta, which is what keeps `SimulatorDataSource` and
`MassiveDataSource` from needing to track "last price" state of their own on top of what the
simulator/API already gives them.

---

## 5. Abstract Interface

**File: `backend/app/market/interface.py`**

```python
from __future__ import annotations

from abc import ABC, abstractmethod


class MarketDataSource(ABC):
    """Contract for market data providers.

    Implementations push price updates into a shared PriceCache on their own
    schedule. Downstream code never calls the data source directly for prices —
    it reads from the cache.

    Lifecycle:
        source = create_market_data_source(cache)
        await source.start(["AAPL", "GOOGL", ...])
        # ... app runs ...
        await source.add_ticker("TSLA")
        await source.remove_ticker("GOOGL")
        # ... app shutting down ...
        await source.stop()
    """

    @abstractmethod
    async def start(self, tickers: list[str]) -> None:
        """Begin producing price updates for the given tickers.

        Starts a background task that periodically writes to the PriceCache.
        Must be called exactly once. Calling start() twice is undefined behavior.
        """

    @abstractmethod
    async def stop(self) -> None:
        """Stop the background task and release resources.

        Safe to call multiple times. After stop(), the source will not write
        to the cache again.
        """

    @abstractmethod
    async def add_ticker(self, ticker: str) -> None:
        """Add a ticker to the active set. No-op if already present.

        The next update cycle will include this ticker.
        """

    @abstractmethod
    async def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker from the active set. No-op if not present.

        Also removes the ticker from the PriceCache.
        """

    @abstractmethod
    def get_tickers(self) -> list[str]:
        """Return the current list of actively tracked tickers."""
```

Push, not pull: implementations write into the cache on their own schedule rather than returning
prices from a method the caller invokes. This is what lets the simulator tick at 500ms and Massive
poll at 15s while the SSE layer reads at its own constant cadence with zero knowledge of which
source is active or how often it updates.

`get_tickers()` is intentionally synchronous (not a coroutine) — it is a cheap, non-blocking read
of state each implementation already holds in memory (`GBMSimulator._tickers` /
`MassiveDataSource._tickers`), with no I/O involved, so there is no reason to force it through the
event loop.

---

## 6. Seed Prices & Correlation

**File: `backend/app/market/seed_prices.py`**

Constants only — no logic, no imports beyond the standard library. Shared by the simulator (for
initial prices and GBM parameters) and reusable later as a fallback if Massive hasn't polled yet.

```python
"""Seed prices and per-ticker parameters for the market simulator."""

# Realistic starting prices for the default watchlist (as of project creation)
SEED_PRICES: dict[str, float] = {
    "AAPL": 190.00,
    "GOOGL": 175.00,
    "MSFT": 420.00,
    "AMZN": 185.00,
    "TSLA": 250.00,
    "NVDA": 800.00,
    "META": 500.00,
    "JPM": 195.00,
    "V": 280.00,
    "NFLX": 600.00,
}

# Per-ticker GBM parameters
# sigma: annualized volatility (higher = more price movement)
# mu: annualized drift / expected return
TICKER_PARAMS: dict[str, dict[str, float]] = {
    "AAPL": {"sigma": 0.22, "mu": 0.05},
    "GOOGL": {"sigma": 0.25, "mu": 0.05},
    "MSFT": {"sigma": 0.20, "mu": 0.05},
    "AMZN": {"sigma": 0.28, "mu": 0.05},
    "TSLA": {"sigma": 0.50, "mu": 0.03},  # High volatility
    "NVDA": {"sigma": 0.40, "mu": 0.08},  # High volatility, strong drift
    "META": {"sigma": 0.30, "mu": 0.05},
    "JPM": {"sigma": 0.18, "mu": 0.04},  # Low volatility (bank)
    "V": {"sigma": 0.17, "mu": 0.04},  # Low volatility (payments)
    "NFLX": {"sigma": 0.35, "mu": 0.05},
}

# Default parameters for tickers not in the list above (dynamically added)
DEFAULT_PARAMS: dict[str, float] = {"sigma": 0.25, "mu": 0.05}

# Correlation groups for the simulator's Cholesky decomposition
# Tickers in the same group have higher intra-group correlation
CORRELATION_GROUPS: dict[str, set[str]] = {
    "tech": {"AAPL", "GOOGL", "MSFT", "AMZN", "META", "NVDA", "NFLX"},
    "finance": {"JPM", "V"},
}

# Correlation coefficients
INTRA_TECH_CORR = 0.6  # Tech stocks move together
INTRA_FINANCE_CORR = 0.5  # Finance stocks move together
CROSS_GROUP_CORR = 0.3  # Between sectors / unknown tickers
TSLA_CORR = 0.3  # TSLA does its own thing
```

Tickers added dynamically (watchlist add, or the AI chat's `watchlist_changes`) that aren't in
`TICKER_PARAMS`/`SEED_PRICES` fall back to `DEFAULT_PARAMS` and a random seed price in
`[$50, $300]` (see `GBMSimulator._add_ticker_internal` in §7) — plausible enough for a ticker the
simulator has no real data for, without a lookup to an external source just to pick a starting
point.

---

## 7. GBM Simulator

**File: `backend/app/market/simulator.py`**

Two classes live here: `GBMSimulator` is pure math/state with no asyncio or cache dependency —
`step()` is the hot path and is independently unit-testable by calling it directly and inspecting
returned prices. `SimulatorDataSource` is the thin asyncio wrapper that owns the background task
and writes results into the shared `PriceCache`.

### 7.1 The model

Each ticker's price evolves under Geometric Brownian Motion, the standard continuous-time model
for a randomly walking asset price:

```
S(t+dt) = S(t) * exp((mu - sigma^2/2) * dt + sigma * sqrt(dt) * Z)
```

- `S(t)` — current price
- `mu` — annualized drift (expected return)
- `sigma` — annualized volatility
- `dt` — time step, as a fraction of a trading year
- `Z` — a standard normal random draw, correlated across tickers (§7.2)

The `-sigma^2/2` term is the Itô correction that keeps the *expected* price growth at `mu` despite
compounding a lognormal process — without it, volatility alone would bias the price upward over
time as a model artifact, not because `mu` increased.

`dt` is 500ms expressed as a fraction of a trading year:

```python
TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600  # 5,896,800 (252 trading days, 6.5h sessions)
DEFAULT_DT = 0.5 / TRADING_SECONDS_PER_YEAR   # ~8.48e-8
```

At this scale each tick's drift/diffusion terms are sub-cent, so prices tick continuously rather
than jump, while the annualized `sigma`/`mu` still produce realistic day-over-day ranges once
compounded across thousands of ticks.

### 7.2 Correlated moves

Real markets don't move ticker-by-ticker independently. The simulator draws correlated, not
independent, random shocks each tick:

1. Build an `n x n` correlation matrix from sector groupings in `seed_prices.py` — same-tech pair
   → `0.6`, same-finance pair → `0.5`, anything involving TSLA → `0.3` (TSLA moves independently of
   even other tech names), everything else (cross-sector or unknown tickers) → `0.3`.
2. Cholesky-decompose that matrix once per ticker-set change (add/remove) — `O(n^2)`, cheap enough
   to rebuild on membership changes, wasteful to redo every 500ms tick.
3. Each tick: draw `n` independent standard normals, multiply by the Cholesky factor to get `n`
   correlated standard normals.

```python
z_independent = np.random.standard_normal(n)
z_correlated = self._cholesky @ z_independent
```

With `n < 50` tickers this whole step — including a matrix rebuild on membership change — is fast
enough to run inline in the same coroutine as the price update.

### 7.3 Random shock events

A small per-tick, per-ticker chance (`event_probability = 0.001`, 0.1%) of a sudden 2–5% move,
sign chosen at random — with 10 tickers at 2 ticks/sec, roughly one shock somewhere in the
watchlist every ~50 seconds, enough to periodically produce a dramatic flash without every demo
session looking scripted or a short demo never seeing one.

### 7.4 Code

```python
from __future__ import annotations

import asyncio
import logging
import math
import random

import numpy as np

from .cache import PriceCache
from .interface import MarketDataSource
from .seed_prices import (
    CORRELATION_GROUPS,
    CROSS_GROUP_CORR,
    DEFAULT_PARAMS,
    INTRA_FINANCE_CORR,
    INTRA_TECH_CORR,
    SEED_PRICES,
    TICKER_PARAMS,
    TSLA_CORR,
)

logger = logging.getLogger(__name__)


class GBMSimulator:
    """Geometric Brownian Motion simulator for correlated stock prices."""

    # 252 trading days * 6.5 hours/day * 3600 seconds/hour = 5,896,800 seconds
    TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600  # 5,896,800
    DEFAULT_DT = 0.5 / TRADING_SECONDS_PER_YEAR  # ~8.48e-8

    def __init__(
        self,
        tickers: list[str],
        dt: float = DEFAULT_DT,
        event_probability: float = 0.001,
    ) -> None:
        self._dt = dt
        self._event_prob = event_probability
        self._tickers: list[str] = []
        self._prices: dict[str, float] = {}
        self._params: dict[str, dict[str, float]] = {}
        self._cholesky: np.ndarray | None = None

        for ticker in tickers:
            self._add_ticker_internal(ticker)
        self._rebuild_cholesky()

    def step(self) -> dict[str, float]:
        """Advance all tickers by one time step. Returns {ticker: new_price}.

        This is the hot path — called every 500ms. Keep it fast.
        """
        n = len(self._tickers)
        if n == 0:
            return {}

        z_independent = np.random.standard_normal(n)
        z_correlated = self._cholesky @ z_independent if self._cholesky is not None else z_independent

        result: dict[str, float] = {}
        for i, ticker in enumerate(self._tickers):
            params = self._params[ticker]
            mu, sigma = params["mu"], params["sigma"]

            drift = (mu - 0.5 * sigma**2) * self._dt
            diffusion = sigma * math.sqrt(self._dt) * z_correlated[i]
            self._prices[ticker] *= math.exp(drift + diffusion)

            if random.random() < self._event_prob:
                shock_magnitude = random.uniform(0.02, 0.05)
                shock_sign = random.choice([-1, 1])
                self._prices[ticker] *= 1 + shock_magnitude * shock_sign
                logger.debug(
                    "Random event on %s: %.1f%% %s",
                    ticker, shock_magnitude * 100, "up" if shock_sign > 0 else "down",
                )

            result[ticker] = round(self._prices[ticker], 2)

        return result

    def add_ticker(self, ticker: str) -> None:
        """Add a ticker to the simulation. Rebuilds the correlation matrix."""
        if ticker in self._prices:
            return
        self._add_ticker_internal(ticker)
        self._rebuild_cholesky()

    def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker from the simulation. Rebuilds the correlation matrix."""
        if ticker not in self._prices:
            return
        self._tickers.remove(ticker)
        del self._prices[ticker]
        del self._params[ticker]
        self._rebuild_cholesky()

    def get_price(self, ticker: str) -> float | None:
        return self._prices.get(ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)

    def _add_ticker_internal(self, ticker: str) -> None:
        """Add a ticker without rebuilding Cholesky (for batch initialization)."""
        if ticker in self._prices:
            return
        self._tickers.append(ticker)
        self._prices[ticker] = SEED_PRICES.get(ticker, random.uniform(50.0, 300.0))
        self._params[ticker] = TICKER_PARAMS.get(ticker, dict(DEFAULT_PARAMS))

    def _rebuild_cholesky(self) -> None:
        """Rebuild the Cholesky decomposition of the ticker correlation matrix.

        Called whenever tickers are added or removed. O(n^2) but n < 50.
        """
        n = len(self._tickers)
        if n <= 1:
            self._cholesky = None
            return

        corr = np.eye(n)
        for i in range(n):
            for j in range(i + 1, n):
                rho = self._pairwise_correlation(self._tickers[i], self._tickers[j])
                corr[i, j] = corr[j, i] = rho

        self._cholesky = np.linalg.cholesky(corr)

    @staticmethod
    def _pairwise_correlation(t1: str, t2: str) -> float:
        tech = CORRELATION_GROUPS["tech"]
        finance = CORRELATION_GROUPS["finance"]

        if t1 == "TSLA" or t2 == "TSLA":
            return TSLA_CORR
        if t1 in tech and t2 in tech:
            return INTRA_TECH_CORR
        if t1 in finance and t2 in finance:
            return INTRA_FINANCE_CORR
        return CROSS_GROUP_CORR


class SimulatorDataSource(MarketDataSource):
    """MarketDataSource backed by the GBM simulator.

    Runs a background asyncio task that calls GBMSimulator.step() every
    `update_interval` seconds and writes results to the PriceCache.
    """

    def __init__(
        self,
        price_cache: PriceCache,
        update_interval: float = 0.5,
        event_probability: float = 0.001,
    ) -> None:
        self._cache = price_cache
        self._interval = update_interval
        self._event_prob = event_probability
        self._sim: GBMSimulator | None = None
        self._task: asyncio.Task | None = None

    async def start(self, tickers: list[str]) -> None:
        self._sim = GBMSimulator(tickers=tickers, event_probability=self._event_prob)
        # Seed the cache with initial prices so SSE has data immediately
        for ticker in tickers:
            price = self._sim.get_price(ticker)
            if price is not None:
                self._cache.update(ticker=ticker, price=price)
        self._task = asyncio.create_task(self._run_loop(), name="simulator-loop")
        logger.info("Simulator started with %d tickers", len(tickers))

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("Simulator stopped")

    async def add_ticker(self, ticker: str) -> None:
        if self._sim:
            self._sim.add_ticker(ticker)
            price = self._sim.get_price(ticker)
            if price is not None:
                self._cache.update(ticker=ticker, price=price)
            logger.info("Simulator: added ticker %s", ticker)

    async def remove_ticker(self, ticker: str) -> None:
        if self._sim:
            self._sim.remove_ticker(ticker)
        self._cache.remove(ticker)
        logger.info("Simulator: removed ticker %s", ticker)

    def get_tickers(self) -> list[str]:
        return self._sim.get_tickers() if self._sim else []

    async def _run_loop(self) -> None:
        """Core loop: step the simulation, write to cache, sleep."""
        while True:
            try:
                if self._sim:
                    prices = self._sim.step()
                    for ticker, price in prices.items():
                        self._cache.update(ticker=ticker, price=price)
            except Exception:
                logger.exception("Simulator step failed")
            await asyncio.sleep(self._interval)
```

**Key behaviors**

- **Immediate seeding**: `start()` populates the cache with seed prices *before* the loop begins,
  and `add_ticker()` does the same for a ticker added mid-run — the SSE endpoint never has a
  "blank until first tick" gap for a ticker the simulator is tracking.
- **Graceful cancellation**: `stop()` cancels the task and awaits it, swallowing
  `CancelledError` — the expected shape for clean shutdown during FastAPI lifespan teardown, and
  idempotent (`stop()` is a no-op if called again, since `self._task` is already `None`).
- **Exception resilience**: the loop wraps each `step()` call in `try/except Exception`, so one
  bad tick logs and the loop continues rather than silently killing the whole feed.

**What this deliberately skips** (per `MARKET_SIMULATOR.md`): no order book / bid-ask spread — a
single tradable price per tick is all market-orders-only trading needs; no market-hours gating —
the simulator runs continuously so a course demo doesn't go quiet at 9pm; no persistence of
simulated state across restarts — prices reseed from `SEED_PRICES` every process start, unlike
the SQLite-backed portfolio data which must survive restarts.

---

## 8. Massive API Client

**File: `backend/app/market/massive_client.py`**

Polls the Massive (formerly Polygon.io) snapshot-all endpoint on an interval — one API call
covers the whole tracked ticker set, which is what keeps a 10+ ticker watchlist inside the free
tier's 5-calls/minute budget. The synchronous `massive` client runs in `asyncio.to_thread()` so it
never blocks the event loop.

```python
from __future__ import annotations

import asyncio
import logging

from massive import RESTClient
from massive.rest.models import SnapshotMarketType

from .cache import PriceCache
from .interface import MarketDataSource

logger = logging.getLogger(__name__)


class MassiveDataSource(MarketDataSource):
    """MarketDataSource backed by the Massive (Polygon.io) REST API.

    Polls GET /v2/snapshot/locale/us/markets/stocks/tickers for all watched
    tickers in a single API call, then writes results to the PriceCache.

    Rate limits:
      - Free tier: 5 req/min -> poll every 15s (default)
      - Paid tiers: higher limits -> poll every 2-5s
    """

    def __init__(
        self,
        api_key: str,
        price_cache: PriceCache,
        poll_interval: float = 15.0,
    ) -> None:
        self._api_key = api_key
        self._cache = price_cache
        self._interval = poll_interval
        self._tickers: list[str] = []
        self._task: asyncio.Task | None = None
        self._client: RESTClient | None = None

    async def start(self, tickers: list[str]) -> None:
        self._client = RESTClient(api_key=self._api_key)
        self._tickers = list(tickers)

        # Immediate first poll so the cache has data right away
        await self._poll_once()

        self._task = asyncio.create_task(self._poll_loop(), name="massive-poller")
        logger.info(
            "Massive poller started: %d tickers, %.1fs interval",
            len(tickers), self._interval,
        )

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        self._client = None
        logger.info("Massive poller stopped")

    async def add_ticker(self, ticker: str) -> None:
        ticker = ticker.upper().strip()
        if ticker not in self._tickers:
            self._tickers.append(ticker)
            logger.info("Massive: added ticker %s (will appear on next poll)", ticker)

    async def remove_ticker(self, ticker: str) -> None:
        ticker = ticker.upper().strip()
        self._tickers = [t for t in self._tickers if t != ticker]
        self._cache.remove(ticker)
        logger.info("Massive: removed ticker %s", ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)

    async def _poll_loop(self) -> None:
        """Poll on interval. First poll already happened in start()."""
        while True:
            await asyncio.sleep(self._interval)
            await self._poll_once()

    async def _poll_once(self) -> None:
        """Execute one poll cycle: fetch snapshots, update cache."""
        if not self._tickers or not self._client:
            return

        try:
            snapshots = await asyncio.to_thread(self._fetch_snapshots)
            processed = 0
            for snap in snapshots:
                try:
                    price = snap.last_trade.price
                    # Massive client normalizes trade timestamps to milliseconds -> seconds
                    timestamp = snap.last_trade.timestamp / 1000.0
                    self._cache.update(ticker=snap.ticker, price=price, timestamp=timestamp)
                    processed += 1
                except (AttributeError, TypeError) as e:
                    logger.warning("Skipping snapshot for %s: %s", getattr(snap, "ticker", "???"), e)
            logger.debug("Massive poll: updated %d/%d tickers", processed, len(self._tickers))

        except Exception as e:
            logger.error("Massive poll failed: %s", e)
            # No re-raise: a single failed poll must not crash the background task.
            # See §11 for how a failure here becomes a *permanent* failover decision.

    def _fetch_snapshots(self) -> list:
        """Synchronous call to the Massive REST API. Runs in a thread."""
        return self._client.get_snapshot_all(
            market_type=SnapshotMarketType.STOCKS,
            tickers=self._tickers,
        )
```

`massive` is a core dependency (declared in `pyproject.toml`, imported at module level) rather
than a lazily-imported optional one — every FinAlly install gets the same dependency set whether
or not `MASSIVE_API_KEY` is set, which keeps the lockfile and CI environment identical across both
code paths and avoids an `ImportError` surprise the first time a student adds a key.

**Why `_poll_once()` never raises.** `MarketDataSource.stop()`'s contract is that the background
task can be cancelled cleanly; letting a poll exception propagate out of `_poll_loop()` would kill
the task outright and silently stop all price updates. Catching broadly here and logging keeps the
loop alive across transient failures (a single dropped request, a momentary rate-limit blip) —
the *permanent* failover decision on more serious errors is made one layer up, in the FastAPI
lifespan code, per §11 below (this is also why `MASSIVE_API.md`'s error table distinguishes
"logged" from "logged, triggers permanent failover" — that trigger doesn't live in this file).

Free tier reality check (`MASSIVE_API.md`): the free plan returns end-of-day prices only, so
polling it every 15s during market hours returns the same number until the next session. A
genuinely live feed against Massive needs at least the Starter plan (15-minute delayed) or
Advanced (real-time) — which is exactly why the simulator, not Massive, is FinAlly's default.

---

## 9. Factory & SSE Endpoint

**File: `backend/app/market/factory.py`**

```python
from __future__ import annotations

import logging
import os

from .cache import PriceCache
from .interface import MarketDataSource
from .massive_client import MassiveDataSource
from .simulator import SimulatorDataSource

logger = logging.getLogger(__name__)


def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
    """Create the appropriate market data source based on environment variables.

    - MASSIVE_API_KEY set and non-empty -> MassiveDataSource (real market data)
    - Otherwise -> SimulatorDataSource (GBM simulation)

    Returns an unstarted source. Caller must await source.start(tickers).
    """
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()

    if api_key:
        logger.info("Market data source: Massive API (real data)")
        return MassiveDataSource(api_key=api_key, price_cache=price_cache)
    else:
        logger.info("Market data source: GBM Simulator")
        return SimulatorDataSource(price_cache=price_cache)
```

This function is the entirety of PLAN.md §5's source-selection logic. Nothing else in the
codebase reads `MASSIVE_API_KEY` directly — every other module asks for "the market data source"
and gets whichever one the factory decided on.

**File: `backend/app/market/stream.py`**

```python
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .cache import PriceCache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stream", tags=["streaming"])


def create_stream_router(price_cache: PriceCache) -> APIRouter:
    """Create the SSE streaming router with a reference to the price cache.

    This factory pattern lets us inject the PriceCache without globals.
    """

    @router.get("/prices")
    async def stream_prices(request: Request) -> StreamingResponse:
        """SSE endpoint for live price updates.

        Streams all tracked ticker prices every ~500ms. The client connects
        with EventSource and receives events shaped:

            data: {"AAPL": {"ticker": "AAPL", "price": 190.50, ...}, ...}

        Includes a retry directive so the browser auto-reconnects on
        disconnection (EventSource built-in behavior).
        """
        return StreamingResponse(
            _generate_events(price_cache, request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering if proxied
            },
        )

    return router


async def _generate_events(
    price_cache: PriceCache,
    request: Request,
    interval: float = 0.5,
) -> AsyncGenerator[str, None]:
    """Async generator that yields SSE-formatted price events.

    Sends all prices every `interval` seconds. Stops when the client
    disconnects (detected via request.is_disconnected()).
    """
    yield "retry: 1000\n\n"

    last_version = -1
    client_ip = request.client.host if request.client else "unknown"
    logger.info("SSE client connected: %s", client_ip)

    try:
        while True:
            if await request.is_disconnected():
                logger.info("SSE client disconnected: %s", client_ip)
                break

            current_version = price_cache.version
            if current_version != last_version:
                last_version = current_version
                prices = price_cache.get_all()
                if prices:
                    data = {ticker: update.to_dict() for ticker, update in prices.items()}
                    yield f"data: {json.dumps(data)}\n\n"

            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logger.info("SSE stream cancelled for: %s", client_ip)
```

**Wire format.** Every push is one SSE `data:` frame carrying every tracked ticker (not just the
one that changed) as a JSON object keyed by ticker:

```
data: {"AAPL":{"ticker":"AAPL","price":190.50,"previous_price":190.42,"timestamp":1707580800.5,"change":0.08,"change_percent":0.042,"direction":"up"},"GOOGL":{...}}

```

Sending the whole set rather than a diff is the simplest correct behavior — the payload for 10–20
tickers is a few hundred bytes, far below the threshold where diffing would matter — and it means
a client that missed no events still has a complete, self-consistent snapshot on every message.
Client-side:

```javascript
const eventSource = new EventSource('/api/stream/prices');
eventSource.onmessage = (event) => {
  const prices = JSON.parse(event.data);   // { AAPL: {...}, GOOGL: {...}, ... }
};
```

`retry: 1000` is sent once at connection open so `EventSource`'s built-in reconnect logic retries
1 second after a drop — this is the entire "SSE resilience" story from PLAN.md §12; there is no
custom reconnect code on either side because the browser API already provides it.

**Package surface — `backend/app/market/__init__.py`**

```python
"""Market data subsystem for FinAlly."""

from .cache import PriceCache
from .factory import create_market_data_source
from .interface import MarketDataSource
from .models import PriceUpdate
from .stream import create_stream_router

__all__ = [
    "PriceUpdate",
    "PriceCache",
    "MarketDataSource",
    "create_market_data_source",
    "create_stream_router",
]
```

---

## 10. FastAPI Lifecycle Integration (design)

*Not yet implemented — `backend/app/main.py` does not exist yet. This section designs the piece
that will start/stop the market data subsystem alongside the FastAPI app, using the standard
`lifespan` context manager.*

```python
# backend/app/main.py  (design)

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.market import PriceCache, create_market_data_source, create_stream_router
from app.db import get_watchlist_tickers, get_position_tickers  # backend/db, not yet built


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP ---
    price_cache = PriceCache()
    app.state.price_cache = price_cache

    source = create_market_data_source(price_cache)
    app.state.market_source = source

    # Active ticker set = watchlist UNION open positions (PLAN.md §6)
    watchlist = await get_watchlist_tickers()
    held = await get_position_tickers()
    initial_tickers = sorted(set(watchlist) | set(held))
    await source.start(initial_tickers)

    app.include_router(create_stream_router(price_cache))

    yield  # app is running

    # --- SHUTDOWN ---
    await source.stop()


app = FastAPI(title="FinAlly", lifespan=lifespan)


def get_price_cache() -> PriceCache:
    return app.state.price_cache


def get_market_source() -> MarketDataSource:
    return app.state.market_source
```

`app.state` holds the two long-lived singletons (`price_cache`, `market_source`); route handlers
pull them out through FastAPI's dependency injection rather than importing a module-level global,
which keeps the market subsystem testable in isolation (a test can construct its own `PriceCache`
and source without touching `app.state`) — the same reason `create_market_data_source` and
`create_stream_router` are both plain factory functions instead of module-level singletons.

```python
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/api")

@router.post("/portfolio/trade")
async def execute_trade(trade: TradeRequest, price_cache: PriceCache = Depends(get_price_cache)):
    current_price = price_cache.get_price(trade.ticker)
    if current_price is None:
        raise HTTPException(404, f"No price available for {trade.ticker}")
    # ... execute trade at current_price ...
```

---

## 11. Permanent Massive Failover (design)

*Not yet implemented. PLAN.md §5/§6 require that any Massive failure — auth error, rate limit,
network error, service error, at startup or mid-run — permanently switches the app to the
simulator for the rest of the run, and never switches back. `MassiveDataSource._poll_once()` (§8)
already logs every failure but deliberately does not raise, so by itself it cannot trigger a
one-time policy decision like "stop trying Massive forever" — that decision belongs one level up,
where the app owns the single `market_source` reference `app.state` points at. This section
designs that orchestration layer.*

### 11.1 Shape of the problem

`MassiveDataSource` swallows every poll exception so that a single dropped request doesn't kill
its own background task. But PLAN.md doesn't want "retry forever quietly" — it wants "the first
failure of any kind ends the Massive experiment for this run." Reconciling those means
`MassiveDataSource` needs to report failures upward without itself deciding what happens next.

### 11.2 Failure callback

Add an optional callback to `MassiveDataSource`, invoked at most once, on the first poll failure:

```python
class MassiveDataSource(MarketDataSource):
    def __init__(
        self,
        api_key: str,
        price_cache: PriceCache,
        poll_interval: float = 15.0,
        on_failure: Callable[[Exception], None] | None = None,
    ) -> None:
        ...
        self._on_failure = on_failure
        self._failure_reported = False

    async def _poll_once(self) -> None:
        if not self._tickers or not self._client:
            return
        try:
            snapshots = await asyncio.to_thread(self._fetch_snapshots)
            ...
        except Exception as e:
            logger.error("Massive poll failed: %s", e)
            if self._on_failure is not None and not self._failure_reported:
                self._failure_reported = True
                self._on_failure(e)
```

`_failure_reported` makes the callback fire exactly once even though `_poll_loop()` keeps calling
`_poll_once()` on its interval after the failure — the loop itself doesn't need to know it's about
to be torn down; the orchestration layer below stops it.

`start()`'s own first poll (`await self._poll_once()`) goes through the same method, so a
startup-time auth failure (401 on the very first call) triggers the same callback as a later
mid-run failure — one code path for both cases in PLAN.md's requirement list.

### 11.3 The orchestrator

Owned by the lifespan code, since it is the only place holding the mutable `app.state.market_source`
reference that needs to be swapped:

```python
# backend/app/market_failover.py  (design)

import asyncio
import logging

from app.market import MarketDataSource, PriceCache
from app.market.massive_client import MassiveDataSource
from app.market.simulator import SimulatorDataSource

logger = logging.getLogger(__name__)


async def start_with_failover(app, price_cache: PriceCache, initial_tickers: list[str]) -> None:
    """Start the configured market data source; permanently fail over to the
    simulator on the first Massive error, per PLAN.md §5/§6."""
    from app.market.factory import create_market_data_source

    source = create_market_data_source(price_cache)
    app.state.market_source = source

    if not isinstance(source, MassiveDataSource):
        await source.start(initial_tickers)
        return

    failover_triggered = asyncio.Event()

    def on_failure(exc: Exception) -> None:
        logger.error("Massive failed permanently (%s) — failing over to simulator", exc)
        failover_triggered.set()

    source._on_failure = on_failure  # or thread through the constructor
    await source.start(initial_tickers)

    async def _watch_for_failover() -> None:
        await failover_triggered.wait()
        tracked = source.get_tickers()
        await source.stop()

        simulator = SimulatorDataSource(price_cache=price_cache)
        await simulator.start(tracked)
        app.state.market_source = simulator
        logger.info("Failover complete: now running the simulator with %d tickers", len(tracked))

    app.state.failover_watcher = asyncio.create_task(_watch_for_failover())
```

**Why a watcher task instead of failing over inline inside `on_failure`.** `on_failure` runs
synchronously from inside `_poll_once()`'s `except` block, on the Massive poller's own task —
stopping that task (`await source.stop()`) from within its own coroutine would deadlock on
`await self._task` inside `stop()`. Deferring the actual swap to a separate task woken by an
`asyncio.Event` avoids that, and keeps `_poll_once()` itself free of any awareness that a
permanent-failure policy exists above it.

**Why the transferred ticker set is `source.get_tickers()`, not the original `initial_tickers`.**
The active ticker set can grow or shrink between startup and the moment Massive fails (watchlist
adds/removes, positions opened/closed — see §12), so the simulator that takes over must start with
whatever the failed source was actually tracking at the moment of failure, not a stale snapshot
from app startup.

**Route handlers that call `add_ticker`/`remove_ticker` must read `app.state.market_source` fresh
on every request** (via `Depends(get_market_source)`, not a captured closure variable) — otherwise
a request that arrives after failover would still be talking to the now-stopped `MassiveDataSource`
instance.

---

## 12. Watchlist Coordination (design)

*Not yet implemented — the watchlist REST endpoints and their SQLite-backed storage belong to a
separate piece of backend work (PLAN.md §7 `watchlist` table, §8 watchlist endpoints). This
section designs how those endpoints talk to the market data layer once they exist.*

### Adding a ticker

```
POST /api/watchlist {ticker: "PYPL"}
  -> INSERT INTO watchlist (SQLite)
  -> await source.add_ticker("PYPL")
       Simulator: adds to GBMSimulator, rebuilds Cholesky, seeds cache immediately
       Massive:   appends to tracked list, appears on the next poll (no immediate cache entry)
  -> respond with the ticker and its current price if already cached, else null
```

```python
@router.post("/watchlist")
async def add_to_watchlist(
    payload: WatchlistAdd,
    source: MarketDataSource = Depends(get_market_source),
    price_cache: PriceCache = Depends(get_price_cache),
):
    ticker = payload.ticker.upper().strip()
    await db.insert_watchlist_entry(ticker)
    await source.add_ticker(ticker)
    return {"ticker": ticker, "price": price_cache.get_price(ticker)}
```

### Removing a ticker — the open-position guard

Per PLAN.md §6, the active ticker set (what's tracked and streamed) is the union of the watchlist
and any open positions. Removing a ticker from the watchlist must not stop its price updates while
shares are still held, or portfolio valuation and P&L display go stale:

```python
@router.delete("/watchlist/{ticker}")
async def remove_from_watchlist(
    ticker: str,
    source: MarketDataSource = Depends(get_market_source),
):
    ticker = ticker.upper().strip()
    await db.delete_watchlist_entry(ticker)

    position = await db.get_position(ticker)
    if position is None or position.quantity == 0:
        await source.remove_ticker(ticker)
    # else: leave it tracked — a position still references it

    return {"status": "ok"}
```

This check belongs in the watchlist route, not inside `MarketDataSource.remove_ticker()` itself —
the market data layer has no knowledge of positions or the database (see §1's design rationale:
`MarketDataSource` implementations only know "track this ticker or don't"). Symmetrically, when a
sell trade closes a position to zero on a ticker that was already removed from the watchlist, the
trade-execution code (not built yet, PLAN.md §8/§9) is responsible for calling
`source.remove_ticker()` at that point, using the same "is it still referenced" check.

---

## 13. Testing Strategy

The built subsystem (§3–§9) has 73 passing tests across 6 modules in `backend/tests/market/`,
84% overall coverage on `app/market/`:

| Module | Tests | What it covers |
|---|---|---|
| `test_models.py` | 11 | `PriceUpdate` properties (`change`, `change_percent`, `direction`, `to_dict`) — 100% |
| `test_cache.py` | 13 | `PriceCache` update/get/remove/version semantics, first-update-is-flat — 100% |
| `test_simulator.py` | 17 | `GBMSimulator` math: prices stay positive, add/remove rebuild Cholesky, unknown-ticker fallback, event frequency — 98% |
| `test_simulator_source.py` | 10 | `SimulatorDataSource` integration: cache seeded before first tick, clean/idempotent `stop()`, add/remove propagate to both simulator and cache |
| `test_factory.py` | 7 | Env-var-driven source selection — 100% |
| `test_massive.py` | 13 | `MassiveDataSource` against a mocked `RESTClient`: successful poll, malformed-snapshot skip, poll failure doesn't raise — 56% (expected; real API calls are mocked, not exercised) |

Run them with:

```bash
cd backend
uv run --extra dev pytest -v
uv run --extra dev pytest --cov=app
```

### Not yet covered — tests to add alongside §10–§12

- **Failover orchestration** (§11): a test double for `MassiveDataSource` whose `_poll_once`
  always raises, asserting that (a) `on_failure` fires exactly once even across repeated poll
  attempts, (b) the resulting `SimulatorDataSource` starts with the ticker set the Massive source
  held at the moment of failure, not the app-startup set, and (c) `app.state.market_source` after
  failover is the new simulator instance.
- **Lifespan integration** (§10): a FastAPI `TestClient`-driven test that the app starts with
  seeded prices already in the cache (SSE's first payload is non-empty) and that `source.stop()`
  is actually awaited on shutdown (no dangling `asyncio.Task` warnings).
- **Watchlist/position interaction** (§12): removing a watchlisted ticker that still has an open
  position keeps it in `source.get_tickers()`; removing one with no position drops it from both
  the source and the cache.
- **E2E** (`test/`, PLAN.md §12): "SSE resilience: disconnect and verify reconnection" exercises
  the `retry: 1000` directive end-to-end through a real browser `EventSource`, which unit tests
  against `_generate_events` directly cannot.

---

## 14. Error Handling & Edge Cases

| Scenario | Behavior |
|---|---|
| Empty watchlist at startup | `start([])` — simulator produces no prices, Massive's first poll is a no-op (`if not self._tickers: return`). SSE sends no `data:` frames until a ticker is added. |
| Trade requested for a ticker with no cached price | `price_cache.get_price(ticker)` returns `None`; the trade-execution route (not yet built) should reject with `400` and a message telling the user to wait a moment — the simulator avoids ever hitting this by seeding on `add_ticker()`, so it's mainly a Massive-cold-start scenario. |
| Massive API key present but invalid | First poll (inside `start()`) fails with 401; today it is only logged (§8) — after §11 is implemented, this is a startup-time failover trigger, so the app runs on the simulator for the entire session rather than showing an empty watchlist. |
| Massive poll returns a malformed snapshot for one ticker | That ticker is skipped with a `logger.warning`; other tickers in the same poll still update (§8, `except (AttributeError, TypeError)`). |
| All tickers fail in a Massive poll | `PriceCache` retains the last-known values (nothing is cleared on failure) — SSE keeps streaming stale-but-present data rather than blanking out, which is preferable for a chart that shouldn't visibly gap. |
| Client disconnects mid-stream | `request.is_disconnected()` is checked every loop iteration; the generator returns, FastAPI closes the response, no dangling task accumulates per client. |
| `PriceCache` under concurrent read/write | `threading.Lock` serializes access; the critical section is a dict lookup + assignment, negligible contention at FinAlly's scale (single-digit tickers, sub-second cadence). A `ReadWriteLock` would only matter at hundreds of tickers / many concurrent readers — not needed here. |
| GBM numerical stability | Prices are `round()`ed to 2 decimals every step; the `exp()` formulation is always positive by construction, so a simulated price can never go negative or NaN under normal float arithmetic. |
| `stop()` called twice | Both `SimulatorDataSource.stop()` and `MassiveDataSource.stop()` guard on `self._task and not self._task.done()` — a second call is a no-op, not an error (required by the `MarketDataSource` contract in §5). |

---

## 15. Configuration Summary

| Parameter | Location | Default | Description |
|---|---|---|---|
| `MASSIVE_API_KEY` | Environment variable | `""` (empty) | Non-empty -> Massive; empty -> simulator (`factory.py`) |
| `update_interval` | `SimulatorDataSource.__init__` | `0.5`s | Time between simulator ticks |
| `event_probability` | `GBMSimulator.__init__` | `0.001` | Chance of a random shock per ticker per tick |
| `dt` | `GBMSimulator.__init__` | `~8.48e-8` | GBM time step, fraction of a trading year |
| `poll_interval` | `MassiveDataSource.__init__` | `15.0`s | Time between Massive polls (free-tier safe; lower for paid plans) |
| SSE push interval | `_generate_events()` | `0.5`s | Cache poll cadence for the SSE generator |
| SSE retry directive | `_generate_events()` | `1000`ms | Browser `EventSource` reconnect delay |

All are constructor/function defaults, not currently environment-driven beyond `MASSIVE_API_KEY`
— PLAN.md doesn't call for the others to be configurable per-deployment, so they aren't, in line
with the project's "don't build for hypothetical requirements" default.
