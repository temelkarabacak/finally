# Phase 1: Live Market Terminal - Pattern Map

**Mapped:** 2026-08-23
**Files analyzed:** 16
**Analogs found:** 11 / 16 (backend has strong analogs; frontend has none — empty directory, RESEARCH.md code examples are the reference instead)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `backend/app/main.py` | config/entrypoint | request-response (app wiring) | `backend/app/market/stream.py` (factory-function style) + `backend/app/market/__init__.py` (public API re-export) | role-match |
| `backend/app/db/connection.py` | service (DB access) | CRUD | `backend/app/market/cache.py` (stateful, lazily-constructed singleton pattern) | role-match |
| `backend/app/db/schema.sql` | config (DDL) | CRUD | none (no existing SQL in repo) | no analog |
| `backend/app/db/seed.py` | utility | batch/CRUD | `backend/app/market/seed_prices.py` (static seed data module) | exact |
| `backend/app/db/__init__.py` | config (barrel export) | — | `backend/app/market/__init__.py` | exact |
| `backend/app/watchlist/router.py` | controller/route | CRUD | `backend/app/market/stream.py` (`create_*_router(dep)` factory pattern) | exact |
| `backend/app/watchlist/__init__.py` | config (barrel export) | — | `backend/app/market/__init__.py` | exact |
| `backend/app/market/factory.py` (MODIFIED) | service | event-driven | itself (existing file, in-place edit) | exact |
| `backend/app/market/failover.py` (NEW) | service | event-driven | `backend/app/market/simulator.py` `SimulatorDataSource` (implements `MarketDataSource` ABC, delegates lifecycle to background task) | role-match |
| `backend/app/market/massive_client.py` (MODIFIED) | service | event-driven / polling | itself (existing file, in-place edit) | exact |
| `backend/tests/api/test_health.py` (NEW) | test | request-response | `backend/tests/market/test_stream.py` (FastAPI router test conventions) | role-match |
| `backend/tests/api/test_static_frontend.py` (NEW) | test | request-response | `backend/tests/market/test_stream.py` | role-match |
| `backend/tests/api/test_app_startup.py` (NEW) | test | event-driven (lifespan) | `backend/tests/market/test_factory.py` (env-var + `patch.dict` style) | role-match |
| `backend/tests/db/test_init.py`, `test_seed.py` (NEW) | test | CRUD | `backend/tests/market/test_cache.py` (stateful-object unit test style, not yet read but same conventions per `conftest.py`) | role-match |
| `backend/tests/watchlist/test_router.py` (NEW) | test | CRUD | `backend/tests/market/test_stream.py` (router unit test with fake request/cache) | role-match |
| `backend/tests/market/test_factory.py` (MODIFIED) | test | event-driven | itself — update 2 assertions | exact |
| `backend/tests/market/test_failover.py` (NEW) | test | event-driven | `backend/tests/market/test_factory.py` (`patch.dict(os.environ, ...)` + isinstance assertions) | role-match |
| `frontend/next.config.ts` | config | — | none (empty frontend/) — use RESEARCH.md Pattern 4 code example verbatim | no analog |
| `frontend/app/globals.css` | config (theme tokens) | — | none — use RESEARCH.md Tailwind v4 `@theme` guidance + PLAN.md §2 color values | no analog |
| `frontend/app/layout.tsx`, `page.tsx` | component | request-response (initial fetch) + streaming | none | no analog |
| `frontend/components/WatchlistPanel.tsx` | component | streaming | none | no analog |
| `frontend/components/Sparkline.tsx` | component | transform | none | no analog |
| `frontend/components/PriceChart.tsx` | component | streaming | none — use RESEARCH.md Pattern 5 (Lightweight Charts v5) verbatim | no analog |
| `frontend/components/ConnectionStatus.tsx` | component | event-driven | none | no analog |
| `frontend/hooks/usePriceStream.ts` | hook | streaming | none — `EventSource` + accumulation buffer, no existing analog; follow `backend/app/market/stream.py` SSE payload shape as the contract | no analog |

## Pattern Assignments

### `backend/app/main.py` (config/entrypoint, request-response)

**Analog:** `backend/app/market/__init__.py` (barrel/public API) + `backend/app/market/stream.py` (factory function signature style) + RESEARCH.md Pattern 1/2 (verified via FastAPI `inspect.signature`)

**Imports pattern** (mirrors `backend/app/market/__init__.py:11-15`):
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db import init_db
from app.market import PriceCache, create_market_data_source, create_stream_router
from app.watchlist import create_watchlist_router
```

**Core wiring pattern** (RESEARCH.md Pattern 1, grounded in `backend/app/market/factory.py:16` signature and `backend/app/market/stream.py:17` closure-capture requirement):
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    tickers = get_active_tickers()  # watchlist UNION open positions -- see Pitfall 3
    await source.start(tickers)
    yield
    await source.stop()

cache = PriceCache()  # module scope: single instance, threaded into both routers
source = create_market_data_source(cache)
app = FastAPI(lifespan=lifespan)
app.include_router(create_stream_router(cache))
app.include_router(create_watchlist_router(db_conn, source))
app.frontend("/", directory="static", fallback="index.html")
```

**Logging pattern** (module-level logger, matches every existing `app/market/*.py` file, e.g. `factory.py:13`):
```python
logger = logging.getLogger(__name__)
```

**Critical constraint (Pitfall 2, verified this session):** `create_stream_router(price_cache)` closes over the `price_cache` argument at call time (`stream.py:17-24`) — construct exactly one `PriceCache()` before creating any router, and pass that same instance to `create_market_data_source`, `create_stream_router`, and the new watchlist router. Do not construct a second `PriceCache()` anywhere.

---

### `backend/app/db/connection.py`, `schema.sql`, `seed.py`, `__init__.py` (service/CRUD)

**Analog for `seed.py`:** `backend/app/market/seed_prices.py:1-15` — static seed-data module, plain module-level constants, no class needed:
```python
"""Seed prices and per-ticker parameters for the market simulator."""

SEED_PRICES: dict[str, float] = {
    "AAPL": 190.00,
    ...
}
```
Mirror this shape for `seed.py`'s default watchlist tickers (same 10 symbols, same order, per PLAN.md §7) and the default `users_profile` row.

**Analog for `connection.py`:** `backend/app/market/cache.py:11-21` — module owns one stateful object with clear lifecycle methods (`__init__`, lazy-guarded mutation). Follow the same "no premature abstraction" style: a plain function `init_db(db_path=...)` plus `get_db()` returning a connection, not a class hierarchy.

**RESEARCH.md code example to follow verbatim** (SQLite lazy init, stdlib, WAL mode — no existing analog since this is stdlib-only, no ORM in the repo):
```python
import sqlite3
from pathlib import Path

def init_db(db_path: str = "db/finally.db") -> None:
    exists = Path(db_path).exists()
    conn = sqlite3.connect(db_path, autocommit=True)
    conn.execute("PRAGMA journal_mode=WAL")
    if not exists or _tables_missing(conn):
        conn.executescript(SCHEMA_SQL)
        _seed_defaults(conn)
    conn.close()
```

**Barrel export pattern** (`backend/app/market/__init__.py:11-23`, exact analog for `backend/app/db/__init__.py`):
```python
"""<subsystem> subsystem for FinAlly.

Public API:
    <ThingA> - <one-line description>
    ...
"""

from .connection import init_db, get_db, get_active_tickers
from .seed import seed_defaults

__all__ = ["init_db", "get_db", "get_active_tickers", "seed_defaults"]
```

**Active-ticker-set query (Pitfall 3, non-negotiable per CONTEXT.md/ROADMAP.md rationale):** write the real UNION now even though `positions` is always empty this phase:
```sql
SELECT ticker FROM watchlist WHERE user_id = ?
UNION
SELECT ticker FROM positions WHERE user_id = ? AND quantity > 0
```

**SQL injection avoidance (ASVS V5, per RESEARCH.md Security Domain):** always use `?` parameterized queries for ticker values, never string-format into SQL, even though `normalize_ticker()` (`backend/app/market/interface.py:8-14`) already restricts input shape.

---

### `backend/app/watchlist/router.py` (controller, CRUD)

**Analog:** `backend/app/market/stream.py:17-48` — the `create_*_router(dependency) -> APIRouter` factory pattern, returning a fresh `APIRouter` per call (safe for tests, no shared-instance route pile-up):

**Imports pattern** (mirrors `stream.py:1-15`):
```python
from __future__ import annotations
import logging
from fastapi import APIRouter
from app.market.interface import normalize_ticker
from app.market.cache import PriceCache

logger = logging.getLogger(__name__)
```

**Core factory + route pattern** (mirrors `stream.py:17-48`):
```python
def create_watchlist_router(db_conn, market_source) -> APIRouter:
    router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

    @router.get("")
    async def get_watchlist():
        ...

    @router.post("")
    async def add_ticker(body: AddTickerRequest):
        ticker = normalize_ticker(body.ticker)
        # write to db, then:
        await market_source.add_ticker(ticker)
        ...

    @router.delete("/{ticker}")
    async def remove_ticker(ticker: str):
        ticker = normalize_ticker(ticker)
        # only remove from market source if no open position references it
        ...

    return router
```

**Reuse `normalize_ticker`** (`backend/app/market/interface.py:8-14`) for all ticker input — both the DB writes and the calls into `market_source.add_ticker()`/`remove_ticker()` must use the identical normalized form the cache is keyed by.

**Error handling pattern (ASVS V7):** no existing controller-layer error pattern exists yet in this codebase (market module has no HTTP-facing error paths beyond the SSE stream). Use FastAPI's standard `HTTPException(status_code=409, detail=...)` for duplicate-ticker-add and `HTTPException(status_code=404, ...)` for delete-of-unknown-ticker — structured JSON, no stack traces, matching RESEARCH.md's ASVS V7 guidance.

---

### `backend/app/market/factory.py` (MODIFIED — wrap Massive branch)

**Analog:** itself, current state (`factory.py:16-31`, read this session — reproduced above in full). Modify only the `if api_key:` branch:
```python
def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if api_key:
        massive = MassiveDataSource(api_key=api_key, price_cache=price_cache)
        return FailoverMarketDataSource(primary=massive, price_cache=price_cache)
    return SimulatorDataSource(price_cache=price_cache)
```
Keep the existing `logger.info(...)` calls and one-directional import style (`factory → simulator/massive_client/failover; all → interface/cache/models`).

---

### `backend/app/market/failover.py` (NEW, service, event-driven)

**Analog:** `backend/app/market/simulator.py` `SimulatorDataSource` (lines 200-260) — implements the full `MarketDataSource` ABC (`backend/app/market/interface.py:17-67`), delegates lifecycle to an inner object, same `logger.info` conventions on start/stop/add/remove.

**Core delegation pattern** (new logic, grounded in RESEARCH.md Pattern 3 + the ABC contract in `interface.py`):
```python
class FailoverMarketDataSource(MarketDataSource):
    def __init__(self, primary: MassiveDataSource, price_cache: PriceCache) -> None:
        self._active: MarketDataSource = primary
        self._cache = price_cache
        self._failed_over = False

    async def start(self, tickers: list[str]) -> None:
        await self._active.start(tickers)

    async def _on_permanent_failure(self) -> None:
        if self._failed_over:
            return
        self._failed_over = True
        tickers = self._active.get_tickers()
        await self._active.stop()
        simulator = SimulatorDataSource(self._cache)
        await simulator.start(tickers)
        self._active = simulator
        logger.error("Massive permanently failed; switched to simulator with %d tickers", len(tickers))

    async def stop(self) -> None: await self._active.stop()
    async def add_ticker(self, ticker: str) -> None: await self._active.add_ticker(ticker)
    async def remove_ticker(self, ticker: str) -> None: await self._active.remove_ticker(ticker)
    def get_tickers(self) -> list[str]: return self._active.get_tickers()
```
Wire `massive._on_permanent_failure = self._on_permanent_failure` (or pass as constructor callback) after constructing `MassiveDataSource`, per RESEARCH.md Pattern 3.

---

### `backend/app/market/massive_client.py` (MODIFIED — permanent-failure guard)

**Analog:** itself, current state (`massive_client.py:83-121`, verbatim quoted in RESEARCH.md and reproduced above). Exact diff shape:
- Add `self._permanently_failed = False` and `on_permanent_failure: Callable | None = None` param in `__init__` (line ~28-39)
- Guard top of `_poll_once()` (line 89): `if self._permanently_failed: return`
- In the `except Exception as e:` block (line 118-121): set `self._permanently_failed = True`, log at `error` level ("permanent failover"), call `if self._on_permanent_failure: await self._on_permanent_failure()`
- In `_poll_loop()` (line 83-87): after `await self._poll_once()`, `if self._permanently_failed: break`

**Test-suite impact (Pitfall 4, must fix in the same task):** `backend/tests/market/test_factory.py:42-49,71-79` (`test_creates_massive_when_api_key_set`, `test_massive_receives_cache`) currently assert `isinstance(source, MassiveDataSource)` — change to `isinstance(source, FailoverMarketDataSource)` and reach the inner Massive instance via a new accessor (e.g. `source._active`).

---

### Backend test files (NEW/MODIFIED)

**Analog for router/service tests:** `backend/tests/market/test_stream.py:1-31` — `FakeRequest`-style minimal stand-ins over real FastAPI request objects, `pytest.mark.asyncio` class-based grouping, one `Test<Subject>` class per module.

**Analog for factory/env-var tests:** `backend/tests/market/test_factory.py:1-80` — `with patch.dict(os.environ, {...}, clear=True):` pattern for isolating env-var-driven branches; plain `assert isinstance(...)` and attribute-access assertions (`source._api_key`, `source._cache`).

**conftest.py note:** `backend/tests/conftest.py` is currently a docstring-only stub (1 line) — RESEARCH.md's Wave 0 Gaps calls for adding shared fixtures here (temp SQLite path, seeded `PriceCache`, `FastAPI` TestClient with lifespan). No existing fixture pattern to copy; build from scratch following pytest's standard `@pytest.fixture` conventions, matching the module-level `logger = logging.getLogger(__name__)` and docstring style used throughout `app/market/`.

---

### Frontend files (all NEW — no codebase analogs, `frontend/` is empty)

No existing frontend code exists to pattern-match against. Use RESEARCH.md's Code Examples section verbatim as the primary reference:
- `frontend/next.config.ts` — RESEARCH.md Pattern 4 (`output: 'export'`, `images.unoptimized: true`)
- `frontend/components/PriceChart.tsx` — RESEARCH.md Pattern 5 (Lightweight Charts v5 `createChart` + `addSeries(LineSeries, opts)` inside `useEffect`, `'use client'` directive, `chart.remove()` cleanup)
- `frontend/app/globals.css` — Tailwind v4 CSS-first `@theme` tokens; use PLAN.md §2 exact hex values: `--color-bg: #0d1117` (or `#1a1a2e`), `--color-accent-yellow: #ecad0a`, `--color-accent-blue: #209dd7`, `--color-accent-purple: #753991` (submit buttons)
- `frontend/hooks/usePriceStream.ts` — native `EventSource('/api/stream/prices')`, no library; parse the exact SSE payload shape emitted by `backend/app/market/stream.py:81` (`{ticker: {ticker, price, previous_price, timestamp, change, change_percent, direction}}`) — this is the wire-format contract, verified against `PriceUpdate.to_dict()` in `backend/app/market/models.py:39-49`
- `frontend/components/Sparkline.tsx` — plain inline SVG polyline per CONTEXT.md decision; no charting library instantiated per row

## Shared Patterns

### Module-level logger + docstrings
**Source:** every file in `backend/app/market/` (e.g. `factory.py:13`, `stream.py:15`, `simulator.py:25`)
**Apply to:** all new backend modules (`db/`, `watchlist/`, `failover.py`)
```python
logger = logging.getLogger(__name__)
```
Every module opens with a one-line docstring describing its purpose (e.g. `"""Factory for creating market data sources."""`).

### `from __future__ import annotations`
**Source:** every file in `backend/app/market/`
**Apply to:** all new backend `.py` files (consistent with existing convention, enables forward-reference type hints without quotes)

### Ticker normalization
**Source:** `backend/app/market/interface.py:8-14` `normalize_ticker(ticker: str) -> str`
**Apply to:** `backend/app/db/` (watchlist writes), `backend/app/watchlist/router.py` (all request bodies), any place a ticker string crosses a boundary
```python
def normalize_ticker(ticker: str) -> str:
    return ticker.upper().strip()
```
Both the DB layer and the market-data-source layer must use this identically or the `PriceCache` and `watchlist` table will diverge on casing/whitespace.

### Factory-function-returns-router pattern
**Source:** `backend/app/market/stream.py:17-48` `create_stream_router(price_cache) -> APIRouter`
**Apply to:** `backend/app/watchlist/router.py` `create_watchlist_router(db, market_source) -> APIRouter`
Returns a fresh `APIRouter` per call — no module-level shared router instance, so tests can call the factory repeatedly without route accumulation.

### Barrel `__init__.py` with docstring-listed public API
**Source:** `backend/app/market/__init__.py:1-23`
**Apply to:** `backend/app/db/__init__.py`, `backend/app/watchlist/__init__.py`
```python
"""<Subsystem> for FinAlly.

Public API:
    <name> - <description>
"""
from .module import thing
__all__ = ["thing"]
```

### `patch.dict(os.environ, ..., clear=True)` for env-var-driven tests
**Source:** `backend/tests/market/test_factory.py:19,28,37,46,55,65,75`
**Apply to:** `backend/tests/market/test_failover.py`, any test touching `MASSIVE_API_KEY`

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `backend/app/db/schema.sql` | config (DDL) | CRUD | No existing SQL/DDL anywhere in the repo — first database code; follow PLAN.md §7 schema definitions directly |
| `frontend/*` (all files) | component/hook/config | streaming/transform | `frontend/` is currently empty; RESEARCH.md's verified Code Examples (Patterns 4 & 5) are the authoritative reference in place of a codebase analog |

## Metadata

**Analog search scope:** `backend/app/`, `backend/tests/`, `backend/pyproject.toml`; `frontend/` confirmed empty
**Files scanned:** 8 source modules (`app/market/*.py`), 7 test modules (`tests/market/*.py`, `tests/conftest.py`), `pyproject.toml`
**Pattern extraction date:** 2026-08-23
