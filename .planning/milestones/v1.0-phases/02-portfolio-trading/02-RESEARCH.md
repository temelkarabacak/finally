# Phase 2: Portfolio & Trading - Research

**Researched:** 2026-08-23
**Domain:** Financial trade execution, SQLite transactional integrity, portfolio valuation, React data visualization (treemap/line chart)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Before the first trade, the positions table shows a centered empty-state message (e.g. "No positions yet — buy shares to get started") in place of the table body, rather than hiding the panel or showing bare headers.
- **D-02:** The heatmap uses the same empty-state message pattern pre-trade, in place of the treemap.
- **D-03:** The P&L chart uses the same empty-state message pattern until at least 2 snapshot points exist to draw a line.
- **D-04:** The 30-second portfolio snapshot recorder starts at app startup (in the FastAPI `lifespan`), not gated on the first trade — it records a flat $10,000 history from minute one regardless of whether the user has traded yet. This also means the P&L chart's empty-state window is short-lived even for a user who hasn't traded (fills in within ~60s of app start), and portfolio snapshot recording does not need a "first trade" trigger to begin — only the existing "immediately after each trade" trigger is additional to the always-on 30s cadence. — **Reversibility:** reversible — purely a background task start condition, easy to change later.
- **D-05:** Clicking a positions-table row selects that ticker and drives the main chart, using the same `onSelect(ticker)` pattern `WatchlistPanel` already uses via `page.tsx`'s `selectedTicker` state.
- **D-06:** Clicking a heatmap tile does the same — all three ticker surfaces (watchlist, positions table, heatmap) converge on one shared `selectedTicker` state in `page.tsx`.
- **D-07:** Selecting a ticker from any of the three surfaces also prefills the trade bar's ticker field, so the flow is: click a row/tile → chart updates → trade bar is ready to buy/sell that ticker without retyping it.
- **D-08:** The currently-selected ticker gets a consistent visual highlight (e.g. accent-yellow border/background) wherever it appears — watchlist row, positions row, heatmap tile — reusing whatever selected-row treatment `WatchlistPanel` already has, rather than only showing selection via the chart changing.

### Claude's Discretion

User discussed 2 of the 4 offered areas (Empty portfolio state, Ticker selection consistency) and was satisfied with that coverage. The following were offered but not discussed — Claude's judgment applies, informed by PLAN.md and existing Phase 1 patterns:
- **Trade bar placement & layout** — where it sits in the grid, exact field/button arrangement. PLAN.md §2 locks purple (`#753991`) for submit buttons; no confirmation dialog (already established for trades). Prefill behavior is locked by D-07 above.
- **Header live stats layout** — how portfolio total value, cash balance, and the connection status dot arrange relative to the existing "FinAlly" title / "Connection: {status}" text in `page.tsx:24-32`. Whether value/cash flash on change like prices do is Claude's call — PLAN.md only specifies flash for watchlist prices (§2), not header stats.
- **Trade execution & snapshot write serialization** — SQLite is WAL-mode with `autocommit=True` (`backend/app/db/connection.py`); trade execution touches `positions`, `trades`, `users_profile.cash_balance`, and `portfolio_snapshots` across multiple statements. Whether to wrap a trade in an explicit transaction, and how the 30s snapshot task avoids interleaving badly with concurrent trade writes, is a backend implementation detail — flagged in `.planning/STATE.md` under Blockers/Concerns for Phase 2, not something the user needs to decide. **This research resolves the mechanism — see Architecture Patterns and Common Pitfalls below.**
- **Heatmap treemap library choice** — mirrors the Phase 1 precedent of picking a charting library without asking (Lightweight Charts was Claude's call there); PLAN.md §10 doesn't mandate a specific treemap library.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope. Trade bar layout and header stats layout were offered as discussable areas but the user was satisfied after covering empty states and ticker selection; both remain in-scope for this phase, just left to Claude's discretion rather than deferred to a future phase.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PORT-01 | `GET /api/portfolio` — positions, cash, total value, unrealized P&L | Architecture Patterns: Portfolio Valuation; Code Examples: portfolio view builder |
| PORT-02 | `POST /api/portfolio/trade` — market buy/sell, fractional quantities | Architecture Patterns: Trade Execution Transaction; Code Examples: trade router skeleton |
| PORT-03 | Buy/sell rejected outright (never clamped) on insufficient cash/quantity | Common Pitfalls: Float-Precision Sell Rejection; Code Examples: validation order |
| PORT-04 | Snapshots every 30s + post-trade, via `GET /api/portfolio/history` | Architecture Patterns: Snapshot Dual-Trigger; Code Examples: background task |
| UI-04 | Portfolio heatmap (treemap), sized by weight, colored by P&L | Standard Stack: recharts; Code Examples: Treemap |
| UI-05 | P&L line chart of total portfolio value | Standard Stack: lightweight-charts reuse; Architecture Patterns |
| UI-06 | Positions table (ticker, qty, avg cost, current price, unrealized P&L, % change) | Architecture Patterns: Portfolio Valuation |
| UI-07 | Trade bar (ticker, quantity, buy/sell) | Code Examples: trade bar component sketch |
| UI-09 | Header: live total value, cash balance, connection status dot | Architecture Patterns: reuse `usePriceStream` `status` |
| TEST-01 | Backend unit tests: trade execution, P&L math, insufficient cash/shares edges | Validation Architecture section |
</phase_requirements>

## Summary

Phase 2 is almost entirely backend-logic-and-wiring work landing on top of an already-complete schema and market-data layer — `positions`, `trades`, and `portfolio_snapshots` tables exist and are unused; `get_active_tickers()` and `ticker_has_open_position()` already read from `positions` correctly. The real engineering risk in this phase is **not** UI (which mirrors Phase 1's established `WatchlistPanel`/`PriceChart`/`usePriceStream` patterns closely) but **transactional correctness of trade execution against a `sqlite3` connection opened with `autocommit=True`**. This mode was added in Python 3.12 and changes SQLite transaction semantics from what most training data assumes: `conn.commit()`/`conn.rollback()` are no-ops, and multiple statements are **not** implicitly grouped — each `execute()` commits independently unless the code issues an explicit SQL `BEGIN`/`COMMIT` [CITED: docs.python.org/3/library/sqlite3.html]. A trade that writes to `positions`, `trades`, and `users_profile.cash_balance` without wrapping those statements in explicit `BEGIN`/`COMMIT` risks a partially-applied trade if any statement fails midway — directly threatening PORT-03 ("nothing is partially filled or clamped").

The second finding resolves the write-serialization concern flagged in `.planning/STATE.md`: because every SQLite call in this codebase is **synchronous** (never wrapped in `asyncio.to_thread`, unlike the Massive REST client) and the app runs a single-threaded asyncio event loop, a sequence of `conn.execute()` calls with **no `await` in between** cannot be interleaved by the 30-second snapshot background task or by a concurrent trade request — asyncio can only switch tasks at an `await` point [CITED: docs.python.org/3/library/asyncio-dev.html general cooperative-scheduling model]. This means the existing single shared connection (`app/db/connection.py:18`, `check_same_thread=False`) plus an explicit `BEGIN...COMMIT` block with no intervening `await` is sufficient to serialize trade writes against the periodic snapshot writer — **no `asyncio.Lock` is required**, matching the "do not overengineer" project constraint.

Third, position averaging can be implemented with a single weighted-average formula that requires **no special-casing** for re-opening a fully-closed position: because `quantity=0` naturally zeroes out the "old" term in `(old_qty*old_avg_cost + buy_qty*price) / (old_qty+buy_qty)`, a position that was sold to zero and later re-bought correctly resets `avg_cost` to the new purchase price with the same formula used for every other buy.

Fourth, on the frontend, PLAN.md §10 explicitly names Recharts as an acceptable charting library alongside Lightweight Charts. Recharts ships a `Treemap` component that satisfies UI-04 directly — no separate treemap-layout library needed. The existing `lightweight-charts` dependency (already used for the per-ticker price chart) can be reused as-is for the P&L line chart (UI-05), keeping a single charting pattern for line-over-time data and adding Recharts only for the one chart type Lightweight Charts cannot do (treemap).

**Primary recommendation:** Wrap every multi-statement trade write in an explicit SQL `BEGIN`/`COMMIT` (rollback on any exception) with zero `await` calls between them; reuse the weighted-average-cost formula unconditionally (no zero-quantity special case); add `recharts` for the treemap only, and reuse `lightweight-charts` for the P&L line chart.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Trade validation (cash/quantity sufficiency) | API / Backend | — | Server is the source of truth for cash and positions; client-side checks would be advisory only and are not required by PLAN.md |
| Trade execution (writes to positions/trades/cash) | API / Backend | Database / Storage | `app/portfolio/router.py` orchestrates; SQLite persists |
| Portfolio valuation (current price × qty) | API / Backend | — | Reads `PriceCache` (in-process, already the pattern for watchlist entries) — never re-fetches market data per request |
| Portfolio snapshot recording (30s + post-trade) | API / Backend | Database / Storage | Background `asyncio.Task` started in `lifespan`, mirrors `source.start()` |
| Positions table / heatmap / P&L chart rendering | Browser / Client | — | Pure presentation of `/api/portfolio` and `/api/portfolio/history` responses |
| Ticker selection state (`selectedTicker`) | Browser / Client | — | Already owned by `page.tsx`; this phase adds more consumers, not a new owner |
| Active-ticker-set extension on trade | API / Backend | — | `market_source.add_ticker()` call after a buy, same call already used by the watchlist router — belongs with the layer that owns `MarketDataSource` |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `recharts` | 3.10.1 [ASSUMED: package name from training knowledge; existence/version VERIFIED: `npm view recharts version` — see Package Legitimacy Audit] | Treemap component for the portfolio heatmap (UI-04) | Explicitly named as an acceptable charting library in `planning/PLAN.md` §10 ("Lightweight Charts or Recharts"); ships a ready-made `<Treemap>` with a customizable cell renderer, avoiding a hand-rolled squarified-treemap layout algorithm |
| `lightweight-charts` | `^5.2.1` (already installed — `frontend/package.json`) [VERIFIED: frontend/package.json] | P&L line chart (UI-05), reused from the Phase 1 `PriceChart.tsx` pattern | Already the project's chosen line-chart library (01-CONTEXT.md decision); reusing it for the P&L chart avoids a second line-chart dependency and keeps one rendering pattern for all "value over time" visuals |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `sqlite3` (stdlib) | Python 3.14.6 bundled, SQLite 3.53.1 [VERIFIED: `uv run python -c "import sqlite3; print(sqlite3.sqlite_version)"`] | All trade/snapshot persistence | Already the project's only DB layer; no ORM needed at this scale (single user, 5 small tables) |
| `pydantic` (transitive via FastAPI) | Bundled with `fastapi>=0.138.0` [VERIFIED: backend/pyproject.toml — no direct pydantic pin needed; `watchlist/router.py:11` already imports it] | Trade request body validation (`TradeRequest`) | Mirrors `AddTickerRequest` pattern already in `watchlist/router.py` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `recharts` Treemap | `@visx/hierarchy` + hand-rolled squarify | More control over rendering, but PLAN.md already blesses Recharts and it ships tooltip/responsive-container wiring for free — hand-rolling a treemap layout algorithm is exactly the kind of "don't hand-roll" complexity this research flags below |
| `recharts` LineChart for P&L | reuse `lightweight-charts` (chosen) | Recharts LineChart would avoid a second library-specific rendering pattern for the treemap alone, but `lightweight-charts` is already proven in `PriceChart.tsx` for near-identical data shape (`{time, value}[]`) — reuse wins on consistency and lower review surface |
| Explicit `BEGIN`/`COMMIT` SQL | `asyncio.Lock` around trade handler | A lock is defensive but redundant given the synchronous-connection-on-single-event-loop guarantee (see Architecture Patterns); adding one anyway is not wrong, just unnecessary per "do not overengineer" |

**Installation:**
```bash
npm install recharts
```
(run inside `frontend/`; no new backend package required)

**Version verification:**
```bash
npm view recharts version
# => 3.10.1, published 2026-07-25
```
Training-data familiarity with Recharts (a long-standing, ubiquitous React charting library) informed the choice; the specific version and its React 19 peer-dependency range were confirmed live against the npm registry, not assumed from memory.

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|--------------|---------|-------------|
| `recharts` | npm | latest version published 2026-07-25 (package itself has 100+ published versions dating back years) | 58,559,996/week | `github.com/recharts/recharts` | SUS | Flagged — see note below |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** `recharts` — the automated check flags "too-new" based on the *latest published version's* release date (2026-07-25), not the package's overall age or legitimacy. 58.5M weekly downloads, a canonical GitHub org (`recharts/recharts`), and a version history beginning at `0.1.0` are strong legitimacy signals that the heuristic doesn't weigh. **Per protocol this is still gated behind a `checkpoint:human-verify` task before `npm install recharts`** — the planner must insert one, even though the underlying signals indicate this is almost certainly a false positive on the "too-new" heuristic (it is measuring recency of the latest patch release, which is expected for an actively maintained library, not recency of package creation).

*The package name `recharts` was recalled from training knowledge before verification, so per the package-name provenance rule it is tagged `[ASSUMED]` in the Standard Stack table above despite the registry check passing on existence/downloads/repo — only an `OK` verdict combined with an authoritative-source origin earns `[VERIFIED]` for the package name itself.*

## Architecture Patterns

### System Architecture Diagram

```
Trade Bar (frontend)                  Positions Table / Heatmap / P&L chart
      │  ticker, qty, side                     ▲  positions[], cash, total_value,
      ▼  POST /api/portfolio/trade              │  unrealized P&L                  ▲ snapshots[]
┌─────────────────────────────────────────────────────────────────────────┐  GET /api/portfolio/history
│                     app/portfolio/router.py                             │──────────────┐
│                                                                         │              │
│  1. Validate request (ticker format, quantity > 0, side)                │              │
│  2. Look up current price from PriceCache.get(ticker) — reject if None  │              │
│  3. Load current position + cash_balance (SELECT)                       │              │
│  4. Compute new position (weighted avg cost) / new cash_balance         │              │
│  5. Validate: buy needs cash >= cost; sell needs qty >= sell_qty        │              │
│     -> reject outright (400) here, before any write, if invalid         │              │
│  6. conn.execute("BEGIN")                                               │              │
│     UPSERT positions, INSERT trades, UPDATE users_profile.cash_balance, │              │
│     INSERT portfolio_snapshots (post-trade snapshot)                    │              │
│     conn.execute("COMMIT")  [rollback on exception]                     │              │
│  7. await market_source.add_ticker(ticker)  -- extend active ticker set │              │
└─────────────────────────────────────────────────────────────────────────┘              │
                                          │                                               │
                                          ▼                                               │
                                  SQLite (positions, trades,                              │
                                  users_profile, portfolio_snapshots)  ◀────────────┐      │
                                          ▲                                         │      │
                                          │ single INSERT every 30s                 │      │
                          ┌───────────────────────────────┐                        │      │
                          │  _snapshot_loop() background   │                        │      │
                          │  task, started in lifespan()   │────────────────────────┘      │
                          │  (D-04): reads cash + positions│                               │
                          │  + PriceCache, writes a row    │                               │
                          └───────────────────────────────┘                               │
                                                                                            │
GET /api/portfolio  ───────────────────────────────────────────────────────────────────────┘
  reads cash_balance + positions (SELECT) + PriceCache.get() per ticker,
  computes unrealized P&L per position and portfolio total_value
```

### Recommended Project Structure
```
backend/app/portfolio/
├── __init__.py          # exports create_portfolio_router
├── router.py            # GET /api/portfolio, POST /api/portfolio/trade, GET /api/portfolio/history
├── trades.py            # execute_trade(conn, cache, ticker, side, quantity) -> TradeResult | TradeError
├── valuation.py         # position_view(), compute_total_value() -- shared by router + snapshot task
└── snapshots.py         # start_snapshot_task(app, conn_getter, cache), record_snapshot()

backend/tests/portfolio/
├── __init__.py
├── test_trades.py       # weighted avg cost, insufficient cash/shares, fractional quantities
├── test_router.py       # HTTP-level: status codes, response shapes (mirrors tests/watchlist/test_router.py)
└── test_snapshots.py    # dual-trigger recording, empty-history behavior

frontend/components/
├── PositionsTable.tsx   # UI-06, mirrors WatchlistPanel row/selection pattern
├── PortfolioHeatmap.tsx # UI-04, Recharts Treemap
├── PnlChart.tsx         # UI-05, lightweight-charts, mirrors PriceChart.tsx
└── TradeBar.tsx         # UI-07
```

### Pattern 1: Explicit Transaction for Multi-Statement Trade Writes
**What:** Because the shared connection is opened with `autocommit=True` [VERIFIED: `backend/app/db/connection.py:51` — `conn = sqlite3.connect(str(path), check_same_thread=False, autocommit=True)`], `Connection.commit()`/`rollback()` are no-ops and each `execute()` commits independently unless statements are wrapped in explicit SQL `BEGIN`/`COMMIT` [CITED: docs.python.org/3/library/sqlite3.html — "True: Use SQLite's autocommit mode. commit() and rollback() have no effect in this mode."].
**When to use:** Any code path that writes to more than one table as one logical unit — trade execution (`positions` + `trades` + `users_profile` + `portfolio_snapshots`) is the only such path in this phase.
**Example:**
```python
# Source: pattern derived from docs.python.org/3/library/sqlite3.html
#         autocommit semantics + backend/app/db/connection.py:51 (autocommit=True)
def execute_trade(conn: sqlite3.Connection, ticker: str, side: str, quantity: float, price: float) -> None:
    conn.execute("BEGIN")
    try:
        # ... UPSERT positions, INSERT trades, UPDATE users_profile, INSERT portfolio_snapshots ...
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
```
**Why this is also the serialization mechanism:** No `await` occurs between `BEGIN` and `COMMIT` (the SQLite calls are synchronous, never `asyncio.to_thread`-wrapped, consistent with every other DB call in this codebase — `watchlist/router.py` does the same). On a single-threaded asyncio event loop, a coroutine only yields control at an `await` — so the 30s snapshot task's `asyncio.sleep(30)` loop cannot interleave a read/write in the middle of a trade's `BEGIN...COMMIT` block, and vice versa [CITED: docs.python.org/3/library/asyncio-dev.html — cooperative single-threaded scheduling]. This resolves the write-serialization concern in `.planning/STATE.md` without an `asyncio.Lock`.

### Pattern 2: Weighted-Average Cost, No Zero-Quantity Special Case
**What:** `new_avg_cost = (old_qty * old_avg_cost + buy_qty * price) / (old_qty + buy_qty)`. When `old_qty == 0` (position previously sold to zero, or first-ever buy with `INSERT OR IGNORE`-style default), the first term vanishes and `new_avg_cost` reduces exactly to `price` — the correct value for a freshly opened position, with the same code path.
**When to use:** Every BUY. Sells never change `avg_cost` (only `quantity` and `updated_at`); `avg_cost` reflects the cost basis of currently-held shares.
**Example:**
```python
# Source: standard weighted-average-cost-basis formula, no citation needed
# (elementary financial arithmetic, not a library API)
def new_position_after_buy(old_qty: float, old_avg_cost: float, buy_qty: float, price: float) -> tuple[float, float]:
    new_qty = old_qty + buy_qty
    new_avg_cost = (old_qty * old_avg_cost + buy_qty * price) / new_qty
    return new_qty, new_avg_cost
```

### Pattern 3: Shared Valuation Function (DRY across GET /api/portfolio, trade response, and snapshot task)
**What:** One function computes `total_value = cash_balance + sum(qty * current_price for each position with qty > 0)`, with a documented fallback when `PriceCache.get(ticker)` returns `None` (see Common Pitfalls).
**When to use:** `GET /api/portfolio`, the post-trade response, and both snapshot triggers (30s task and post-trade write) must all agree on the exact same total-value number at the same instant — computing it three different ways risks the P&L chart and header disagreeing with the positions table.
**Example:**
```python
# Source: derived from existing PriceCache API (backend/app/market/cache.py)
def compute_total_value(conn: sqlite3.Connection, cache: PriceCache, user_id: str = "default") -> float:
    cash = conn.execute(
        "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
    ).fetchone()[0]
    rows = conn.execute(
        "SELECT ticker, quantity, avg_cost FROM positions WHERE user_id = ? AND quantity > 0",
        (user_id,),
    ).fetchall()
    holdings_value = sum(
        qty * (cache.get_price(ticker) or avg_cost)  # fallback: no price tick yet
        for ticker, qty, avg_cost in rows
    )
    return cash + holdings_value
```

### Pattern 4: Active-Ticker-Set Extension on Trade
**What:** After a successful BUY, call `await market_source.add_ticker(ticker)` — identical to the call `watchlist/router.py:94` already makes on `POST /api/watchlist`. `add_ticker()` is documented as "No-op if already present" [VERIFIED: `backend/app/market/interface.py:51-55`, quoted verbatim: `"""Add a ticker to the active set. No-op if already present. The next update cycle will include this ticker."""`], so it is always safe to call unconditionally on every successful buy, regardless of whether the ticker was already on the watchlist.
**When to use:** Every successful BUY trade (not sells — a sell never needs to *add* tracking).
**Why it matters:** This is the mechanism that satisfies the phase note "Opening a position must extend the active ticker set so a held ticker keeps streaming after it leaves the watchlist" — `get_active_tickers()` (`backend/app/db/connection.py:72-85`) already unions watchlist and open positions for use at *startup*, but the market source's runtime tracked-ticker set is a separate in-memory structure that only changes via explicit `add_ticker()`/`remove_ticker()` calls — the DB union alone does not make a newly-bought, not-watchlisted ticker start streaming.

### Pattern 5: Background Snapshot Task Lifecycle
**What:** Mirror the existing `SimulatorDataSource` task-lifecycle pattern — `asyncio.create_task(_snapshot_loop(), name="portfolio-snapshot-loop")` in `lifespan()`, stored on `app.state`, cancelled and awaited (catching `asyncio.CancelledError`) on shutdown [VERIFIED: `backend/app/market/simulator.py` — `grep` confirms `self._task = asyncio.create_task(self._run_loop(), name="simulator-loop")` at line 229 and `except asyncio.CancelledError:` at line 237].
**When to use:** The 30s snapshot recorder, started unconditionally at app startup per D-04.
**Example:**
```python
# Source: pattern mirrored from backend/app/market/simulator.py start()/stop()
async def _snapshot_loop(get_conn, cache, interval: float = 30.0) -> None:
    while True:
        await asyncio.sleep(interval)
        conn = get_conn()
        record_snapshot(conn, compute_total_value(conn, cache))
```

### Anti-Patterns to Avoid
- **Clamping trade quantity to available cash/shares:** PORT-03 explicitly forbids this — reject the entire trade with an error, never partially fill.
- **Wrapping SQLite calls in `asyncio.to_thread()` "for safety":** would break the natural serialization described in Pattern 1 by introducing an `await` mid-transaction, re-opening the interleaving risk the explicit transaction was designed to close. The Massive REST client uses `to_thread` because it's a *real* blocking network call; local SQLite writes are fast enough that the existing codebase convention (synchronous, direct) is correct as-is.
- **Recomputing total_value with a different formula in three places:** use Pattern 3's single shared function.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Treemap layout (squarified rectangles sized by weight) | A custom `d3-hierarchy`/manual rectangle-packing algorithm | `recharts` `<Treemap>` | Squarified treemap layout is a nontrivial algorithm (Bruls et al.) with real edge cases (near-zero-weight positions, single-item treemaps); Recharts ships this plus tooltip/responsive-sizing for free, and PLAN.md already blesses the library |
| SQL transaction management | Manual dirty-flag / retry logic around `conn.commit()` | Explicit `BEGIN`/`COMMIT`/`ROLLBACK` SQL statements (Pattern 1) | `conn.commit()` is a documented no-op under `autocommit=True`; reaching for a custom retry/flag mechanism instead of the SQL-level primitive the sqlite3 docs describe is solving an already-solved problem the wrong way |
| Portfolio total value across 3 call sites | 3 separate ad-hoc SQL + arithmetic blocks | One `compute_total_value()` shared function (Pattern 3) | Divergent rounding or fallback behavior between the header, positions table, and P&L chart is a subtle, hard-to-notice bug class |

**Key insight:** The domain-specific pieces this phase must genuinely write from scratch are small and well-scoped (weighted-average-cost math, transaction wrapping, validation ordering) — everything else has either an existing in-repo pattern to mirror (routers, background tasks, SSE-consuming components) or a blessed library (Recharts for the one chart type Lightweight Charts can't do).

## Common Pitfalls

### Pitfall 1: `autocommit=True` Silently Allows Partial Trade Application
**What goes wrong:** A trade handler that calls `conn.execute(...)` three times (positions, trades, cash) without explicit `BEGIN`/`COMMIT` will have each statement commit independently. If the process crashes or an exception is raised after the `positions` UPDATE but before the `users_profile` UPDATE, the user's shares increase but their cash never decreases — a real, silent data-integrity bug directly violating PORT-03's "nothing is partially filled" guarantee.
**Why it happens:** Training-data intuition about Python's `sqlite3` module assumes the pre-3.12 default (`isolation_level`-based implicit transactions), which auto-opens a transaction before the first DML statement. `autocommit=True` (opted into by this codebase) is a fundamentally different, newer mode where that assumption is false.
**How to avoid:** Every trade write path uses Pattern 1's explicit `BEGIN`/`COMMIT`, wrapped in `try/except` with `ROLLBACK` on failure.
**Warning signs:** A test that kills the process (or raises) mid-trade and finds an inconsistent DB state (position updated, cash not); code review sees three `conn.execute()` calls for a trade with no `BEGIN` visible anywhere in the diff.

### Pitfall 2: Float-Precision False Rejections/Acceptances on Sell Quantity
**What goes wrong:** Fractional share quantities stored as SQLite `REAL` (IEEE 754 double) accumulate float drift across repeated buy/sell cycles. A sell request for "all of it" (e.g., client sends `quantity=1.1` after a prior buy of `1.1`) can fail an exact `sell_qty <= held_qty` comparison by a few ULPs, incorrectly rejecting a legitimate full-close sell — or, in the other direction, a position left at `quantity=1e-16` after a "full" sell still satisfies `quantity > 0` and lingers in the active ticker set / positions table forever.
**Why it happens:** IEEE 754 double arithmetic is not exact for most decimal fractions; this is a well-known class of bug in any system storing money/share quantities as floating point rather than fixed-point/decimal.
**How to avoid:** Use a small epsilon (e.g. `1e-9`) for sell-sufficiency comparisons (`sell_qty <= held_qty + EPSILON`), and round `quantity`/`avg_cost` to a fixed number of decimal places (e.g. 8) after every write, mirroring the existing `PriceCache.update()` pattern of `round(price, 2)` [VERIFIED: `backend/app/market/cache.py:36-37`, quoted: `price=round(price, 2), previous_price=round(previous_price, 2)`].
**Warning signs:** A test that buys then sells the exact same fractional quantity and expects the position to disappear from `get_active_tickers()`, but it doesn't; flaky test failures that only reproduce with specific fractional values.

### Pitfall 3: Trading a Ticker With No Cached Price
**What goes wrong:** A user (or, in a future phase, the LLM) submits a trade for a ticker that has never been tracked (`PriceCache.get(ticker)` returns `None`) — e.g., typed directly into the trade bar without first adding it to the watchlist. "Market order, instant fill at current price" has no price to fill at.
**Why it happens:** The trade bar (UI-07) does not restrict its ticker field to watchlist entries; PLAN.md doesn't explicitly say whether trading requires the ticker to already be tracked.
**How to avoid:** Reject with 400 and a clear message ("no current price available for {ticker} — add it to your watchlist first") when `PriceCache.get(ticker) is None`, rather than attempting to call `add_ticker()` and wait for the next tick (which would make "instant fill" a lie for up to 500ms–15s depending on data source). **This is a design call not covered by CONTEXT.md — flagged in Open Questions below for confirmation during planning.**
**Warning signs:** A trade silently uses `price=0` or throws an unhandled `TypeError`/`NoneType` error deep in valuation math instead of a clean 400 at the API boundary.

### Pitfall 4: Recharts / Lightweight Charts Rendering During Next.js Static Export Prerender
**What goes wrong:** Both `Treemap` (Recharts, uses `ResizeObserver`/DOM measurement) and `lightweight-charts` (`createChart`, direct canvas DOM API) throw or no-op if evaluated during Next.js's static-export build-time prerender pass rather than in the browser.
**Why it happens:** `output: 'export'` prerenders every page at build time in a Node environment with no DOM; any component that touches `window`/`document`/canvas APIs at module-eval or render time (not inside `useEffect`) breaks the build.
**How to avoid:** Follow the exact pattern already established in `PriceChart.tsx` — `"use client"` directive, all chart-library calls inside `useEffect` (never at top-level render), refs for chart/series instances. `PositionsTable.tsx` (a plain table, no chart library) does not need this guard.
**Warning signs:** `npm run build` fails with a DOM-API-undefined error that doesn't reproduce under `npm run dev`.

### Pitfall 5: Duplicate Near-Simultaneous Snapshots
**What goes wrong:** If a trade happens to execute within the same tick as the 30s background task's write, two `portfolio_snapshots` rows land within milliseconds of each other.
**Why it happens:** Two independent triggers (D-04: always-on 30s cadence, plus post-trade) with no deduplication.
**How to avoid:** This is explicitly the intended, accepted design per PLAN.md §7 ("Recorded every 30 seconds by a background task, and immediately after each trade execution") — do **not** add deduplication logic; the P&L chart simply draws two points close together, which is harmless. Flagging only so it isn't "fixed" as a perceived bug during implementation.
**Warning signs:** N/A — this is expected behavior, not a defect.

## Code Examples

### Trade Request Validation (Pydantic, mirrors existing `AddTickerRequest`)
```python
# Source: pattern mirrored from backend/app/watchlist/router.py:23-34
from typing import Literal
from pydantic import BaseModel, Field, field_validator
from app.market.interface import normalize_ticker

class TradeRequest(BaseModel):
    ticker: str = Field(min_length=1)
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0)

    @field_validator("ticker")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return normalize_ticker(value)
```
`side: Literal["buy", "sell"]` matches the schema's `CHECK (side IN ('buy', 'sell'))` constraint verbatim [VERIFIED: `backend/app/db/schema.sql:32`, quoted: `side TEXT NOT NULL CHECK (side IN ('buy', 'sell'))`].

### Recharts Treemap with Custom Cell Coloring (P&L-colored, weight-sized)
```typescript
// Source: Context7 /recharts/recharts — CustomContentTreemap pattern
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
Each node's `plColor` should be computed client-side from `--color-up`/`--color-down` tokens (already defined in `frontend/app/globals.css`) based on that position's unrealized P&L sign — not from Recharts' default palette, to stay consistent with the project's green/red P&L convention used everywhere else (watchlist flash, arrows).

### Explicit-Transaction Trade Execution Skeleton
```python
# Source: pattern combines docs.python.org/3/library/sqlite3.html autocommit
#         semantics with backend/app/db/connection.py conventions
def execute_trade(conn, cache, ticker: str, side: str, quantity: float) -> dict:
    price = cache.get_price(ticker)
    if price is None:
        raise TradeError(400, f"No current price available for {ticker}")

    row = conn.execute(
        "SELECT quantity, avg_cost FROM positions WHERE user_id='default' AND ticker=?", (ticker,)
    ).fetchone()
    old_qty, old_avg_cost = (row[0], row[1]) if row else (0.0, 0.0)
    cash = conn.execute("SELECT cash_balance FROM users_profile WHERE id='default'").fetchone()[0]

    if side == "buy":
        cost = quantity * price
        if cost > cash + 1e-9:
            raise TradeError(400, "Insufficient cash")
        new_qty = old_qty + quantity
        new_avg_cost = (old_qty * old_avg_cost + quantity * price) / new_qty
        new_cash = cash - cost
    else:  # sell
        if quantity > old_qty + 1e-9:
            raise TradeError(400, "Insufficient shares")
        new_qty = old_qty - quantity
        new_avg_cost = old_avg_cost  # unchanged on sell
        new_cash = cash + quantity * price

    conn.execute("BEGIN")
    try:
        conn.execute(
            "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
            "VALUES (?, 'default', ?, ?, ?, ?) "
            "ON CONFLICT(user_id, ticker) DO UPDATE SET quantity=excluded.quantity, "
            "avg_cost=excluded.avg_cost, updated_at=excluded.updated_at",
            (uuid.uuid4().hex, ticker, round(new_qty, 8), round(new_avg_cost, 8), now_iso),
        )
        conn.execute(
            "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
            "VALUES (?, 'default', ?, ?, ?, ?, ?)",
            (uuid.uuid4().hex, ticker, side, quantity, price, now_iso),
        )
        conn.execute("UPDATE users_profile SET cash_balance=? WHERE id='default'", (new_cash,))
        conn.execute(
            "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) VALUES (?, 'default', ?, ?)",
            (uuid.uuid4().hex, new_cash + new_qty * price + _other_positions_value, now_iso),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return {"ticker": ticker, "side": side, "quantity": quantity, "price": price}
```
Note: `ON CONFLICT(user_id, ticker) DO UPDATE` (SQLite `UPSERT` syntax) relies on the existing `UNIQUE (user_id, ticker)` constraint [VERIFIED: `backend/app/db/schema.sql:25`, quoted: `UNIQUE (user_id, ticker)`] and is the idiomatic single-statement way to insert-or-update a position, avoiding a separate SELECT-then-branch for insert vs. update.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `sqlite3.connect()` default `isolation_level` (implicit transaction on first DML) | `autocommit=True`/`False` explicit parameter | Python 3.12 (Oct 2023) | Any training-data-derived assumption about Python sqlite3 transaction behavior for code written against `autocommit=True` connections is likely wrong unless explicitly re-verified — this project already opted into the new mode |

**Deprecated/outdated:**
- `isolation_level`-based transaction control: still works but the docs recommend `autocommit` for new code [CITED: docs.python.org/3/library/sqlite3.html]; this project already uses `autocommit=True`, so this note is informational only — no migration needed, just don't reintroduce `isolation_level` assumptions.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|----------------|
| A1 | `recharts` is the correct/intended package name (vs. e.g. a scoped variant) | Standard Stack | Low — registry lookup confirmed existence, 58M weekly downloads, canonical GitHub org; the only reason this is tagged ASSUMED is the provenance rule (name recalled from training before verification), not any doubt about correctness |
| A2 | Trading a ticker with no cached price should be rejected (400) rather than auto-added-and-awaited | Common Pitfalls #3 | Medium — if the intended UX is "trade bar can buy anything, auto-subscribing it," a 400 rejection is the wrong behavior; needs explicit confirmation since CONTEXT.md's D-01–D-08 don't cover this case |
| A3 | HTTP 400 (not 404 or 422) is the right status code for insufficient-cash/insufficient-shares rejections | Code Examples | Low — 400 is consistent with the watchlist router's error-status conventions (409/404), and PORT-03 only specifies "rejected outright," not a status code; a plan reviewer could reasonably pick 422 instead |
| A4 | `quantity`/`avg_cost` should be rounded to 8 decimal places on write | Common Pitfalls #2 | Low — the specific precision (8 vs 6 vs unrounded) is a judgment call; any reasonable fixed precision resolves the float-drift issue, 8 was chosen to comfortably exceed typical fractional-share precision without introducing new rounding errors |

**If this table is empty:** N/A — see entries above.

## Open Questions

1. **Should a trade for a never-tracked ticker (no cached price) be rejected, or auto-subscribed with a wait?**
   - What we know: PLAN.md specifies "instant fill at current price"; the watchlist and positions are the only two ways a ticker currently enters the active tracked set.
   - What's unclear: Whether the trade bar is expected to work for arbitrary tickers not yet on the watchlist.
   - Recommendation: Reject with 400 (Pitfall 3) — simplest, matches "instant fill" literally, and is trivially reversible later (relax to auto-add-and-poll if needed). Planner should confirm this reading of PLAN.md is acceptable before locking it into the plan.

2. **Exact wording/columns for the trade error response body.**
   - What we know: PORT-03 requires a "clear error"; the watchlist router uses FastAPI's default `{"detail": "..."}` shape via `HTTPException`.
   - What's unclear: Whether the frontend trade bar needs a machine-readable error code (e.g., `"insufficient_cash"`) in addition to the human-readable detail string, for UI-specific handling (e.g., disabling the submit button vs. showing a toast).
   - Recommendation: Start with `HTTPException(status_code=400, detail="...")` matching existing convention; add a structured `error_code` field only if the plan's UI design calls for differentiated handling.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|--------------|-----------|---------|----------|
| Python | Backend runtime | ✓ | 3.14.6 [VERIFIED: `uv run python --version`] | — |
| SQLite (stdlib bundled) | Trade/snapshot persistence | ✓ | 3.53.1 [VERIFIED: `sqlite3.sqlite_version`] | — |
| uv | Backend package management | ✓ | 0.11.32 [VERIFIED: `uv --version`] | — |
| Node.js | Frontend build | ✓ | v24.16.0 [VERIFIED: `node --version`] | — |
| npm | Frontend package install | ✓ | 11.13.0 [VERIFIED: `npm --version`] | — |
| `recharts` (npm) | UI-04 heatmap | not yet installed | 3.10.1 available on registry | none needed — installation is a plan task, not a missing environment dependency |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** none — `recharts` is simply not yet installed, which is expected (it's this phase's job to add it).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.0+, pytest-asyncio 0.24.0+ [VERIFIED: backend/pyproject.toml] |
| Config file | `backend/pyproject.toml` `[tool.pytest.ini_options]` (testpaths=["tests"], asyncio_mode="auto") |
| Quick run command | `uv run --extra dev pytest tests/portfolio -v` |
| Full suite command | `uv run --extra dev pytest -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|-------------|
| PORT-01 | GET /api/portfolio returns positions/cash/total_value/unrealized P&L | unit + HTTP | `pytest tests/portfolio/test_router.py -x` | ❌ Wave 0 |
| PORT-02 | POST /api/portfolio/trade fills instantly, fractional quantities work | unit + HTTP | `pytest tests/portfolio/test_trades.py -x` | ❌ Wave 0 |
| PORT-03 | Buy over cash / sell over quantity rejected outright, no partial fill | unit | `pytest tests/portfolio/test_trades.py::TestTradeValidation -x` | ❌ Wave 0 |
| PORT-04 | Snapshots every 30s + post-trade; GET /api/portfolio/history | unit + HTTP | `pytest tests/portfolio/test_snapshots.py -x` | ❌ Wave 0 |
| TEST-01 | Trade execution, P&L math, insufficient cash/shares edge cases | unit | `pytest tests/portfolio -v` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run --extra dev pytest tests/portfolio -v`
- **Per wave merge:** `uv run --extra dev pytest -v` (full backend suite)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/portfolio/__init__.py` — new test package (mirrors `tests/watchlist/`)
- [ ] `backend/tests/portfolio/test_trades.py` — covers PORT-02, PORT-03, TEST-01 (weighted-avg-cost math, insufficient cash/shares, fractional quantities, zero-quantity-reopen case from Pattern 2)
- [ ] `backend/tests/portfolio/test_router.py` — covers PORT-01, PORT-02 at the HTTP layer, mirrors `tests/watchlist/test_router.py`'s `FakeMarketSource` + `initialized_db` fixture pattern
- [ ] `backend/tests/portfolio/test_snapshots.py` — covers PORT-04 dual-trigger and empty-history (`GET /api/portfolio/history` with zero rows)
- [ ] No new fixtures needed in `backend/tests/conftest.py` — `initialized_db`, `seeded_cache`, and `client` fixtures already exist and cover this phase's needs; a `_insert_position()` test helper (mirrors `tests/watchlist/test_router.py:43-48`) should be added locally to the new test files, not conftest, since it's portfolio-specific

*Frontend unit tests (TEST-04) are explicitly assigned to Phase 3 per `.planning/REQUIREMENTS.md` traceability table — no frontend test framework gap to fill in this phase.*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|----------------|---------|--------------------|
| V2 Authentication | No | Single hardcoded `user_id="default"`, no login — explicitly out of scope per `.planning/REQUIREMENTS.md` Out of Scope table |
| V3 Session Management | No | No sessions exist in this app |
| V4 Access Control | No | Single-user app; no authorization boundaries to enforce |
| V5 Input Validation | Yes | Pydantic `TradeRequest` (Code Examples) — `quantity: float = Field(gt=0)` rejects zero/negative at the framework boundary before any business logic runs; ticker normalization/regex mirrors `AddTickerRequest`'s existing `_TICKER_PATTERN = re.compile(r"^[A-Z.\-]+$")` [VERIFIED: `backend/app/watchlist/router.py:20`] |
| V6 Cryptography | No | No secrets, tokens, or cryptographic operations in this phase's scope |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|------------------------|
| SQL injection via ticker/quantity in trade request | Tampering | Parameterized queries throughout (already the established pattern — every existing query in `connection.py`/`watchlist/router.py` uses `?` placeholders, never string interpolation); continue this convention for all new portfolio queries |
| Float/precision manipulation to bypass insufficient-cash check | Tampering | Epsilon-tolerant comparisons (Pitfall 2) combined with server-side-only validation (V5 above) — the client never supplies `cash_balance` or `avg_cost`, only `ticker`/`side`/`quantity`, so there is no client-controlled input that can directly forge a passing balance check |
| Race between two concurrent trade requests reading stale cash before either commits | Tampering / Repudiation (double-spend-style) | Resolved by Pattern 1 — the explicit `BEGIN`/`COMMIT` with no intervening `await`, combined with the single-threaded event loop, means a second trade request's `SELECT cash_balance` cannot execute until the first trade's transaction has fully committed (its own `execute()` calls block the loop synchronously) |

## Sources

### Primary (HIGH confidence — direct code reads this session)
- `backend/app/db/connection.py` — `autocommit=True` connection setup, `get_active_tickers()`, `ticker_has_open_position()`
- `backend/app/db/schema.sql` — `positions`, `trades`, `portfolio_snapshots`, `users_profile` table definitions
- `backend/app/db/seed.py` — default seed values (`DEFAULT_USER_ID = "default"`, `DEFAULT_CASH_BALANCE = 10000.0`)
- `backend/app/watchlist/router.py` — Pydantic request validation pattern, router factory pattern, ticker normalization regex
- `backend/app/market/interface.py`, `cache.py`, `models.py`, `simulator.py`, `failover.py` — `MarketDataSource` lifecycle, `PriceCache` API, background-task pattern
- `backend/app/main.py` — `lifespan()` wiring pattern
- `frontend/app/page.tsx`, `WatchlistPanel.tsx`, `PriceChart.tsx`, `usePriceStream.ts`, `Sparkline.tsx`, `globals.css` — `selectedTicker` state pattern, chart/SSE conventions, theme tokens
- `backend/tests/conftest.py`, `backend/tests/watchlist/test_router.py` — existing test fixture/pattern conventions

### Secondary (MEDIUM confidence)
- Context7 `/recharts/recharts` — Treemap `content` custom-renderer example, `ResponsiveContainer` child-component list, LineChart/Tooltip composition pattern
- docs.python.org `sqlite3` module documentation (fetched this session via WebFetch) — `autocommit` parameter semantics, `executescript()` behavior under autocommit
- npm registry (`npm view recharts ...`) — version 3.10.1, React 19 peer dependency range, 58.5M weekly downloads, `github.com/recharts/recharts` repo URL

### Tertiary (LOW confidence)
- General asyncio cooperative-scheduling model (single-threaded event loop, task switches only at `await`) — well-established Python semantics, not re-verified against docs.python.org this session beyond general familiarity; treated as CITED rather than VERIFIED for that reason

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — recharts existence/version/peer-deps confirmed live against npm registry; lightweight-charts reuse confirmed from already-installed `package.json`
- Architecture: HIGH — trade-transaction and serialization patterns derived directly from reading `connection.py`'s actual connection parameters plus official Python docs, not assumed from training data
- Pitfalls: HIGH — the `autocommit=True` pitfall is the single most load-bearing finding in this research and was independently verified against official documentation, not left as a training-data assumption

**Research date:** 2026-08-23
**Valid until:** 30 days (stable domain — SQLite/Python sqlite3 semantics and the existing codebase patterns are not fast-moving; recharts version pin should be re-checked if planning is delayed past ~30 days)
