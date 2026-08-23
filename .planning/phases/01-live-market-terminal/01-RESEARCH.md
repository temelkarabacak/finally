# Phase 1: Live Market Terminal - Research

**Researched:** 2026-08-23
**Domain:** FastAPI app wiring over an existing async market-data subsystem, SQLite lazy-init without an ORM, Next.js 15+/16 static export with Tailwind v4, TradingView Lightweight Charts, and a concrete fix for permanent Massive-API failover.
**Confidence:** HIGH

## Summary

This phase turns a fully-built, fully-tested market-data subsystem (`backend/app/market/`) plus an empty `frontend/` into a running, browsable application. The backend side is almost entirely *wiring*, not new algorithm design: FastAPI's current `lifespan` context manager starts the existing `create_market_data_source()` / `PriceCache` pair, a new `app/db/` module lazily creates and seeds a 6-table SQLite schema using the stdlib `sqlite3` module (no ORM, no new dependency), and a new `app/watchlist/` router does CRUD against that schema while pushing ticker adds/removes into the running market-data source. The frontend side scaffolds a fresh Next.js static export project (`output: 'export'`) with Tailwind v4's CSS-first config and TradingView's `lightweight-charts` for the per-ticker chart, consuming the existing `/api/stream/prices` SSE endpoint via the native `EventSource` API.

The one piece of genuinely new logic is PORT-05 (Massive permanent failover): `massive_client.py`'s `_poll_once()` currently logs and silently retries forever on any exception — this must become a one-way trip to the simulator. The verified fix is a two-part change: (1) a small, self-contained guard inside `massive_client.py` that flags permanent failure and stops the poll loop from scheduling further Massive calls, plus an optional failure callback; (2) a new thin wrapper (`FailoverMarketDataSource`), constructed by `factory.py` only when `MASSIVE_API_KEY` is set, that owns swapping the "active" source to a freshly-started `SimulatorDataSource` when the callback fires. This keeps both existing, 100%-tested modules (`simulator.py`, `massive_client.py`) free of cross-imports and isolates the new orchestration logic in one small, independently testable unit.

A significant finding that changes the plan from what stale training data would suggest: FastAPI (installed and registry-verified at **0.141.1**, feature added in **0.138.0**, 2026-06-20) now ships a built-in `app.frontend(path, *, directory, fallback="auto")` method that replaces the older hand-rolled `StaticFiles` + catch-all-route pattern for serving a static SPA build with index.html fallback — this is the correct FOUND-03 implementation, not a manually mounted `StaticFiles`.

**Primary recommendation:** Wire the FastAPI app with `lifespan` + the existing market factory/cache/stream-router; use stdlib `sqlite3` (no new backend dependency) with `PRAGMA journal_mode=WAL` for the DB layer; use `app.frontend()` (FastAPI ≥0.138.0) to serve the Next.js static export; scaffold the frontend with Next.js 16 App Router + TypeScript + Tailwind v4 + `lightweight-charts`; fix PORT-05 with a small in-`massive_client.py` permanent-failure guard plus a new `FailoverMarketDataSource` wrapper built in `factory.py`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Market data generation/polling (simulator, Massive) | API / Backend | — | Already implemented in `app/market/`; background `asyncio.Task`, no client involvement |
| Massive permanent failover orchestration | API / Backend | — | Pure server-side state machine; client never sees the swap, only continued price data |
| SQLite schema, lazy-init, seed data | Database / Storage | API / Backend (init trigger) | Schema/DDL owns no logic beyond storage; FastAPI lifespan triggers init once |
| Watchlist CRUD (`/api/watchlist`) | API / Backend | Database / Storage | Router validates input and normalizes tickers; DB layer persists; both mediate active-ticker-set computation |
| SSE price stream (`/api/stream/prices`) | API / Backend | Browser / Client (consumer) | Already implemented; server pushes, `EventSource` is a passive consumer |
| Static frontend serving | API / Backend (via `app.frontend()`) | — | No SSR/server tier exists — `output: 'export'` produces pre-rendered HTML+JS served as static files |
| Watchlist grid, price flash, sparkline | Browser / Client | — | Client-side state accumulated from SSE since page load; no server involvement beyond initial fetch |
| Per-ticker chart (Lightweight Charts) | Browser / Client | — | Canvas rendering is inherently client-side; historical data seeded from accumulated SSE ticks |
| Dark theme tokens (Tailwind config) | Browser / Client (build-time) | — | Tailwind v4 CSS-first `@theme` tokens compiled at build time into static CSS |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.141.1 installed; require `>=0.138.0` | HTTP API, SSE (existing), static frontend serving | `[VERIFIED: uv pip install + inspect.signature(app.frontend), this session]` `app.frontend()` exists with signature `frontend(path, *, directory, fallback='auto', check_dir='auto')` |
| Uvicorn | `>=0.32.0` (existing pin) | ASGI server | Already in `pyproject.toml:9` `[VERIFIED: backend/pyproject.toml:9]` `"uvicorn[standard]>=0.32.0"` |
| Python stdlib `sqlite3` | Python 3.12+/3.13 stdlib | DB access, no ORM | `[VERIFIED: this session]` `sqlite3.Connection.autocommit` attribute confirmed present (`hasattr(conn, 'autocommit')` → `True`) on the installed interpreter; avoids a new dependency, matches existing `asyncio.to_thread()` convention already used for the synchronous Massive REST client (`backend/app/market/massive_client.py:97`) |
| Next.js | 16.3.2 (registry latest) | Frontend framework, static export | `[VERIFIED: npm view next version]`; requires Node `>=20.9.0` `[VERIFIED: npm view next engines]` — installed Node is v24.16.0, satisfies this |
| React / react-dom | 19.2.8 | UI library (Next.js peer dep) | `[VERIFIED: npm view react version / npm view next@16.3.2 peerDependencies]` — Next 16 accepts `^19.0.0` |
| TypeScript | latest registry `7.0.2` | Type safety | `[VERIFIED: npm view typescript version]`. Note: this is TypeScript 7 (the native/Go-ported compiler line) — a major-version jump from the 5.x most training data assumes; confirm this is intentional before locking the version (see Assumptions Log) |
| Tailwind CSS | 4.3.3 | Styling, dark theme tokens | `[VERIFIED: npm view tailwindcss version]`. v4 uses CSS-first config (`@theme` in globals.css) — no `tailwind.config.js` content globs required by default |
| `@tailwindcss/postcss` + `postcss` | 4.x / registry-current | Tailwind v4 PostCSS plugin | `[CITED: tailwindcss.com/docs/installation/framework-guides/nextjs]` — v4 install requires this package in addition to `tailwindcss` itself, unlike v3 |
| `lightweight-charts` | 5.2.1 | Per-ticker price chart (UI-03) | `[VERIFIED: npm view lightweight-charts version]`; chosen in CONTEXT.md; v5 API uses `chart.addSeries(LineSeries, opts)` rather than the v3/v4 `chart.addLineSeries()` `[CITED: github.com/tradingview/lightweight-charts README + react tutorial]` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `@types/node`, `@types/react`, `@types/react-dom` | registry-current | TypeScript types for Next.js dev | Always, dev dependency only |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib `sqlite3` + `asyncio.to_thread` | `aiosqlite` | True async driver avoids the thread-pool hop, but adds a dependency for a write pattern (rare watchlist CRUD + one-time schema init) that doesn't need it; stdlib matches the existing to-thread convention already established for the Massive REST client |
| `app.frontend()` (FastAPI ≥0.138.0) | Manual `StaticFiles` mount + catch-all route | The manual pattern is what most existing tutorials/training data show, but `app.frontend()` is now first-class, has built-in SPA fallback semantics (`index.html`, `404.html`, `auto`), and needs no custom catch-all route — strictly less code for the same result |
| `lightweight-charts` v5 `addSeries(LineSeries, ...)` | v4-style `addLineSeries()` | v4 API is what most tutorials still show but is superseded in v5; using the old API against the v5 package installed via `npm install lightweight-charts` will fail at runtime |
| Inline SVG sparkline (per CONTEXT.md decision) | A full charting library instantiated per row | Already decided in CONTEXT.md — no charting library overhead for 10+ simultaneously-rendered sparklines |

**Installation:**
```bash
# Backend: no new dependency needed for the DB layer.
# Bump the existing FastAPI pin in backend/pyproject.toml:
#   "fastapi>=0.115.0" -> "fastapi>=0.138.0"
cd backend && uv sync --extra dev

# Frontend (new project):
npx create-next-app@latest frontend --typescript --tailwind --app --no-src-dir --import-alias "@/*"
cd frontend && npm install lightweight-charts
```

**Version verification:** All frontend package versions above were confirmed via `npm view <pkg> version` against the live npm registry this session (see Package Legitimacy Audit for full signal detail). FastAPI's installed/available version and the exact `app.frontend()` signature were confirmed by installing it into a throwaway `uv venv` and calling `inspect.signature()` directly — not from training data.

## Package Legitimacy Audit

> Frontend packages are new installs (empty `frontend/`). Backend packages (`fastapi`, `uvicorn`, `numpy`, `massive`) are pre-existing dependencies already in `backend/pyproject.toml` — not gated here since they are not new installs.

| Package | Registry | Published | Downloads/wk | Source Repo | Verdict | Disposition |
|---------|----------|-----------|---------------|--------------|---------|-------------|
| `next` | npm | 2026-08-21 | 53.1M | github.com/vercel/next.js | SUS ("too-new") | Approved — false-positive; canonical package, huge download count, official repo. Routine release cadence, not a risk signal. |
| `react` | npm | 2026-07-21 | 170.2M | github.com/react/react | OK | Approved |
| `react-dom` | npm | 2026-07-21 | 159.7M | github.com/react/react | OK | Approved |
| `typescript` | npm | 2026-07-08 | 269.3M | github.com/microsoft/TypeScript | OK | Approved (note major-version jump to 7.x — see Assumptions Log) |
| `tailwindcss` | npm | 2026-07-16 | 125.2M | github.com/tailwindlabs/tailwindcss | OK | Approved |
| `@tailwindcss/postcss` | npm | 2026-07-16 | 33.8M | github.com/tailwindlabs/tailwindcss | OK | Approved |
| `postcss` | npm | 2026-08-06 | 274.3M | github.com/postcss/postcss | SUS ("too-new") | Approved — false-positive; foundational, near-ubiquitous package |
| `lightweight-charts` | npm | 2026-08-12 | 905K | github.com/tradingview/lightweight-charts | SUS ("too-new") | Approved — official TradingView repo, this is the CONTEXT.md-decided library |
| `@types/node` | npm | 2026-08-07 | 416.0M | github.com/DefinitelyTyped/DefinitelyTyped | SUS ("too-new") | Approved — DefinitelyTyped canonical types package |
| `@types/react` | npm | 2026-07-30 | 159.1M | github.com/DefinitelyTyped/DefinitelyTyped | SUS ("too-new") | Approved — same as above |
| `@types/react-dom` | npm | 2026-07-30 | 132.2M | github.com/DefinitelyTyped/DefinitelyTyped | SUS ("too-new") | Approved — same as above |

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** `next`, `postcss`, `lightweight-charts`, `@types/node`, `@types/react`, `@types/react-dom` — all flagged solely on the legitimacy checker's "too-new" heuristic (recent publish timestamp), which for actively-maintained, extremely high-download, officially-repo'd packages is a routine patch-release artifact, not a hallucination/squatting signal. Root cause: the heuristic can't distinguish "freshly hallucinated" from "actively maintained, ships often." **Recommendation to planner:** a single lightweight `checkpoint:human-verify` before `npm install` in the frontend scaffold task is sufficient (verify the installed versions match the table above); do not gate each package individually.

## Architecture Patterns

### System Architecture Diagram

```
Browser (EventSource, fetch)
   │
   │  GET /                      GET /api/watchlist, POST/DELETE
   │  (static HTML/JS/CSS)       GET /api/stream/prices (SSE)
   ▼                                  ▼
┌─────────────────────────────────────────────────────────┐
│ FastAPI app (uvicorn, single process, port 8000)         │
│                                                           │
│  lifespan():                                             │
│   1. db.init_db()          -- lazy schema create + seed  │
│   2. create_market_data_source(cache) -- existing factory│
│   3. active_tickers = watchlist ∪ open positions         │
│   4. await source.start(active_tickers)                  │
│   5. yield  (app runs)                                   │
│   6. await source.stop()   -- on shutdown                │
│                                                           │
│  Routers:                                                │
│   create_stream_router(cache)   -- existing, SSE          │
│   create_watchlist_router(db, source) -- NEW               │
│   app.frontend("/", directory="static", fallback="auto")  │
│                                                           │
│  On watchlist add/remove:                                │
│   db writes row  ──▶  recompute active set  ──▶  source.add_ticker()/remove_ticker()
└─────────────────────┬─────────────────────────────────────┘
                      │
        ┌─────────────┴──────────────┐
        ▼                            ▼
  PriceCache (in-memory)      SQLite (db/finally.db, WAL mode)
  written by source loop      users_profile, watchlist, positions,
  read by SSE + watchlist      trades, portfolio_snapshots, chat_messages
        ▲
        │ MASSIVE_API_KEY set?
        ├─ yes → FailoverMarketDataSource(MassiveDataSource) ─┐
        │                                                      │ on permanent failure:
        │                                                      │ stop Massive, start Simulator
        └─ no  → SimulatorDataSource ◀────────────────────────┘ with same tickers
```

### Recommended Project Structure
```
backend/app/
├── main.py              # NEW: FastAPI app factory + lifespan
├── db/
│   ├── __init__.py
│   ├── schema.sql       # 6-table DDL (users_profile, watchlist, positions,
│   │                    #   trades, portfolio_snapshots, chat_messages)
│   ├── seed.py          # default user + 10 watchlist tickers
│   └── connection.py    # get_db() -> sqlite3.Connection, lazy init check
├── watchlist/
│   ├── __init__.py
│   └── router.py        # create_watchlist_router(db, market_source)
└── market/
    ├── factory.py        # MODIFIED: wrap Massive in FailoverMarketDataSource
    ├── failover.py        # NEW: FailoverMarketDataSource
    └── massive_client.py  # MODIFIED: permanent-failure guard + callback

frontend/
├── next.config.ts        # output: 'export', images.unoptimized: true
├── postcss.config.mjs     # @tailwindcss/postcss plugin
├── app/
│   ├── globals.css        # @import "tailwindcss"; @theme { --color-... }
│   ├── layout.tsx
│   └── page.tsx            # composes WatchlistPanel + ChartPanel
└── components/
    ├── WatchlistPanel.tsx   # grid + inline add/remove + sparklines
    ├── Sparkline.tsx        # inline SVG polyline, no charting lib
    ├── PriceChart.tsx       # Lightweight Charts wrapper (ref-based cleanup)
    ├── ConnectionStatus.tsx # EventSource readyState -> dot color
    └── usePriceStream.ts    # hook wrapping EventSource + accumulation buffer
```

### Pattern 1: FastAPI lifespan wiring existing market subsystem
**What:** Use `@asynccontextmanager` lifespan to start/stop the market data source and DB init, matching the existing `create_market_data_source()` / `PriceCache` contract exactly.
**When to use:** App startup/shutdown — this is the only correct place per FastAPI's current recommended pattern (separate `@app.on_event("startup")` is deprecated).
**Example:**
```python
# Source: https://fastapi.tiangolo.com/advanced/events (Context7, this session)
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db import init_db, get_active_tickers
from app.market import PriceCache, create_market_data_source, create_stream_router
from app.watchlist import create_watchlist_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    cache = PriceCache()
    source = create_market_data_source(cache)
    tickers = get_active_tickers()  # watchlist UNION open positions
    await source.start(tickers)
    app.state.cache = cache
    app.state.source = source
    yield
    await source.stop()

app = FastAPI(lifespan=lifespan)
app.include_router(create_stream_router(app.state.cache if hasattr(app.state, "cache") else None))
# Router mounting must happen after app.state is populated by lifespan in practice;
# use a factory function taking app.state, or defer router creation to inside lifespan.
app.frontend("/", directory="static", fallback="auto")
```
**Caveat verified this session:** `create_stream_router(price_cache)` requires the cache instance at router-creation time (it captures `price_cache` in a closure — see `backend/app/market/stream.py:17-24`), so the router must be created either after `PriceCache()` exists (module-level, before `app.include_router`) or inside `lifespan` with `app.include_router` called there too (FastAPI supports router inclusion at runtime). The straightforward approach: construct `PriceCache()` before `FastAPI(lifespan=...)`, pass it into both the lifespan closure and `create_stream_router()` at module scope.

### Pattern 2: Serving the static export with `app.frontend()`
**What:** Replace the "mount StaticFiles + catch-all route" pattern with the current built-in method.
**When to use:** FOUND-03 (serve Next.js static export for all non-`/api/*` routes).
**Example:**
```python
# Source: https://fastapi.tiangolo.com/tutorial/frontend (Context7 + WebFetch, this session)
# Signature verified via inspect.signature() on installed fastapi==0.141.1:
#   frontend(path, *, directory, fallback='auto', check_dir='auto') -> None
app.frontend("/", directory="static", fallback="index.html")
```
API routes registered before this call take precedence; the frontend fallback is only checked when no API route matches. `directory` should point at the Next.js `out/` export copied into the backend image/working tree at build time (Dockerfile stage in Phase 4; for local dev, copy `frontend/out` to wherever `directory` points, e.g. `backend/static/`).

### Pattern 3: Massive permanent failover (PORT-05)
**What:** A self-contained "stop polling forever" guard inside `massive_client.py`, plus a thin `FailoverMarketDataSource` wrapper (new module) that swaps to the simulator when notified.
**When to use:** PORT-05 — this is the one piece of genuinely new backend logic in this phase.
**Design (recommended over directly importing `SimulatorDataSource` into `massive_client.py`):** keeping `massive_client.py` and `simulator.py` mutually unaware preserves the existing one-directional import graph documented in `ARCHITECTURE.md` (`factory → simulator/massive_client; both → interface/cache/models`) and keeps both fully-tested modules untouched in their core logic.

**Step 1 — guard inside `massive_client.py`** (verbatim current code being modified, read this session):
```python
# backend/app/market/massive_client.py:83-121 (current, unmodified):
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
            # ... (unchanged processing loop) ...
        except Exception as e:
            logger.error("Massive poll failed: %s", e)
            # Don't re-raise -- the loop will retry on the next interval.
```
Recommended change: add `self._permanently_failed = False` and an optional `on_permanent_failure` callback param in `__init__`; guard the top of `_poll_once()` with `if self._permanently_failed: return`; in the `except` block set the flag, log at `error` level that failover is occurring, and (if set) schedule the callback; in `_poll_loop()`, `break` after `_poll_once()` returns if `self._permanently_failed` is now `True`, so the task ends and no further Massive calls are ever made.

**Step 2 — new wrapper, `factory.py` constructs it:**
```python
# backend/app/market/factory.py (current, read this session):
#   api_key = os.environ.get("MASSIVE_API_KEY", "").strip()
#   if api_key: return MassiveDataSource(api_key=api_key, price_cache=price_cache)
#   else: return SimulatorDataSource(price_cache=price_cache)
#
# Recommended: wrap the Massive branch only.
def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if api_key:
        massive = MassiveDataSource(api_key=api_key, price_cache=price_cache)
        return FailoverMarketDataSource(primary=massive, price_cache=price_cache)
    return SimulatorDataSource(price_cache=price_cache)
```
`FailoverMarketDataSource` implements the same `MarketDataSource` ABC, delegates all four lifecycle methods to whichever source is currently "active," and on the callback firing: captures `self._active.get_tickers()`, calls `await self._active.stop()`, constructs and starts a fresh `SimulatorDataSource(price_cache)` with those tickers, and reassigns `self._active`. Idempotency guard (`self._failed_over` bool) prevents double-failover if the callback somehow fires twice.

**Known test-suite impact (verified by reading `backend/tests/market/test_factory.py` this session):** `test_creates_massive_when_api_key_set` and `test_massive_receives_cache` currently assert `isinstance(source, MassiveDataSource)` (lines 42-49, 71-79). Once wrapped, `create_market_data_source()` returns a `FailoverMarketDataSource` in the Massive-key branch — these two assertions must change to check `isinstance(source, FailoverMarketDataSource)` (and a new accessor, e.g. `source._active` or `.primary`, to reach the inner `MassiveDataSource` for the remaining assertions like `source._api_key`). Flag this explicitly as a required test update, not a regression to silently work around.

### Pattern 4: Next.js static export + FastAPI, no CORS
**What:** `output: 'export'` in `next.config.ts`; frontend fetches same-origin `/api/*` and `/api/stream/prices`.
**Example:**
```typescript
// Source: https://github.com/vercel/next.js next.config.ts docs (Context7, this session)
import type { NextConfig } from 'next'
const nextConfig: NextConfig = {
  output: 'export',
  images: { unoptimized: true }, // required with output:'export' -- no server Image Optimization API
}
export default nextConfig
```
**Verified constraints (Context7, this session):** with `output: 'export'`, `headers`/`rewrites`/`redirects` config keys are ignored (warned), `i18n` throws, Server Actions and Intercepting Routes are build-time errors, and `dynamic = "force-dynamic"` route handlers throw. None of these are needed for this phase (no server actions, no i18n) — but do not reach for them later without first removing `output: 'export'`.

### Pattern 5: Lightweight Charts in a React client component (v5 API)
**What:** `createChart` + `addSeries(LineSeries, opts)` inside a `useEffect`, with cleanup via `chart.remove()`.
**Example:**
```tsx
// Source: github.com/tradingview/lightweight-charts README + react tutorial (Context7, this session)
'use client'
import { useEffect, useRef } from 'react'
import { createChart, LineSeries, type IChartApi } from 'lightweight-charts'

export function PriceChart({ data }: { data: { time: number; value: number }[] }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const chart = createChart(containerRef.current, { width: 600, height: 300 })
    const series = chart.addSeries(LineSeries, { color: '#209dd7' })
    series.setData(data)
    chartRef.current = chart
    return () => {
      chart.remove()
      chartRef.current = null
    }
  }, [])

  return <div ref={containerRef} />
}
```
Must be a Client Component (`'use client'`) — chart creation touches the DOM directly and cannot run during static export's build-time prerender.

### Anti-Patterns to Avoid
- **Reimplementing `MarketDataSource` logic in the DB or watchlist layer:** all price reads must go through `PriceCache`; the watchlist router only decides *which tickers* are tracked (via `add_ticker`/`remove_ticker`), never generates or fetches prices itself.
- **Catching Massive failures only at `_poll_once()` without a loop-level stop:** logging alone (current behavior) is not failover — the loop must actually stop calling Massive, or PORT-05 is unmet even if a callback fires once.
- **Mounting `StaticFiles` manually when `app.frontend()` is available:** duplicates functionality FastAPI now provides natively (SPA fallback, dotted-path fix, background-task/dependency support) — see FastAPI release notes 0.138.0-0.141.x, `[VERIFIED: raw release-notes.md, this session]`.
- **Using `output: 'export'` with any App Router feature needing a request-time server** (Server Actions, dynamic route handlers, `i18n`) — build-time errors, not warnings, in current Next.js.
- **Building a full charting-library instance per watchlist row for sparklines:** already flagged in CONTEXT.md as a discretion call resolved in favor of a plain inline SVG polyline.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Static SPA fallback serving | Custom catch-all route + manual `FileResponse` | `app.frontend(path, directory=..., fallback="auto")` | Built into FastAPI ≥0.138.0; handles dotted paths, `Accept` header sniffing, and 404 vs fallback semantics correctly already |
| SSE reconnection | Custom retry/backoff JS | Native `EventSource` (`retry: 1000` directive already sent by `stream.py:62`) | Browsers implement automatic reconnection for `EventSource`; the server already sends the retry directive |
| Chart rendering/interaction (pan, zoom, crosshair, time axis) | Canvas drawing code | `lightweight-charts` | Purpose-built financial time-series rendering; CONTEXT.md already decided this |
| Correlated multi-asset price simulation | New GBM/Cholesky code | Existing `GBMSimulator` in `simulator.py` (reuse as-is) | Already implemented, tested, and explicitly marked "do not redesign" in phase notes |
| SQLite concurrent-write serialization | Custom async lock/queue | `PRAGMA journal_mode=WAL` (SQLite's own reader/writer concurrency model) | Standard, zero-code solution for "one writer, many readers" that this phase's write volume (rare watchlist CRUD + startup seed) doesn't even stress yet — cheap to enable now ahead of Phase 2's heavier write load |

**Key insight:** Every piece of genuinely custom logic in this phase is either (a) wiring together already-tested modules, or (b) the Massive failover state machine — and even that should be as small and isolated as possible (a single wrapper class) rather than woven into either existing tested module.

## Common Pitfalls

### Pitfall 1: FastAPI version too old for `app.frontend()`
**What goes wrong:** The current `pyproject.toml` pin (`fastapi>=0.115.0`) does not guarantee `app.frontend()` exists — that method was added in 0.138.0 (2026-06-20).
**Why it happens:** The existing pin predates this feature; `uv sync` with the old floor could resolve to a pre-0.138 version if a lockfile isn't regenerated.
**How to avoid:** Bump the pin to `fastapi>=0.138.0` in `backend/pyproject.toml` before writing `app.frontend(...)` calls, then `uv sync` to refresh `uv.lock`.
**Warning signs:** `AttributeError: 'FastAPI' object has no attribute 'frontend'` at import/startup time.

### Pitfall 2: Router closures capture a stale `PriceCache`/source reference
**What goes wrong:** `create_stream_router(price_cache)` and the new watchlist router both need the *same* `PriceCache` and market-data-source instances that `lifespan` starts — if the app module constructs a second `PriceCache()` or router at a different point, SSE and watchlist CRUD silently diverge onto separate caches.
**Why it happens:** `create_stream_router` (verified, `backend/app/market/stream.py:17`) closes over whatever `price_cache` object it's called with; there is no global singleton enforcing consistency.
**How to avoid:** Construct exactly one `PriceCache()` at app module scope (or store it in `app.state` and defer all router creation until after `lifespan` populates it), and thread that single instance through `create_stream_router`, the watchlist router, and the market data source factory.
**Warning signs:** Adding a ticker via `POST /api/watchlist` doesn't appear in the SSE stream, or appears with no price data.

### Pitfall 3: Treating "watchlist ∪ open positions" as watchlist-only in Phase 1
**What goes wrong:** Since `positions` will always be empty until Phase 2's trading endpoints exist, it's tempting to write `get_active_tickers()` as "return the watchlist" and defer the union logic.
**Why it happens:** No code path can create a position yet, so the simplification is invisible in Phase 1 testing.
**How to avoid:** Write the actual `SELECT ticker FROM watchlist WHERE user_id=? UNION SELECT ticker FROM positions WHERE user_id=? AND quantity > 0` query now, even though the second half is a no-op today — this is explicitly why the phase notes mandate creating the full 6-table schema now (`.planning/phases/01-live-market-terminal/01-CONTEXT.md` code_context section, `backend/app/db/`).
**Warning signs:** Phase 2 requires reworking the watchlist-removal logic that should have been correct from Phase 1.

### Pitfall 4: `test_factory.py` assertions break silently after adding the failover wrapper
**What goes wrong:** `isinstance(source, MassiveDataSource)` assertions in the existing, passing test suite (`backend/tests/market/test_factory.py:42-49,71-79`, read this session) will fail once `create_market_data_source()` returns a `FailoverMarketDataSource` for the Massive branch.
**Why it happens:** Wrapping changes the concrete return type of an already-tested factory function.
**How to avoid:** Update these specific assertions as part of the PORT-05 implementation task, not as an afterthought; add new tests for `FailoverMarketDataSource` itself (simulate a Massive exception, assert the active source becomes `SimulatorDataSource` and stays that way on subsequent polls).
**Warning signs:** CI red on a task that "only touched massive_client.py."

### Pitfall 5: Building Lightweight Charts against v4-era API examples
**What goes wrong:** Most tutorials/training data show `chart.addLineSeries({...})`; the registry-current package (5.2.1, verified) uses `chart.addSeries(LineSeries, {...})` with `LineSeries` imported from the package.
**Why it happens:** v5 changed the series-creation API as part of a broader refactor for custom series/plugin support.
**How to avoid:** Follow the v5 example in Pattern 5 above; import `LineSeries` (or `AreaSeries`, etc.) as a named export alongside `createChart`.
**Warning signs:** `TypeError: chart.addLineSeries is not a function`.

### Pitfall 6: Static export + Image Optimization
**What goes wrong:** If any component later uses `next/image` with default settings, the build fails under `output: 'export'`.
**Why it happens:** The server-side Image Optimization API doesn't exist in a static export; Next.js throws at build time rather than silently degrading.
**How to avoid:** Set `images: { unoptimized: true }` in `next.config.ts` from the start (this phase doesn't need optimized images, but the flag prevents future build breaks), or avoid `next/image` entirely for now.
**Warning signs:** Build-time error referencing `export-image-api`.

## Code Examples

### FastAPI lifespan (see Pattern 1 above for full context)
```python
# Source: https://fastapi.tiangolo.com/advanced/events (Context7, this session)
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    yield
    # shutdown
```

### SQLite lazy init (stdlib, WAL mode)
```python
# Pattern verified via direct execution this session:
# sqlite3.Connection.autocommit exists on Python 3.13; PRAGMA journal_mode=WAL succeeds.
import sqlite3
from pathlib import Path

def init_db(db_path: str = "db/finally.db") -> None:
    exists = Path(db_path).exists()
    conn = sqlite3.connect(db_path, autocommit=True)
    conn.execute("PRAGMA journal_mode=WAL")
    if not exists or _tables_missing(conn):
        conn.executescript(SCHEMA_SQL)  # all 6 tables
        _seed_defaults(conn)
    conn.close()
```

### `app.frontend()` (see Pattern 2 above)
```python
app.frontend("/", directory="static", fallback="index.html")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `@app.on_event("startup")` / `@app.on_event("shutdown")` | `lifespan` async context manager | FastAPI 0.93.0+ (well-established by now) `[CITED: fastapi.tiangolo.com/release-notes]` | `on_event` still works but is legacy; use `lifespan` |
| Manual `StaticFiles` mount + catch-all route for SPA serving | `app.frontend(path, directory=..., fallback=...)` | FastAPI 0.138.0, 2026-06-20 `[VERIFIED: raw release-notes.md, this session]` | Directly changes the FOUND-03 implementation pattern from what most existing tutorials show |
| Tailwind v3 `tailwind.config.js` with `content: [...]` globs + `@tailwind base/components/utilities` directives | Tailwind v4 CSS-first `@import "tailwindcss";` + `@theme { --color-*: ... }` | Tailwind v4 (major rewrite) `[CITED: tailwindcss.com/docs]` | Config-file structure for this phase's dark theme tokens is different from v3-era examples |
| `lightweight-charts` v3/v4 `chart.addLineSeries(options)` | v5 `chart.addSeries(LineSeries, options)` | lightweight-charts v5 `[CITED: github.com/tradingview/lightweight-charts]` | Changes the exact API call in Pattern 5 |

**Deprecated/outdated:**
- `@app.on_event(...)`: superseded by `lifespan`, still functions but not the current recommended pattern.
- Manually mounting `StaticFiles` for a full SPA with fallback: superseded by `app.frontend()` for this exact use case (still valid for serving a plain assets directory without SPA fallback semantics).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|----------------|
| A1 | TypeScript registry-latest is genuinely major version 7.x (native/Go compiler line), not a `npm view` reporting artifact | Standard Stack | If wrong assumption about ecosystem readiness (editor tooling, ts-node equivalents, Next.js's own TS support) causes friction, pin to a known-stable 5.x line instead; verify TS 7.x + Next.js 16 compatibility before locking `package.json` |
| A2 | `FailoverMarketDataSource` wrapper design (new module, callback-based) is the correct shape for PORT-05, versus directly modifying `massive_client.py` to import `SimulatorDataSource` | Architecture Patterns (Pattern 3) | If the planner/executor prefers the more literal CONCERNS.md wording ("modify `_poll_once()` to ... transfer tracked tickers to the simulator instance"), a direct-import approach also satisfies PORT-05, at the cost of coupling the two previously-independent, fully-tested modules |
| A3 | Next.js `create-next-app` scaffold flags (`--typescript --tailwind --app --no-src-dir`) produce a config compatible with later Docker-stage copying (Phase 4) without adjustment | Standard Stack / Installation | Low risk — `output: 'export'` output directory (`out/`) is independent of `src/` vs root `app/` choice; only affects import ergonomics |
| A4 | `EventSource`'s built-in reconnection (native browser API) is sufficient for WATCH-04/UI-09's "connection status indicator" without additional client-side heartbeat logic | Architecture Patterns | If `EventSource.readyState` transitions don't map cleanly to the three required states (connected/reconnecting/disconnected), a small custom heartbeat/timeout layer may be needed on top |

**If this table is empty:** N/A — see entries above; none are compliance/security-critical, all are technology-choice risks with cheap correction paths.

## Open Questions

1. **Should `db/finally.db` connections be pooled or opened per-request?**
   - What we know: SQLite + stdlib `sqlite3` connections are cheap to open; WAL mode allows concurrent readers with one writer.
   - What's unclear: Whether a single long-lived connection (stored in `app.state`) or a per-request `sqlite3.connect()` is preferable for this phase's light write volume.
   - Recommendation: Use a single connection stored in `app.state.db` for this phase (simplest, matches the single-process/single-worker deployment target); revisit only if Phase 2's snapshot/trade write volume shows contention.

2. **Exact shape of the `MASSIVE_API_KEY`-set-but-invalid startup check.**
   - What we know: CONCERNS.md flags that invalid keys are currently only caught at first poll, not at startup.
   - What's unclear: Whether Phase 1 should add startup-time key format validation (out of PORT-05's literal scope, which is about *failure during a run*, not malformed keys at boot) or leave it to the same failover path (an invalid key will simply fail the first poll and trigger the same permanent-failover mechanism).
   - Recommendation: Let the same failover mechanism handle a bad key at first poll — no separate validation path needed; this keeps PORT-05's fix scope minimal and the behavior (bad key → simulator, permanently) is what PLAN.md §5 actually requires either way.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| FOUND-01 | `GET /api/health` health check | Trivial FastAPI route; no new research needed — standard `@app.get("/api/health")` returning `{"status": "ok"}` |
| FOUND-02 | Lazy SQLite schema create + seed on first run | Pattern 2 (SQLite lazy init, stdlib `sqlite3`, WAL mode) + Don't Hand-Roll row on WAL |
| FOUND-03 | Serve Next.js static export from FastAPI, single port | Pattern 2 (`app.frontend()`, FastAPI ≥0.138.0) — verified via direct install + `inspect.signature` |
| FOUND-04 | Market data source starts at app startup, tracks watchlist ∪ open positions | Pattern 1 (lifespan wiring existing `create_market_data_source`/`PriceCache`) + Pitfall 3 (write the real UNION query now) |
| WATCH-01 | `GET /api/watchlist` with latest prices | Reuses existing `PriceCache.get_all()`/`get_price()`; new router in `app/watchlist/` |
| WATCH-02 | `POST /api/watchlist` add ticker | New router + `source.add_ticker()` (existing `MarketDataSource` method, both implementations already support it) |
| WATCH-03 | `DELETE /api/watchlist/{ticker}`, keep streaming if open position | Pitfall 3 — active-ticker-set query must check `positions` table even though empty this phase |
| WATCH-04 | SSE pushes watchlist ∪ open positions at ~500ms | Already implemented (`stream.py`); Pitfall 2 (shared `PriceCache` instance) is the integration risk |
| PORT-05 | Massive permanent failover, never switches back | Pattern 3 (guard + `FailoverMarketDataSource` wrapper), Pitfall 4 (test-suite impact), CONCERNS.md fix-location citation |
| UI-01 | Watchlist grid: ticker, price, %, sparkline since page load | Recommended Project Structure (`Sparkline.tsx`, inline SVG, no charting lib per CONTEXT.md) |
| UI-02 | Price flash green/red fading CSS animation | Standard CSS transition on price-change class toggle; no external research needed, Tailwind v4 `@theme` + `transition` utilities suffice |
| UI-03 | Click ticker -> larger chart | Pattern 5 (Lightweight Charts v5 React integration) |
| UI-10 | Dark trading-terminal theme throughout | Standard Stack (Tailwind v4 CSS-first `@theme` tokens) using colors specified in PLAN.md §2 |
</phase_requirements>

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|--------------|-----------|---------|----------|
| Node.js | Next.js frontend build/dev | ✓ | v24.16.0 | — (exceeds Next.js's `>=20.9.0` requirement, verified) |
| npm | Frontend package installs | ✓ | 11.13.0 | — |
| uv | Backend dependency management | ✓ | 0.11.32 | — |
| Python (system) | N/A — project uses `uv`-managed venvs, not system Python | ✓ (3.13.15 via `uv venv`) | — | `uv` manages its own interpreter; system `python3`/`pip` are irrelevant to this project (`pip` on the base system is in fact broken — see below) |
| Docker | Not required this phase (Phase 4) | ✓ | 29.3.1 | N/A — noted for forward reference only |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** none — all required tools for this phase are present and version-sufficient.

**Note:** The base system's `pip` binary raised an import traceback when invoked directly (`pip index versions fastapi` failed with a broken `pip._internal.cli.autocompletion` import). This is irrelevant to the project, which uses `uv` exclusively per the user's global CLAUDE.md instructions (`uv run`/`uv add`, never `pip`/`python3` directly) — flagging only so the executor doesn't waste time debugging the system `pip` install.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Backend framework | pytest 8.3+ with `pytest-asyncio` (`asyncio_mode = "auto"`) `[VERIFIED: backend/pyproject.toml:30-36]` |
| Backend config file | `backend/pyproject.toml` (`[tool.pytest.ini_options]`) |
| Frontend framework | none configured — `frontend/` is empty; TEST-04 (frontend unit tests) is explicitly assigned to Phase 3 per `.planning/REQUIREMENTS.md` traceability table, not this phase |
| Quick run command | `cd backend && uv run --extra dev pytest -v` |
| Full suite command | `cd backend && uv run --extra dev pytest --cov=app` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|--------------|
| FOUND-01 | `/api/health` returns 200 | integration | `pytest backend/tests/api/test_health.py -x` | ❌ Wave 0 |
| FOUND-02 | Fresh DB gets schema + seed (default user, 10 tickers) | unit | `pytest backend/tests/db/test_init.py -x` | ❌ Wave 0 |
| FOUND-03 | Non-`/api/*` route serves static `index.html` | integration | `pytest backend/tests/api/test_static_frontend.py -x` | ❌ Wave 0 |
| FOUND-04 | Source starts with watchlist ∪ open positions on app startup | integration | `pytest backend/tests/api/test_app_startup.py -x` | ❌ Wave 0 |
| WATCH-01/02/03 | Watchlist CRUD, dup prevention, position-referenced removal | unit + integration | `pytest backend/tests/watchlist/ -x` | ❌ Wave 0 |
| WATCH-04 | SSE reflects watchlist changes | integration | Existing `pytest backend/tests/market/test_stream.py -x` extended, or new `test_stream_watchlist_integration.py` | ✅ (test_stream.py exists; extension needed) |
| PORT-05 | Massive failure → permanent simulator switch, never reverts | unit | `pytest backend/tests/market/test_failover.py -x` (new) + updated `test_factory.py` assertions | ❌ Wave 0 (new file); ✅ existing file needs edits |
| UI-01/02/03/10 | Watchlist grid, flash animation, chart-on-click, dark theme | manual (UAT) | N/A — frontend test framework not introduced until Phase 3 per traceability | N/A |

### Sampling Rate
- **Per task commit:** `cd backend && uv run --extra dev pytest -v` (fast subset relevant to the task's module)
- **Per wave merge:** `cd backend && uv run --extra dev pytest --cov=app`
- **Phase gate:** Full backend suite green before `/gsd-verify-work`; UI-0x requirements verified manually/via `/gsd-ui-review` since no automated frontend suite exists yet this phase.

### Wave 0 Gaps
- [ ] `backend/tests/api/test_health.py` — covers FOUND-01
- [ ] `backend/tests/api/test_static_frontend.py` — covers FOUND-03
- [ ] `backend/tests/api/test_app_startup.py` — covers FOUND-04
- [ ] `backend/tests/db/test_init.py` — covers FOUND-02
- [ ] `backend/tests/db/test_seed.py` — covers FOUND-02 seed data correctness
- [ ] `backend/tests/watchlist/test_router.py` — covers WATCH-01/02/03
- [ ] `backend/tests/market/test_failover.py` — covers PORT-05 (new `FailoverMarketDataSource`)
- [ ] `backend/tests/market/test_factory.py` — MODIFY existing assertions (see Pitfall 4)
- [ ] `backend/tests/conftest.py` — currently a docstring-only stub; add shared fixtures (temp SQLite path, seeded `PriceCache`, `FastAPI` test client with lifespan)
- [ ] Framework install: none — pytest/pytest-asyncio already present via `uv sync --extra dev`

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|----------------|---------|---------------------|
| V2 Authentication | No | Single hardcoded `user_id="default"`, no login this milestone (explicit scope decision, `.planning/REQUIREMENTS.md` Out of Scope) |
| V3 Session Management | No | No sessions — stateless REST + SSE |
| V4 Access Control | No | Single-user, no authorization boundaries to enforce |
| V5 Input Validation | Yes | Pydantic request models for `POST /api/watchlist` (`{ticker: str}`); ticker normalization via existing `normalize_ticker()` (`backend/app/market/interface.py:8`, verified) reused for consistency between API input and market-data-source ticker keys |
| V6 Cryptography | No | No secrets handled by this phase's new code beyond reading the existing `MASSIVE_API_KEY` env var (already-established pattern in `factory.py`) |
| V7 Error Handling & Logging | Yes | Watchlist errors (duplicate ticker, unknown ticker on delete) must return structured 4xx JSON, not leak stack traces; matches existing `logger = logging.getLogger(__name__)` module-level convention |
| V12 File/Resource | Yes (indirect) | `app.frontend(directory=...)` must not allow path traversal outside the static directory — this is FastAPI's own responsibility (built into `app.frontend()`), not custom code to write |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|------------------------|
| SQL injection via ticker string in watchlist queries | Tampering | Use parameterized `sqlite3` queries (`?` placeholders) exclusively — never string-format ticker values into SQL, even though `normalize_ticker()` already restricts to uppercase/trimmed strings |
| Path traversal via crafted request path against static frontend serving | Information Disclosure | Handled by FastAPI's `app.frontend()` internally (verified: dotted-path fix shipped in a recent patch per release notes, line 213 of `release-notes.md`) — do not bypass with a custom static handler |
| Unbounded watchlist growth (DoS via many `POST /api/watchlist` calls) | Denial of Service | Out of scope for this phase per PLAN.md (no stated ticker-count limit); note as a `checkpoint:human-verify`-worthy gap if the planner wants a soft cap, but not a phase blocker |
| SSE connection resource exhaustion (many open `EventSource` connections) | Denial of Service | Existing `stream.py` already checks `request.is_disconnected()` per iteration; no change needed, single-user app has natural low connection count |

## Sources

### Primary (HIGH confidence)
- Context7 `/websites/fastapi_tiangolo` — lifespan events, `StaticFiles`, `app.frontend()` reference signature
- Context7 `/vercel/next.js` — `output: 'export'` configuration, constraints, `create-next-app` defaults, `src/` folder conventions
- Context7 `/tradingview/lightweight-charts` — v5 `createChart`/`addSeries` API, React integration tutorial
- Context7 `/websites/tailwindcss` — v4 CSS-first `@theme` config, Next.js PostCSS install steps
- Direct tool verification this session: `uv pip install fastapi` into a throwaway venv + `inspect.signature(app.frontend)`; `npm view <pkg> version/engines/peerDependencies` for `next`, `react`, `tailwindcss`, `lightweight-charts`, `typescript`, `@tailwindcss/postcss`, `postcss`, `@types/*`; `sqlite3.Connection.autocommit` attribute check on the installed Python
- Raw file fetch: `raw.githubusercontent.com/fastapi/fastapi/master/docs/en/docs/release-notes.md` — confirms `app.frontend()` added in FastAPI 0.138.0 (2026-06-20)
- Direct reads this session of all `backend/app/market/*.py`, `backend/tests/market/*.py`, `backend/pyproject.toml`, `.planning/codebase/*.md`

### Secondary (MEDIUM confidence)
- WebFetch of `fastapi.tiangolo.com/tutorial/frontend` (summarized page content, cross-checked against Context7 snippets and the raw release notes)

### Tertiary (LOW confidence)
- None — all package/version/API claims were tool-verified or docs-cited this session; see Assumptions Log for the handful of judgment calls that remain open.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every version number was confirmed via `npm view`/`uv pip install` this session, not recalled from training data
- Architecture: HIGH — lifespan/`app.frontend()`/Lightweight Charts patterns confirmed via Context7 + direct signature inspection; Massive failover design is a reasoned proposal grounded in verbatim-quoted existing code, not an external citation (flagged as such)
- Pitfalls: HIGH — all six pitfalls are grounded in either verified current-API behavior or actual existing test/code content read this session

**Research date:** 2026-08-23
**Valid until:** 2026-09-06 (14 days — frontend ecosystem, especially Next.js/Tailwind/TypeScript major versions, moves fast enough that version pins should be re-checked if planning is delayed)
