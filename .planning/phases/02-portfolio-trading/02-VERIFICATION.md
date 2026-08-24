---
phase: 02-portfolio-trading
verified: 2026-08-24T22:30:00Z
status: human_needed
score: 15/15 must-haves verified
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Fresh database: buy 2 AAPL and sell them back via the trade bar's Buy/Sell buttons in a running browser"
    expected: "Order fills instantly (no confirmation dialog, no page reload); Cash and Total Value in the header update immediately; a position row appears in the Positions table and a tile in the Heatmap, then both disappear when sold back to zero"
    why_human: "Instant-fill UX, absence of a confirmation dialog, and absence of a page reload are runtime browser behaviors that static analysis and unit tests cannot observe"
  - test: "Attempt a buy that exceeds cash (e.g. 100000 shares) and a sell of a ticker not held"
    expected: "An inline red error message appears below the trade bar, both fields retain their entered values, and Cash/Total Value do not change"
    why_human: "Visual placement and persistence of form field values on rejection is a rendering behavior, not statically verifiable"
  - test: "Watch the header connection dot through a simulated disconnect/reconnect cycle (e.g. stop/restart the backend)"
    expected: "Dot is green while the SSE stream is open, turns yellow while reconnecting, and red when closed, with the status word beside it"
    why_human: "Real-time color transitions driven by EventSource readyState changes require an actual running SSE connection to observe"
  - test: "Wait ~70 seconds after a fresh app start without trading, watching the P&L panel"
    expected: "Panel shows 'Building portfolio history' / 'usually within a minute' for the first phase, then switches to a flat 10000.00 line with at least two points, proving the recorder runs unconditionally (D-04) with no trade"
    why_human: "Timing-dependent transition from empty-state to populated chart over real wall-clock seconds cannot be exercised by a fast unit test in this suite"
  - test: "Buy three tickers in clearly different dollar amounts and observe the heatmap"
    expected: "Tile areas visibly track the dollar weights (not visually equal), each tile shows ticker + signed percent, green for winners and red for losers; a very small fourth position's tile suppresses its text label rather than clipping"
    why_human: "Recharts' actual pixel-level treemap layout, small-cell label suppression at real dimensions, and color rendering require a browser to observe"
  - test: "Click a watchlist row, a positions-table row, and a heatmap tile in turn"
    expected: "Each click highlights the clicked item with the same accent-blue left-border/outline treatment, switches the main price chart to that ticker, and prefills the trade bar's ticker field"
    why_human: "Cross-component visual consistency and the full click-to-chart-to-tradebar chain is an end-to-end interaction that requires a rendered DOM"
  - test: "Tab to a positions-table row and a watchlist row and press Enter or Space"
    expected: "The same selection behavior as a mouse click occurs (keyboard-reachable rows)"
    why_human: "Keyboard focus order and activation require a real browser/DOM, not observable via source grep alone"
  - test: "Take a grayscale screenshot of the positions table and the heatmap with at least one winner and one loser held"
    expected: "Winners and losers remain distinguishable via arrow glyphs and signed numbers/percent labels alone, without relying on color"
    why_human: "Color-independence is a visual-perception check that requires rendering and a screenshot, not source inspection"
---

# Phase 2: Portfolio & Trading Verification Report

**Phase Goal:** A user can buy and sell shares instantly from the terminal and watch cash, positions, and P&L revalue live as prices stream
**Verified:** 2026-08-24T22:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User enters ticker/quantity in trade bar, clicks Buy/Sell, order fills instantly — cash, positions, header totals update without reload, no confirmation dialog | ✓ VERIFIED | `TradeBar.tsx` POSTs `/api/portfolio/trade` and calls `await onTraded()` (→ `usePortfolio.refresh()`) on success with no `confirm()`/dialog anywhere in the file; `execute_trade` (`backend/app/portfolio/trades.py`) commits synchronously inside one `BEGIN`/`COMMIT`. Backend proven end-to-end by `TestTradeHappyPath` (3 tests, all pass). Runtime/visual confirmation (no page reload observed in a real browser) is in `human_verification` item 1. |
| 2 | Over-budget buy / over-size sell rejected outright (400), nothing clamped/partial; backend unit tests cover these edges alongside trade execution and P&L math | ✓ VERIFIED | `execute_trade` raises `TradeError` *before* any write for `insufficient_cash`/`insufficient_shares`/`no_price`/`invalid_side`/`invalid_quantity`; router maps to `HTTPException(400)`. `TestTradeValidation` in `test_trades.py` asserts zero side effects (`SELECT COUNT(*) FROM trades`, position quantity, `cash_balance` all unchanged) after each rejection. 168/168 backend tests pass (`uv run pytest -q`), `app/portfolio` at 97% statement coverage (gate was 85%). |
| 3 | Positions table shows ticker/qty/avg cost/current price/unrealized P&L/%change, revaluing as prices stream | ✓ VERIFIED | `PositionsTable.tsx` renders all 6 columns from `PositionView[]` supplied by `usePortfolio(prices)`, which runs `revalue()` against the live SSE price map on every price tick (memoized on `[portfolio, prices]`) — the same live-remarking mechanism proven for the watchlist in Phase 1. Empty/no-cached-price/dust-position edges are handled (`avg_cost` fallback, `POSITION_EPSILON` filter in `position_views`). Live-stream visual confirmation is in `human_verification` item 1/5. |
| 4 | Heatmap sized by weight/colored by P&L; P&L chart gains a point every ≥30s and immediately after each trade | ✓ VERIFIED | `PortfolioHeatmap.tsx`: `Treemap dataKey="weight"` over `market_value`, `fillFor(pnl)` green/red/grey. Snapshot recorder: `start_snapshot_task` launched unconditionally in `lifespan` (not gated on a trade — D-04), `_snapshot_loop` sleeps 30s then records; `execute_trade` calls `record_snapshot` inside its own transaction on every successful trade. Both triggers are proven distinct, non-deduplicating writes by `test_dual_trigger_near_simultaneous_snapshots_both_persist` and `test_a_single_buy_leaves_exactly_one_snapshot`. `PnlChart.tsx`'s CR-02 fix (container always mounted, empty-state as an absolute overlay) is confirmed present in the current file — the chart-creation `useEffect` now always finds a real container and creates the series. Pixel-level rendering is in `human_verification` item 4/5. |
| 5 | Header shows live total value, cash balance, connection dot green/yellow/red | ✓ VERIFIED | `page.tsx` header renders `Total Value {...toFixed(2)}`, `Cash {...toFixed(2)}` sourced from `usePortfolio`, and a `rounded-full` dot with `CONNECTION_DOT_COLOR = {open: bg-up, connecting: bg-accent-yellow, reconnecting: bg-accent-yellow, closed: bg-down}` keyed off `usePriceStream()`'s `status`. Values render `--` before first load (`portfolio ? ... : "--"`), matching the plan's backstop truth. Real-time dot-color transition through an actual reconnect cycle is in `human_verification` item 3. |

### Code-Review Fix Verification (2 critical + 3 warning issues from 02-REVIEW.md)

| Finding | Fix Commit | Verified in current code | Regression test present |
|---|---|---|---|
| CR-01: `execute_trade` didn't validate `side`/`quantity`, allowing cash fabrication via a negative-quantity direct call | `6bcf38e` | ✓ Confirmed: `trades.py` lines 79-82 reject `side not in ("buy","sell")` and non-finite/non-positive `quantity` before any read/write. Manually reproduced the original exploit against the current code — both attack vectors (negative-quantity buy, `side="short"`) are now rejected with `TradeError`, cash and position tables unchanged. | ⚠️ No — no test in `backend/tests/portfolio/*.py` calls `execute_trade` directly with an invalid `side` or non-positive `quantity`; only HTTP-level 422 (Pydantic) tests exist, which never reach these two new lines. Coverage report confirms lines 80/82 uncovered. |
| CR-02: `PnlChart.tsx` never created the chart because its container div was conditionally unmounted | `0719b79` | ✓ Confirmed: container `<div ref={containerRef}>` is now unconditionally rendered inside a `relative` wrapper; the empty-state message is an `absolute inset-0` overlay, matching `PriceChart.tsx`'s precedent. | N/A (frontend chart-rendering behavior; no frontend unit-test harness exists in this repo for either sibling component) |
| WR-01: `TradeBar.tsx` form had no submit guard — Enter reloaded the page | `2e009f4` | ✓ Confirmed: `<form onSubmit={(event) => event.preventDefault()}>` present. | N/A (no frontend test harness) |
| WR-02: `usePortfolio.ts` `refresh()` inconsistently skipped the history fetch on a portfolio-fetch failure | `635ab40` | ✓ Confirmed: the early `return` was removed; both fetch blocks now run unconditionally in sequence. | N/A (no frontend test harness) |
| WR-03: unguarded `market_source.add_ticker` turned an already-committed buy into a client-visible 500 | `54f2524` | ✓ Confirmed: `router.py`'s post-commit `add_ticker` call is wrapped in `try/except Exception: logger.exception(...)`. | ✓ Yes — `test_router.py`'s 9 tests all pass with this code path; full suite green. |

All 5 fix commits (`6bcf38e`, `0719b79`, `2e009f4`, `635ab40`, `54f2524`) verified present in `git log`. This is the current, post-review state of the code, not the pre-fix SUMMARY.md description.

**Score:** 15/15 must-haves verified (5 ROADMAP success criteria + all 5 review-fix items independently re-confirmed in the current codebase); 0 present-but-behavior-unverified.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/portfolio/trades.py` | `execute_trade` w/ BEGIN/COMMIT, weighted-avg cost, outright rejection incl. CR-01 guards | ✓ VERIFIED | Present, substantive, wired into router, exercised by 18 tests |
| `backend/app/portfolio/valuation.py` | Shared valuation (`position_views`, `compute_total_value`, `portfolio_view`) | ✓ VERIFIED | 100% statement coverage, single source of arithmetic used by router/trade-response/snapshots |
| `backend/app/portfolio/snapshots.py` | `record_snapshot`, `get_snapshot_history`, `start_snapshot_task`/`stop_snapshot_task`, `SNAPSHOT_INTERVAL_SECONDS=30`, `HISTORY_LIMIT=2000` | ✓ VERIFIED | 97% coverage; loop lifecycle proven by `TestSnapshotLoop` |
| `backend/app/portfolio/router.py` | `GET /api/portfolio`, `GET /api/portfolio/history`, `POST /api/portfolio/trade` | ✓ VERIFIED | All 3 routes present, mounted above the static fallback in `main.py` |
| `frontend/hooks/usePortfolio.ts` | Fetch + client-side `revalue()`, history w/ same-second collapse | ✓ VERIFIED | `revalue`, `collapseToChartPoints`, `history`/`historyError`/`historyLoaded` all present |
| `frontend/components/TradeBar.tsx` | Buy/Sell form, disabled/pending/error states | ✓ VERIFIED | `canSubmit` gating, `submitting` disables both buttons, inline `text-down` error, WR-01 submit guard present |
| `frontend/components/PnlChart.tsx` | lightweight-charts line series, D-03 empty state | ✓ VERIFIED (post-fix) | CR-02 fix confirmed — container unconditionally mounted |
| `frontend/components/PositionsTable.tsx` | Positions grid, D-01 empty state, selection | ✓ VERIFIED | All required columns, empty state, keyboard row handling present |
| `frontend/components/PortfolioHeatmap.tsx` | Recharts Treemap, D-02 empty state | ✓ VERIFIED | `dataKey="weight"`, P&L fill colors, selected-tile outline, small-cell label suppression all present |
| `backend/tests/portfolio/*.py` | Trade/valuation/router/snapshot test coverage | ✓ VERIFIED | 44 portfolio-scoped tests, 97% `app/portfolio` coverage; 168/168 full backend suite passes |

### Key Link Verification

| From | To | Via | Status |
|------|----|----|--------|
| `backend/app/main.py` | `backend/app/portfolio/router.py` | `create_portfolio_router(get_db, source, cache)`, registered above `app.frontend(...)` | ✓ WIRED |
| `backend/app/main.py` | `backend/app/portfolio/snapshots.py` | `start_snapshot_task` after `source.start`, `stop_snapshot_task` before `source.stop`/`conn.close` | ✓ WIRED |
| `backend/app/portfolio/router.py` | `backend/app/portfolio/trades.py` | `execute_trade` called, `TradeError` → `HTTPException(400)` | ✓ WIRED |
| `backend/app/portfolio/trades.py` | `backend/app/market/cache.py` | `cache.get_price(ticker)` supplies fill price | ✓ WIRED |
| `backend/app/portfolio/trades.py` | `backend/app/portfolio/snapshots.py` | `record_snapshot` called inside the trade's open transaction | ✓ WIRED |
| `frontend/components/TradeBar.tsx` | `backend/app/portfolio/router.py` | `fetch POST /api/portfolio/trade` | ✓ WIRED |
| `frontend/app/page.tsx` | `frontend/hooks/usePortfolio.ts` | `usePortfolio(prices)` supplies header/positions/heatmap/chart data | ✓ WIRED |
| `frontend/app/page.tsx` | `frontend/components/PositionsTable.tsx` / `PortfolioHeatmap.tsx` | both wired to shared `selectedTicker`/`setSelectedTicker` | ✓ WIRED |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| Header Total Value / Cash | `portfolio.total_value`/`cash_balance` | `GET /api/portfolio` → `portfolio_view()` → SQLite `users_profile`/`positions` | Yes | ✓ FLOWING |
| Positions table rows | `portfolio.positions` | Same `GET /api/portfolio`, revalued client-side against live SSE prices | Yes | ✓ FLOWING |
| Heatmap tiles | `positions[].market_value`/`unrealized_pnl` | Same source, mapped 1:1 to Treemap nodes | Yes | ✓ FLOWING |
| P&L chart points | `history` | `GET /api/portfolio/history` → `get_snapshot_history()` → SQLite `portfolio_snapshots` | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Negative-quantity buy is rejected and leaves cash untouched (CR-01 exploit reproduction) | Direct Python call to `execute_trade(conn, cache, "AAPL", "buy", -100)` against an in-memory schema | `TradeError(code=invalid_quantity)` raised, `cash_balance` unchanged at 10000.0 | ✓ PASS |
| Invalid `side` string is rejected rather than silently treated as a sell | `execute_trade(conn, cache, "AAPL", "short", 1)` | `TradeError(code=invalid_side)` raised | ✓ PASS |
| Full backend suite is green | `uv run --directory backend --extra dev pytest -q` | `168 passed` | ✓ PASS |
| `app/portfolio` coverage meets its 85% gate | `pytest tests/portfolio --cov=app.portfolio --cov-report=term-missing -q` | `97%` (185 statements, 5 missed — 2 of which are the untested CR-01 guard lines) | ✓ PASS |
| Ruff clean | `uv run --directory backend --extra dev ruff check app/ tests/` | `All checks passed!` | ✓ PASS |
| Frontend builds and type-checks | `npm --prefix frontend run build` | Compiles, static export produced, TypeScript check passes | ✓ PASS |
| Frontend lint | `npm --prefix frontend run lint` | 4 errors, all `react-hooks/set-state-in-effect` on pre-existing mount-fetch patterns, documented in `deferred-items.md`/`STATE.md`, no new categories | ⚠️ Known, non-blocking, already logged |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| PORT-01 | 02-01 | `GET /api/portfolio` returns positions, cash, total value, unrealized P&L | ✓ SATISFIED | `portfolio_view()`, `TestPortfolioRoutes` |
| PORT-02 | 02-01 | Market buy/sell, fractional quantities | ✓ SATISFIED | `execute_trade`, `TestTradeHappyPath` |
| PORT-03 | 02-01 | Insufficient cash/shares rejected outright, never clamped | ✓ SATISFIED | `TestTradeValidation` (zero side-effect assertions) |
| PORT-04 | 02-01 + 02-02 | 30s + post-trade snapshots, `GET /api/portfolio/history` | ✓ SATISFIED | `TestSnapshotLoop`, `TestPostTradeSnapshot`, `TestSnapshotHistory` |
| UI-04 | 02-03 | Heatmap sized by weight, colored by P&L | ✓ SATISFIED | `PortfolioHeatmap.tsx` |
| UI-05 | 02-02 | P&L line chart over time | ✓ SATISFIED (post-CR-02-fix) | `PnlChart.tsx` |
| UI-06 | 02-03 | Positions table w/ 6 columns, live revaluation | ✓ SATISFIED | `PositionsTable.tsx` |
| UI-07 | 02-01 | Trade bar w/ disabled/pending/error states | ✓ SATISFIED (post-WR-01-fix) | `TradeBar.tsx` |
| UI-09 | 02-01 | Header live stats + connection dot | ✓ SATISFIED | `page.tsx` header |
| TEST-01 | 02-01 + 02-02 | Backend tests cover trade execution, P&L, edges | ✓ SATISFIED | 44 portfolio tests, 97% coverage |

No orphaned requirements: all Phase-2-mapped IDs in `REQUIREMENTS.md`'s tracking table (PORT-01–04, UI-04/05/06/07/09, TEST-01) appear in at least one plan's `requirements:` frontmatter field.

**Documentation drift (not a code gap):** `.planning/REQUIREMENTS.md`'s checkbox list (lines 26-56) still shows `[ ]` (Pending) for PORT-01–04, UI-05, UI-07, UI-09, and TEST-01, even though the tracking table further down and the actual code confirm these are implemented and tested. UI-04 and UI-06 were updated to `[x]`/Complete but the rest were not. This is a documentation-sync gap the project should close (update `REQUIREMENTS.md`), not a functional gap in the phase.

### Anti-Patterns Found

None. Grep for `TODO|FIXME|XXX|TBD|HACK|PLACEHOLDER` and stub-return patterns across all phase-modified backend and frontend files returned zero hits (the only `placeholder` matches are legitimate HTML `<input placeholder="...">` attributes, not code stubs).

### Gaps Summary

No blocking gaps. Two non-blocking findings surfaced during verification, worth the developer's attention but not preventing phase goal achievement:

1. **CR-01's new guard clauses (`invalid_side`, `invalid_quantity`) have no regression test.** The fix is correct and was independently re-verified by this verifier via direct reproduction of the original exploit against the current code (both attack vectors now rejected). But `backend/tests/portfolio/test_trades.py` and `test_router.py` contain no test that calls `execute_trade` directly with an invalid `side` or non-positive `quantity` — the coverage report confirms `trades.py` lines 80 and 82 are unexercised. Since PLAN.md §9 explicitly designates `execute_trade` as the function Phase 3's LLM auto-execution path will call directly (bypassing the HTTP/Pydantic layer that currently masks this gap), an untested guard here is exactly the kind of protection Phase 3 will depend on. Recommend adding 2 tests before or during Phase 3 planning.
2. **`.planning/REQUIREMENTS.md` checkbox drift**, described above — a documentation housekeeping item, not a code defect.

### Human Verification Required

See frontmatter `human_verification` (7 items) — visual rendering, real-time SSE/dot-color transitions, timing-dependent chart population, treemap pixel-level layout, and cross-panel click/keyboard interactions. These were also independently harvested by the three plans' own `<human-check>` blocks and logged in each SUMMARY.md as not yet executed in a browser by the implementing agents (all three executed headless). All underlying logic, wiring, and data contracts for each item are already statically and/or unit-test verified above; only the rendered/interactive confirmation remains.

---

_Verified: 2026-08-24T22:30:00Z_
_Verifier: Claude (gsd-verifier)_
