# Phase 2: Portfolio & Trading - Pattern Map

**Mapped:** 2026-08-23
**Files analyzed:** 16
**Analogs found:** 14 / 16

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/app/portfolio/router.py` | route/controller | request-response + CRUD | `backend/app/watchlist/router.py` | exact |
| `backend/app/portfolio/trades.py` | service | CRUD (transactional) | `backend/app/db/connection.py` (query helpers) | role-match |
| `backend/app/portfolio/valuation.py` | service | transform | `backend/app/db/connection.py::get_active_tickers` | partial |
| `backend/app/portfolio/snapshots.py` | service | event-driven (background loop) | `backend/app/market/simulator.py` (`_run_loop`/start/stop) | role-match |
| `backend/app/portfolio/__init__.py` | module barrel | — | `backend/app/watchlist/__init__.py` | exact |
| `backend/app/main.py` (modified) | config/entrypoint | event-driven (lifespan) | itself (existing) | exact |
| `backend/tests/portfolio/test_trades.py` | test | CRUD | `backend/tests/watchlist/test_router.py` (fixture style) | role-match |
| `backend/tests/portfolio/test_router.py` | test | request-response | `backend/tests/watchlist/test_router.py` | exact |
| `backend/tests/portfolio/test_snapshots.py` | test | event-driven | `backend/tests/watchlist/test_router.py` + `conftest.py` fixtures | partial |
| `frontend/components/PositionsTable.tsx` | component | request-response (fetch + render) | `frontend/components/WatchlistPanel.tsx` | exact |
| `frontend/components/PortfolioHeatmap.tsx` | component | request-response (render) | `frontend/components/PriceChart.tsx` (client-chart-lifecycle pattern) | role-match |
| `frontend/components/PnlChart.tsx` | component | streaming/transform | `frontend/components/PriceChart.tsx` | exact |
| `frontend/components/TradeBar.tsx` | component | request-response (form submit) | `frontend/components/WatchlistPanel.tsx` (add-ticker form) | role-match |
| `frontend/app/page.tsx` (modified) | page/provider | state orchestration | itself (existing) | exact |
| `frontend/hooks/usePortfolio.ts` (new, if added) | hook | request-response/polling | `frontend/hooks/usePriceStream.ts` | role-match (not read this session, inferred pattern) |
| `frontend/package.json` (add `recharts`) | config | — | n/a | no analog needed |

## Pattern Assignments

### `backend/app/portfolio/router.py` (route, request-response + CRUD)

**Analog:** `backend/app/watchlist/router.py` (full file read, 117 lines)

**Imports pattern** (lines 1-18):
```python
from __future__ import annotations

import logging
import re
import sqlite3
from collections.abc import Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.db import add_watchlist_ticker, get_watchlist_tickers, remove_watchlist_ticker
from app.db import ticker_has_open_position as db_ticker_has_open_position
from app.market import MarketDataSource, PriceCache
from app.market.interface import normalize_ticker

logger = logging.getLogger(__name__)
```
For portfolio, swap `app.db` watchlist helpers for portfolio helpers (or inline SQL via `trades.py`/`valuation.py`), keep `PriceCache`/`normalize_ticker` imports identical.

**Request validation pattern** (lines 23-34, `AddTickerRequest`):
```python
class AddTickerRequest(BaseModel):
    ticker: str = Field(min_length=1)

    @field_validator("ticker")
    @classmethod
    def _normalize_and_validate(cls, value: str) -> str:
        normalized = normalize_ticker(value)
        if not normalized or not _TICKER_PATTERN.match(normalized):
            raise ValueError("ticker must contain only letters, '.', and '-'")
        return normalized
```
Mirror directly for `TradeRequest` (see RESEARCH.md Code Examples for the `side: Literal["buy","sell"]` + `quantity: float = Field(gt=0)` variant — same `field_validator` shape).

**Factory router pattern** (lines 60-70):
```python
def create_watchlist_router(
    get_conn: Callable[[], sqlite3.Connection],
    market_source: MarketDataSource,
    price_cache: PriceCache,
) -> APIRouter:
    router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])
    ...
    return router
```
Use identically for `create_portfolio_router(get_conn, market_source, price_cache) -> APIRouter` with `prefix="/api/portfolio"`.

**DB-write-then-external-call ordering + error handling** (lines 79-95):
```python
@router.post("", status_code=201)
async def add_to_watchlist(request: AddTickerRequest) -> dict:
    conn = get_conn()
    ticker = normalize_ticker(request.ticker)

    inserted = add_watchlist_ticker(conn, ticker)
    if not inserted:
        raise HTTPException(status_code=409, detail="Ticker already on watchlist")

    await market_source.add_ticker(ticker)
    return _entry_for(ticker, price_cache)
```
For `POST /api/portfolio/trade`: validate → look up price → validate cash/qty (reject via `HTTPException(400, detail=...)` before any write, per PORT-03) → call `execute_trade()` (writes DB) → `await market_source.add_ticker(ticker)` on buy only (Pattern 4 in RESEARCH.md) → return trade result dict.

**Idempotent guard-then-act pattern** (lines 97-115, DELETE handler) — model for any "re-derive state from DB on every call" logic (not directly reused here, but shows the project's idiom of never trusting cached in-memory state for authorization-style checks).

---

### `backend/app/portfolio/trades.py` (service, CRUD/transactional)

**Analog:** `backend/app/db/connection.py` (query-helper style) + RESEARCH.md Code Examples (authoritative transaction skeleton, already verified against this repo's `autocommit=True` setup)

**Helper function style** (from `connection.py` lines 97-121, `add_watchlist_ticker`/`remove_watchlist_ticker`):
```python
def add_watchlist_ticker(
    conn: sqlite3.Connection, ticker: str, user_id: str = DEFAULT_USER_ID
) -> bool:
    cursor = conn.execute(
        "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
        (uuid.uuid4().hex, user_id, ticker, datetime.now(UTC).isoformat()),
    )
    return cursor.rowcount > 0
```
Function signature style (`conn: sqlite3.Connection, ..., user_id: str = DEFAULT_USER_ID`), `uuid.uuid4().hex` for IDs, `datetime.now(UTC).isoformat()` for timestamps — copy exactly for `execute_trade()`.

**Explicit transaction + weighted-avg-cost skeleton** — copy verbatim from RESEARCH.md "Explicit-Transaction Trade Execution Skeleton" (lines 340-392 of 02-RESEARCH.md). Key points to preserve:
- `conn.execute("BEGIN")` ... `conn.execute("COMMIT")` wrapped in `try/except` with `conn.execute("ROLLBACK"); raise` on failure (autocommit=True means this project's `conn.commit()` is a no-op — see `backend/app/db/connection.py:51`).
- No `await` between `BEGIN` and `COMMIT`.
- `ON CONFLICT(user_id, ticker) DO UPDATE` UPSERT for `positions`, matching `schema.sql`'s `UNIQUE (user_id, ticker)`.
- Epsilon-tolerant comparisons (`cost > cash + 1e-9`, `quantity > old_qty + 1e-9`) and `round(x, 8)` on write.

---

### `backend/app/portfolio/snapshots.py` (service, event-driven background loop)

**Analog:** `backend/app/main.py` `lifespan()` (lines 29-48) for task lifecycle wiring, and RESEARCH.md Pattern 5 for the loop body (verified against `backend/app/market/simulator.py`'s `asyncio.create_task(..., name="simulator-loop")` / `except asyncio.CancelledError:` idiom, not re-quoted here to avoid re-reading the file).

**Lifespan wiring pattern** (main.py lines 29-48):
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    conn = get_db()
    tickers = get_active_tickers(conn)

    await source.start(tickers)

    app.state.cache = cache
    app.state.source = source
    app.state.db = conn

    logger.info("FinAlly backend started with %d active tickers", len(tickers))

    yield

    await source.stop()
    conn.close()
    logger.info("FinAlly backend shut down")
```
Extend this exact function: after `await source.start(tickers)`, add `snapshot_task = asyncio.create_task(_snapshot_loop(get_db, cache), name="portfolio-snapshot-loop")`; store on `app.state.snapshot_task`; before `await source.stop()` on shutdown, cancel and await it catching `asyncio.CancelledError` (mirrors `MarketDataSource.stop()` idiom).

**Loop body** — copy RESEARCH.md Pattern 5 example (02-RESEARCH.md lines 244-251):
```python
async def _snapshot_loop(get_conn, cache, interval: float = 30.0) -> None:
    while True:
        await asyncio.sleep(interval)
        conn = get_conn()
        record_snapshot(conn, compute_total_value(conn, cache))
```

---

### `backend/app/portfolio/valuation.py` (service, transform)

**Analog:** `backend/app/db/connection.py::get_active_tickers` (lines 72-85) for query style; RESEARCH.md Pattern 3 for the shared valuation function (already the authoritative implementation, verified against `PriceCache` API).

```python
def compute_total_value(conn: sqlite3.Connection, cache: PriceCache, user_id: str = "default") -> float:
    cash = conn.execute(
        "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
    ).fetchone()[0]
    rows = conn.execute(
        "SELECT ticker, quantity, avg_cost FROM positions WHERE user_id = ? AND quantity > 0",
        (user_id,),
    ).fetchall()
    holdings_value = sum(
        qty * (cache.get_price(ticker) or avg_cost)
        for ticker, qty, avg_cost in rows
    )
    return cash + holdings_value
```
Use this single function from `GET /api/portfolio`, the trade response, and both snapshot triggers — do not reimplement.

---

### `backend/tests/portfolio/test_router.py` and `test_trades.py` (test, request-response / CRUD)

**Analog:** `backend/tests/watchlist/test_router.py` (full file, 170 lines) + `backend/tests/conftest.py` (fixtures)

**Fake collaborator pattern** (test_router.py lines 16-40):
```python
class FakeMarketSource:
    """Records add_ticker/remove_ticker calls instead of running a real simulator."""

    def __init__(self, tickers: list[str] | None = None) -> None:
        self._tickers = list(tickers or [])
        self.add_calls: list[str] = []
        self.remove_calls: list[str] = []

    async def start(self, tickers: list[str]) -> None:
        self._tickers = list(tickers)

    async def add_ticker(self, ticker: str) -> None:
        self.add_calls.append(ticker)
        if ticker not in self._tickers:
            self._tickers.append(ticker)
    ...
```
Reuse `FakeMarketSource` as-is (import or duplicate into `tests/portfolio/`) since trade execution also calls `market_source.add_ticker()` on buy.

**Test-local insert helper** (lines 43-48):
```python
def _insert_position(conn, ticker: str, quantity: float = 1.0) -> None:
    conn.execute(
        "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
        "VALUES (?, 'default', ?, ?, 100.0, ?)",
        (uuid.uuid4().hex, ticker, quantity, datetime.now(UTC).isoformat()),
    )
```
Add a local `_insert_position` (with `avg_cost` param) in the new test files per RESEARCH.md's Wave 0 Gaps note — do not add to `conftest.py`.

**Router-under-test fixture pattern** (lines 51-62):
```python
@pytest.fixture
def watchlist_client(initialized_db):
    conn = initialized_db
    source = FakeMarketSource()
    cache = PriceCache()

    app = FastAPI()
    app.include_router(create_watchlist_router(lambda: conn, source, cache))

    with TestClient(app) as client:
        yield client, conn, source, cache
```
Mirror for `portfolio_client` fixture wrapping `create_portfolio_router`.

**Assertion style** (lines 68-76, 158-169) — direct SQL assertions against `conn` after the HTTP call, plus response JSON shape checks; use for verifying `positions`/`trades`/`users_profile.cash_balance` rows post-trade.

**conftest.py fixtures available (do not redefine):** `initialized_db`, `seeded_cache`, `tmp_db_path`, `client` (full `TestClient(app)` with real `lifespan`) — from `backend/tests/conftest.py` lines 14-58.

---

### `frontend/components/PositionsTable.tsx` (component, request-response)

**Analog:** `frontend/components/WatchlistPanel.tsx` (full file, 236 lines)

**Row selection + highlight pattern** (lines 179-200):
```tsx
<tr
  key={ticker}
  role="row"
  tabIndex={0}
  aria-selected={isSelected}
  onClick={() => onSelect(ticker)}
  onKeyDown={(event) => handleRowKeyDown(event, ticker)}
  onAnimationEnd={() => clearFlash(ticker)}
  className={`cursor-pointer border-b border-terminal-border/60 ${flashClass} ${
    isSelected ? "border-l-2 border-l-accent-blue bg-terminal-bg/60" : ""
  }`}
>
```
Per D-08, reuse this exact `isSelected` treatment (`border-l-2 border-l-accent-blue bg-terminal-bg/60`, or swap to accent-yellow per D-08's wording — confirm against Phase 1's actual token) for positions rows and heatmap tiles.

**Keyboard handler** (lines 124-129):
```tsx
function handleRowKeyDown(event: KeyboardEvent<HTMLTableRowElement>, ticker: string) {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    onSelect(ticker);
  }
}
```

**Fetch-then-setState pattern** (lines 52-61):
```tsx
const refetch = useCallback(async () => {
  const response = await fetch("/api/watchlist");
  if (!response.ok) return;
  const data = (await response.json()) as WatchlistEntry[];
  setTickers(data.map((entry) => entry.ticker));
}, []);

useEffect(() => {
  refetch();
}, [refetch]);
```
Use identically for `GET /api/portfolio` polling/refetch in `PositionsTable`.

**Empty-state note (D-01):** No existing analog for an empty state exists in `WatchlistPanel` (watchlist is always seeded with 10 tickers). Implement as a simple conditional render replacing `<tbody>` contents: `{rows.length === 0 ? <EmptyState message="No positions yet — buy shares to get started" /> : rows.map(...)}` — no analog, follow terminal-panel styling (`text-terminal-muted`, centered) used for `"Connection: {status}"` text in `page.tsx` line 26-27 and `"Select a ticker to see its chart"` in `PriceChart.tsx` line 93.

---

### `frontend/components/PnlChart.tsx` (component, streaming/transform)

**Analog:** `frontend/components/PriceChart.tsx` (full file, 98 lines) — copy almost verbatim.

**Client-only chart lifecycle guard** (lines 1, 32-76):
```tsx
'use client';
...
useEffect(() => {
  if (!containerRef.current) return;
  const chart = createChart(containerRef.current, { ... });
  const series = chart.addSeries(LineSeries, { color: "#209dd7", lineWidth: 2 });
  chartRef.current = chart;
  seriesRef.current = series;

  const resizeObserver = new ResizeObserver((entries) => {
    const entry = entries[0];
    if (!entry) return;
    chart.applyOptions({ width: entry.contentRect.width, height: entry.contentRect.height });
  });
  resizeObserver.observe(containerRef.current);

  return () => {
    resizeObserver.disconnect();
    chart.remove();
    chartRef.current = null;
    seriesRef.current = null;
  };
}, []);
```
Mandatory per RESEARCH.md Pitfall 4 (static-export prerender breaks on DOM APIs) — never call `createChart` outside `useEffect`.

**Data update pattern** (lines 82-86):
```tsx
useEffect(() => {
  seriesRef.current?.setData(
    points.map((point) => ({ time: point.time as UTCTimestamp, value: point.value })),
  );
}, [ticker, points]);
```
Reuse for snapshot points `{time, value}` from `GET /api/portfolio/history`.

**Empty-state (D-03):** Follow the same `{ticker ? <label/> : <fallback-text/>}` conditional pattern (lines 90-94) — show empty-state message until `points.length >= 2`, else render the chart.

---

### `frontend/components/TradeBar.tsx` (component, request-response form submit)

**Analog:** `frontend/components/WatchlistPanel.tsx` add-ticker form (lines 88-108, 151-166)

**Form submit + status-code branching pattern**:
```tsx
async function handleAdd(event: FormEvent) {
  event.preventDefault();
  const ticker = inputValue.trim().toUpperCase();
  if (!ticker) return;

  const response = await fetch("/api/watchlist", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker }),
  });

  if (response.status === 201) {
    setInputValue("");
    setErrorMessage(null);
    await refetch();
  } else if (response.status === 409) {
    setErrorMessage(`${ticker} is already on the watchlist`);
  } else {
    setErrorMessage(`Could not add ${ticker}`);
  }
}
```
For `TradeBar`, POST to `/api/portfolio/trade`; branch on `200`/`201` (success, clear+refetch portfolio) vs `400` (read `detail` from JSON body and show as `errorMessage`, matching PORT-03's "clear error, no partial fill").

**Purple submit button styling** (line 159-164):
```tsx
<button
  type="submit"
  className="rounded bg-accent-purple px-3 py-1 text-sm font-medium text-terminal-text hover:opacity-90"
>
  Add
</button>
```
PLAN.md §2 locks purple (`#753991`, CSS var `--color-accent-purple`) for trade submit buttons — reuse this exact class for Buy/Sell buttons (differentiate buy/sell only by label/icon, not color, unless up/down tokens are used for buy=up-green/sell=down-red per Claude's discretion).

**Prefill from selection (D-07):** No existing analog (watchlist input isn't driven by `selectedTicker`). New wiring: `TradeBar` accepts a `selectedTicker: string | null` prop from `page.tsx` and seeds its local ticker-input state via `useEffect(() => { if (selectedTicker) setTickerInput(selectedTicker); }, [selectedTicker])` — same `useEffect`-driven sync idiom used elsewhere in the codebase, no direct copy source.

---

### `frontend/components/PortfolioHeatmap.tsx` (component, request-response render)

**Analog:** `frontend/components/PriceChart.tsx` for the "must run in `useEffect`/client-only" discipline (Recharts' `Treemap` uses `ResizeObserver`-based `ResponsiveContainer`, same DOM-touching risk class per RESEARCH.md Pitfall 4) — no in-repo Recharts precedent exists yet since this is a new dependency.

**Reference implementation** — copy from RESEARCH.md Code Examples "Recharts Treemap with Custom Cell Coloring" (02-RESEARCH.md lines 321-337):
```tsx
import { Treemap } from "recharts";

function CustomizedCell({ x, y, width, height, name, value, plColor }: any) {
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} style={{ fill: plColor, stroke: "#0d1117", strokeWidth: 2 }} />
      <text x={x + 4} y={y + 16} fill="#e6edf3" fontSize={12}>{name}</text>
    </g>
  );
}

<Treemap data={positionsAsTreemapNodes} dataKey="weight" content={CustomizedCell} />
```
`plColor` derived from `--color-up: #3fb950` / `--color-down: #f85149` (see `frontend/app/globals.css` lines 16-17) based on each position's unrealized P&L sign — same tokens `WatchlistPanel`'s `directionTextClass` already uses (`text-up`/`text-down`, lines 186-187 of `WatchlistPanel.tsx`).

**Empty-state (D-02):** Same conditional-render pattern as `PositionsTable`/`PnlChart` — render empty-state message in place of `<Treemap>` when `positions.length === 0`.

---

### `frontend/app/page.tsx` (modified, state orchestration)

**Analog:** itself (existing file, 53 lines, full content read)

**Existing `selectedTicker` state + prop wiring** (lines 9-17, 43-49):
```tsx
const { prices, history, timeline, status } = usePriceStream();
const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
...
<WatchlistPanel
  prices={prices}
  history={history}
  selected={selectedTicker}
  onSelect={setSelectedTicker}
/>
<PriceChart ticker={selectedTicker} points={chartPoints} />
```
Per D-05/D-06/D-07/D-08: pass `selected={selectedTicker} onSelect={setSelectedTicker}` to `PositionsTable` and `PortfolioHeatmap` exactly as done for `WatchlistPanel`; pass `selectedTicker` to `TradeBar` for prefill. Extend the `grid-cols-[minmax(0,420px)_1fr]` layout (line 42) to accommodate the new panels — comment at lines 36-41 already flags this as reserved space.

**Header extension target** (lines 24-32) — existing header is title + connection text only; UI-09 extends this with live total value, cash balance, and a colored status dot (currently just text `Connection: {status}` at line 27, no dot element yet — new UI element, no in-repo dot analog).

---

## Shared Patterns

### Router factory + dependency injection
**Source:** `backend/app/watchlist/router.py` lines 60-70 (`create_watchlist_router`)
**Apply to:** `backend/app/portfolio/router.py` — same `create_portfolio_router(get_conn, market_source, price_cache) -> APIRouter` signature and factory-per-call convention (enables test reuse without route accumulation).

### Explicit-transaction SQLite writes (autocommit=True)
**Source:** `backend/app/db/connection.py:51` (`autocommit=True`) + RESEARCH.md Pattern 1 (verified against docs.python.org)
**Apply to:** `backend/app/portfolio/trades.py::execute_trade` only — the sole multi-statement write path this phase introduces. `conn.execute("BEGIN")` / `conn.execute("COMMIT")` / `except: conn.execute("ROLLBACK"); raise`, with zero `await` between.

### Ticker normalization
**Source:** `backend/app/market/interface.py::normalize_ticker` (imported and used at `watchlist/router.py:16,31,88,107`)
**Apply to:** All portfolio ticker inputs (`TradeRequest.ticker` field_validator) — identical to `AddTickerRequest`.

### `selectedTicker` shared state
**Source:** `frontend/app/page.tsx` lines 10-11, 43-49
**Apply to:** `PositionsTable`, `PortfolioHeatmap`, `TradeBar` — single state owner in `page.tsx`, prop-drilled `selected`/`onSelect` (D-05/D-06), consumed for prefill (D-07) and highlight (D-08).

### Client-only chart/DOM component guard
**Source:** `frontend/components/PriceChart.tsx` lines 1, 32-76 (`'use client'` + all DOM/canvas calls inside `useEffect`)
**Apply to:** `PnlChart.tsx` (lightweight-charts reuse) and `PortfolioHeatmap.tsx` (Recharts Treemap) — mandatory to avoid Next.js static-export prerender failures (RESEARCH.md Pitfall 4).

### Empty-state message pattern (D-01/D-02/D-03)
**Source:** No direct in-repo analog; closest precedent is the conditional label in `PriceChart.tsx` lines 90-94 (`{ticker ? <label/> : <fallback text/>}`) and `text-terminal-muted` styling used throughout `WatchlistPanel`/`page.tsx`.
**Apply to:** `PositionsTable.tsx`, `PortfolioHeatmap.tsx`, `PnlChart.tsx` — centered `text-terminal-muted` message replacing the data body, not the whole panel.

### Test fixture reuse
**Source:** `backend/tests/conftest.py` (`initialized_db`, `seeded_cache`, `client`), `backend/tests/watchlist/test_router.py` (`FakeMarketSource`, local `_insert_position` helper, fixture-per-router pattern)
**Apply to:** All new files under `backend/tests/portfolio/` — no new conftest fixtures needed per RESEARCH.md Wave 0 Gaps.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `frontend/components/PortfolioHeatmap.tsx` | component | render | `recharts` is a brand-new dependency (not yet installed); no existing Treemap usage in repo — RESEARCH.md Code Examples is the closest thing to an analog (Context7-sourced, not repo-native) |
| Header live-stats + connection-status dot markup | UI fragment (part of `page.tsx`) | render | Current header (`page.tsx` lines 24-32) has only text, no colored-dot element anywhere in the frontend yet; build fresh using existing `--color-up`/`--color-down`/`--color-accent-*` CSS tokens (`globals.css`) rather than copying a nonexistent pattern |

## Metadata

**Analog search scope:** `backend/app/` (watchlist, db, market, main.py), `backend/tests/` (watchlist, conftest), `frontend/app/page.tsx`, `frontend/components/` (WatchlistPanel, PriceChart), `frontend/app/globals.css`
**Files scanned:** 9 read in full (watchlist/router.py, db/connection.py, main.py, page.tsx, WatchlistPanel.tsx, PriceChart.tsx, watchlist/test_router.py, conftest.py, globals.css excerpt)
**Pattern extraction date:** 2026-08-23
