# Coding Conventions

**Analysis Date:** 2026-08-22

## Naming Patterns

**Files:**
- Lowercase with underscores: `simulator.py`, `price_cache.py`, `market_data.py`
- Test files: `test_<module_name>.py` (e.g., `test_simulator.py`, `test_cache.py`)
- Private/internal files prefixed with underscore: `_generate_events` function in stream module
- Package modules use descriptive names matching their responsibility: `interface.py` for abstract base classes, `factory.py` for creation logic, `models.py` for data structures

**Functions:**
- Lowercase with underscores: `normalize_ticker()`, `_poll_once()`, `get_tickers()`, `add_ticker()`
- Private methods prefixed with single underscore: `_add_ticker_internal()`, `_rebuild_cholesky()`, `_pairwise_correlation()`, `_poll_loop()`
- Async functions use `async def`: `async def start()`, `async def stop()`, `async def add_ticker()`
- Properties use `@property` decorator for computed attributes: `@property def direction()`, `@property def version`
- Verb-noun pattern for actions: `update()`, `get()`, `remove()`, `fetch()`, `step()`

**Variables:**
- Lowercase with underscores for regular variables: `price_cache`, `previous_price`, `event_prob`, `update_interval`
- Private class attributes: `self._prices`, `self._lock`, `self._version`, `self._task`
- Constants: UPPERCASE with underscores: `DEFAULT_DT`, `TRADING_SECONDS_PER_YEAR`, `SEED_PRICES`
- Abbreviations acceptable: `dt` (delta time), `Z` (random normal), `S` (security price), `ts` (timestamp), `sim` (simulator)

**Types:**
- Type hints used throughout: `-> None`, `-> dict[str, float]`, `-> PriceUpdate | None`, `async def ... -> None`
- Union types use `|` syntax (Python 3.10+): `float | None` instead of `Optional[float]`
- Generic collections: `list[str]`, `dict[str, PriceUpdate]`
- Dataclass fields use type hints: `ticker: str`, `price: float`, `timestamp: float`

**Classes:**
- PascalCase: `PriceUpdate`, `PriceCache`, `GBMSimulator`, `SimulatorDataSource`, `MassiveDataSource`, `MarketDataSource`
- Test classes: `Test<Component>` (e.g., `TestPriceUpdate`, `TestPriceCache`, `TestSimulatorDataSource`)
- Abstract base classes: `MarketDataSource` (inherits from `ABC`)

## Code Style

**Formatting:**
- Line length: 100 characters (enforced by ruff configuration)
- Indentation: 4 spaces (Python standard)
- Module docstrings: Triple-quoted at top of file, concise one-liner: `"""Data models for market data."""`
- Class docstrings: Immediately after class declaration, full description of responsibility and public interface
- Method docstrings: Immediately after method signature, explain what it does, parameters if not obvious, return type if useful

**Linting:**
- Tool: `ruff` (installed as dev dependency)
- Configuration in `pyproject.toml`:
  - Line length: 100 characters
  - Target version: Python 3.12
  - Rules: E (errors), F (Pyflakes), I (import sort), N (naming), W (warnings)
  - Ignored: E501 (line too long, handled by formatter)
- Run with: `uv run --extra dev ruff check app/ tests/`
- No `.eslintrc` or `.prettierrc` — Python relies on ruff for both lint and format rules

## Import Organization

**Order:**
1. `from __future__ import annotations` (always first if used)
2. Standard library: `import asyncio`, `import logging`, `import os`, `from threading import Lock`
3. Third-party: `import numpy as np`, `from fastapi import ...`, `from massive import ...`
4. Local: `from .cache import PriceCache`, `from .interface import MarketDataSource`

**Path Aliases:**
- No aliases defined; imports use relative paths within packages
- Relative imports within a module: `from .models import PriceUpdate` (same level), `from .interface import MarketDataSource` (same level)
- Absolute imports from app root: `from app.market.cache import PriceCache`

**Import Style:**
- Single imports per line: `from threading import Lock` (not `from threading import Lock, RLock`)
- Exception: Multiple imports from same module acceptable if logically grouped: `from fastapi import APIRouter, Request`
- Avoid `import *`
- Import submodules explicitly rather than importing the parent and accessing attributes

## Error Handling

**Patterns:**
- Specific exception catching: `except asyncio.CancelledError:` (for cancellation), `except (AttributeError, TypeError):` (for parsing errors)
- Broad exception handling in background loops: `except Exception as e:` at the top level of polling/streaming tasks, log and continue (don't re-raise)
- Example from `massive_client.py`:
  ```python
  except Exception as e:
      logger.error("Massive poll failed: %s", e)
      # Don't re-raise — the loop will retry on the next interval.
  ```
- Validation errors: Return `None` or raise descriptive errors early; no silent failures
- Thread-safe error handling: Lock critical sections, use context managers
- Async task cancellation: Catch `asyncio.CancelledError` and handle cleanup gracefully:
  ```python
  if self._task and not self._task.done():
      self._task.cancel()
      try:
          await self._task
      except asyncio.CancelledError:
          pass
  ```

## Logging

**Framework:** Python `logging` module

**Patterns:**
- Module-level logger: `logger = logging.getLogger(__name__)` at top of each file
- Log levels:
  - `logger.debug()` for detailed info (e.g., "Random event on AAPL", cache version increments)
  - `logger.info()` for lifecycle events (e.g., "Simulator started with X tickers", "Massive poller started")
  - `logger.warning()` for recoverable errors (e.g., "Skipping snapshot for X: malformed data")
  - `logger.error()` for non-fatal failures that don't stop the app (e.g., "Massive poll failed: 401 Unauthorized")
- Do not log at `logger.critical()` level (reserved for unrecoverable failures)
- Example from `massive_client.py`:
  ```python
  logger.warning("Skipping snapshot for %s: %s", getattr(snap, "ticker", "???"), e)
  logger.error("Massive poll failed: %s", e)
  ```

## Comments

**When to Comment:**
- Docstrings for all public classes and functions (mandatory)
- Inline comments for non-obvious math, algorithm choices, or gotchas
- Example: GBM simulator includes mathematical formula comment:
  ```python
  # GBM: S(t+dt) = S(t) * exp((mu - 0.5*sigma^2)*dt + sigma*sqrt(dt)*Z)
  ```
- Example: Timestamp conversion in massive_client:
  ```python
  # Massive timestamps are Unix milliseconds → convert to seconds
  timestamp = snap.last_trade.timestamp / 1000.0
  ```

**JSDoc/TSDoc:**
- Not applicable (Python project)
- Use docstring format (PEP 257) for type and parameter documentation

## Function Design

**Size:** Methods are short and focused. Examples:
- `get_price()` in cache: 3 lines
- `remove()` in cache: 3 lines
- `normalize_ticker()` in interface: 2 lines
- Larger methods (e.g., `step()` in GBMSimulator) have clear sections with comments separating logic phases

**Parameters:**
- Type hints always included: `def update(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate:`
- Positional parameters for required args, keyword-only for optional
- Default values documented in docstring
- Factory functions pass cache/config as parameters, not singletons: `create_market_data_source(price_cache: PriceCache) -> MarketDataSource`

**Return Values:**
- Typed return values: `-> PriceUpdate`, `-> dict[str, float]`, `-> PriceUpdate | None`
- Return `None` rather than raising for "not found" cases: `def get(self, ticker: str) -> PriceUpdate | None:`
- Setter-style methods return `None`: `async def start(self, tickers: list[str]) -> None:`
- Computed properties return the value: `@property def direction(self) -> str:`

## Module Design

**Exports:**
- No `__all__` definitions currently; all public classes/functions are importable
- Private internals prefixed with underscore
- Public API clearly marked by lack of underscore prefix

**Barrel Files:**
- `__init__.py` in `app/market/` exports public API:
  ```python
  from .models import PriceUpdate
  from .cache import PriceCache
  from .interface import MarketDataSource, create_market_data_source
  ```
- Allows: `from app.market import PriceCache, PriceUpdate, MarketDataSource`

**Module Cohesion:**
- `app/market/` — all market data logic (cache, simulator, API client, streaming)
- Each module has a single responsibility:
  - `cache.py`: in-memory price storage
  - `simulator.py`: GBM price generation
  - `massive_client.py`: Polygon.io API integration
  - `interface.py`: abstract base class
  - `factory.py`: source creation logic
  - `stream.py`: SSE endpoint and generators
  - `models.py`: data structures (PriceUpdate)
  - `seed_prices.py`: configuration constants

## Dataclass Usage

**Immutable Models:**
- `PriceUpdate` is `@dataclass(frozen=True, slots=True)` — immutable, memory-efficient
- Computed properties derive values from immutable fields: `change`, `change_percent`, `direction`
- Serialization method: `to_dict()` for JSON conversion

**Thread-Safe State:**
- Mutable class state protected with `threading.Lock`:
  ```python
  class PriceCache:
      def __init__(self) -> None:
          self._prices: dict[str, PriceUpdate] = {}
          self._lock = Lock()
  ```
- All reads/writes to `_prices` are guarded: `with self._lock: ...`

## Async/Await Patterns

**Background Tasks:**
- Created with `asyncio.create_task()` with optional name:
  ```python
  self._task = asyncio.create_task(self._run_loop(), name="simulator-loop")
  ```
- Cleanup on stop: cancel, catch `CancelledError`, set to `None`

**Thread Integration:**
- Synchronous third-party APIs (e.g., Massive REST client) run in thread pool:
  ```python
  snapshots = await asyncio.to_thread(self._fetch_snapshots)
  ```

**Sleep and Timing:**
- Periodic tasks use `await asyncio.sleep(interval)` in a loop
- Zero delay in tests for responsiveness: `update_interval=0` or very small values

---

*Convention analysis: 2026-08-22*
