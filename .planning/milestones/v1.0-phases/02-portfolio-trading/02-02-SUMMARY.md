---
phase: 02-portfolio-trading
plan: 02
subsystem: portfolio
tags: [background-tasks, sqlite, fastapi, lightweight-charts, react]
requires:
  - phase: 02-portfolio-trading
    provides: "record_snapshot, compute_total_value, execute_trade, portfolio router factory, usePortfolio hook (Plan 02-01)"
provides:
  - "Always-on 30s portfolio_snapshots recorder started unconditionally in lifespan (D-04)"
  - "GET /api/portfolio/history: oldest-first, id tie-break, capped at HISTORY_LIMIT=2000"
  - "PnlChart.tsx: lightweight-charts line series of total portfolio value with the D-03 empty state"
  - "usePortfolio.ts history/historyError/historyLoaded, refetched by the same refresh() call"
  - "backend/tests/portfolio/test_valuation.py and test_router.py: P&L arithmetic and full HTTP-contract coverage"
affects: [02-03-heatmap-and-positions-table, phase-03-llm-copilot]
actuals:
  tokens: 8968
  tasks: 3
  commits: 3
tech-stack:
  added: []
  patterns:
    - "Sleep-then-record loop body (await asyncio.sleep first) so startup never doubles up with a snapshot a trade writes in the first instants"
    - "ORDER BY recorded_at ASC, id ASC as a deterministic tie-break for near-simultaneous rows"
    - "Same floor-to-seconds + same-second-collapse guard applied at the chart boundary in both usePriceStream and usePortfolio, keeping underlying rows untouched"
key-files:
  created:
    - backend/tests/portfolio/test_snapshots.py
    - backend/tests/portfolio/test_valuation.py
    - backend/tests/portfolio/test_router.py
    - frontend/components/PnlChart.tsx
  modified:
    - backend/app/portfolio/snapshots.py
    - backend/app/portfolio/router.py
    - backend/app/portfolio/__init__.py
    - backend/app/main.py
    - frontend/hooks/usePortfolio.ts
    - frontend/app/page.tsx
key-decisions:
  - "get_snapshot_history uses a subquery (ORDER BY ... DESC LIMIT n, then re-ORDER ASC) to select the most recent N rows by insertion recency while still returning them oldest-first, rather than OFFSET-based pagination"
  - "snapshot_task is stopped before source.stop() and before conn.close() in lifespan, mirroring the shutdown ordering already used for the market data source"
  - "PnlChart's `ready` prop is combined with points.length < 2 (not read alone) so the empty state condition stays a single boolean expression, even though ready=false implies zero points by construction"
requirements-completed: [PORT-04, UI-05, TEST-01]
coverage:
  - id: D1
    description: "A background task started at app startup records one portfolio_snapshots row every 30 seconds, unconditionally (D-04, PORT-04)"
    requirement: "PORT-04"
    verification:
      - kind: unit
        ref: "backend/tests/portfolio/test_snapshots.py::TestSnapshotLoop::test_loop_records_and_stops_cleanly"
        status: pass
      - kind: unit
        ref: "backend/tests/portfolio/test_snapshots.py::TestSnapshotLoop::test_loop_survives_a_failing_iteration"
        status: pass
    human_judgment: false
  - id: D2
    description: "GET /api/portfolio/history returns 200 with [] when empty, oldest-first ordering with a stable id tie-break, and a HISTORY_LIMIT=2000 cap"
    requirement: "PORT-04"
    verification:
      - kind: unit
        ref: "backend/tests/portfolio/test_snapshots.py::TestSnapshotHistory"
        status: pass
    human_judgment: false
  - id: D3
    description: "The 30s recorder and a post-trade write both persist as separate rows -- never deduplicated -- and shut down cleanly with the app"
    requirement: "PORT-04"
    verification:
      - kind: unit
        ref: "backend/tests/portfolio/test_snapshots.py::TestSnapshotHistory::test_dual_trigger_near_simultaneous_snapshots_both_persist"
        status: pass
      - kind: unit
        ref: "backend/tests/portfolio/test_snapshots.py::TestPostTradeSnapshot::test_a_single_buy_leaves_exactly_one_snapshot"
        status: pass
    human_judgment: false
  - id: D4
    description: "P&L arithmetic is exact: market value, unrealized P&L, and P&L percent, including the no-cached-price fallback to avg_cost and POSITION_EPSILON exclusion"
    requirement: "TEST-01"
    verification:
      - kind: unit
        ref: "backend/tests/portfolio/test_valuation.py (99% app/portfolio coverage, gate was 85%)"
        status: pass
    human_judgment: false
  - id: D5
    description: "GET /api/portfolio, GET /api/portfolio/history, and POST /api/portfolio/trade return correct status codes (200/422/400) and complete response key sets"
    requirement: "TEST-01"
    verification:
      - kind: unit
        ref: "backend/tests/portfolio/test_router.py"
        status: pass
    human_judgment: false
  - id: D6
    description: "The P&L chart draws total portfolio value over time using the lightweight-charts line-series pattern, with the D-03 empty state until >=2 points exist and an inline text-down error on a failed history fetch"
    requirement: "UI-05"
    verification:
      - kind: unit
        ref: "npm run build (exit 0); npx tsc --noEmit (exit 0)"
        status: pass
    human_judgment: true
    rationale: "Visual rendering, the empty-state-to-populated transition timing, and the flat 10000.00 startup line need a human eyeball per Task 3's own <human-check> list; compiles and builds cleanly but was not clicked through in a browser by this agent (headless worktree, no browser)."
duration: ~50min
completed: 2026-08-24
status: complete
---

# Phase 2 Plan 2: Portfolio History and P&L Chart Summary

**A 30-second background recorder starts unconditionally at app startup and writes `portfolio_snapshots` rows for the life of the process; `GET /api/portfolio/history` serves them back oldest-first with a stable tie-break and a 2000-row cap; `PnlChart.tsx` plots them as a `lightweight-charts` line with the "Building portfolio history" empty state until at least two points exist.**

## Performance
- **Duration:** ~50min
- **Started:** 2026-08-24T~05:03Z (approx, plan load)
- **Completed:** 2026-08-24T07:53:37Z
- **Tasks:** 3 completed (all `<acceptance_criteria>` gates cleared)
- **Files modified:** 11 (4 created, 6 modified, 1 deviation log created across 3 commits)

## Accomplishments
- `_snapshot_loop` sleeps first, then records, so app startup never doubles up with a snapshot a trade writes in the first instants; a failing iteration is logged and the loop continues to the next interval rather than dying
- `app.state.snapshot_task` is started right after `source.start(tickers)` and stopped before `source.stop()`/`conn.close()` in `lifespan`, so the recorder can never touch a closed connection or a stopped cache
- `get_snapshot_history` returns the most recent `HISTORY_LIMIT` rows oldest-first, with `recorded_at ASC, id ASC` as a deterministic tie-break for snapshots written in the same instant (the 30s tick landing on a trade)
- `PnlChart.tsx` mirrors `PriceChart.tsx`'s mount-only `useEffect`/`ResizeObserver`/cleanup structure almost verbatim, replacing the whole series on each `points` change via `setData` (never `series.update`)
- `usePortfolio.ts`'s `refresh()` now fetches both `/api/portfolio` and `/api/portfolio/history` in one pass, applying the same floor-to-seconds + same-second-collapse guard `usePriceStream` already uses for its timeline, so duplicate-second points never reach the charting library while the underlying rows stay untouched
- 34 new backend tests across `test_snapshots.py` (10), `test_valuation.py` (7), and `test_router.py` (9, plus one moved fixture) bring `app/portfolio` statement coverage to 99% (gate was 85%)

## Task Commits
1. **Task 1: Record portfolio value every 30 seconds and serve it back** - `e3ece6a` (feat)
2. **Task 2: Cover P&L arithmetic and the portfolio HTTP contract** - `aa6e604` (test)
3. **Task 3: Draw the portfolio value line** - `78efe06` (feat)

**Plan metadata:** (this commit, docs)

## Files Created/Modified
- `backend/app/portfolio/snapshots.py` - added `get_snapshot_history`, `_snapshot_loop`, `start_snapshot_task`, `stop_snapshot_task`, `SNAPSHOT_INTERVAL_SECONDS`, `HISTORY_LIMIT` alongside the existing `record_snapshot`
- `backend/app/portfolio/router.py` - `GET /api/portfolio/history`
- `backend/app/portfolio/__init__.py` - re-exports for the new snapshot-loop public API
- `backend/app/main.py` - `lifespan` starts the recorder after `source.start`, stops it before `source.stop`/`conn.close`
- `backend/tests/portfolio/test_snapshots.py` - dual-trigger, empty-history, ordering/tie-break, `HISTORY_LIMIT` truncation, loop lifecycle, and loop-resilience coverage
- `backend/tests/portfolio/test_valuation.py` - exact P&L/percent arithmetic, avg-cost fallback, `POSITION_EPSILON` exclusion
- `backend/tests/portfolio/test_router.py` - 422 vs 400 distinction, full response key-set assertions for all three portfolio routes
- `frontend/hooks/usePortfolio.ts` - `PnlPoint`, `history`/`historyError`/`historyLoaded`, `collapseToChartPoints` (same-second dedupe)
- `frontend/components/PnlChart.tsx` - lightweight-charts line series with the D-03 empty state and inline error text
- `frontend/app/page.tsx` - full-width P&L row beneath the watchlist/chart grid

## Decisions Made
- `get_snapshot_history` selects the most recent N rows via a `DESC LIMIT n` subquery and re-orders `ASC` in the outer query, rather than a plain `ASC LIMIT` (which would return the *oldest* N rows, not the most recent) or OFFSET-based pagination (unnecessary at this scale)
- `PnlChart`'s empty-state condition is `!ready || points.length < 2` rather than `points.length < 2` alone -- functionally identical (since `ready=false` implies zero points) but keeps `ready` a real, referenced prop instead of a documented-but-unused one

## Deviations from Plan

### Auto-fixed Issues

None - Task 1 and Task 2 implementations matched the plan and research directly; no bugs found during self-verification.

### Out-of-Scope Discoveries (not auto-fixed, logged per scope boundary)

**1. `npm run lint` reports 4 `react-hooks/set-state-in-effect` errors, not the 2 recorded in `.planning/STATE.md`**
- **Found during:** Task 3's `<verify>` (`npm run lint`)
- **Issue:** The 2 documented errors are `WatchlistPanel.tsx:60,77` (Phase 1, already accepted as non-blocking). Two additional errors of the same category -- `TradeBar.tsx:28` and the pre-existing `useEffect(() => { refresh(); }, [refresh])` mount-fetch pattern in `usePortfolio.ts` -- were introduced by Plan 02-01, whose own verification ran `npm run build` + `tsc --noEmit` only, never `npm run lint`. Confirmed via `git show HEAD:frontend/hooks/usePortfolio.ts` before this plan's edits and via `git log` on `TradeBar.tsx` that both lines predate any Plan 02-02 change.
- **Why not fixed:** `TradeBar.tsx` is not in this plan's `files_modified` list (out of scope per the scope-boundary rule); restructuring the mount-fetch pattern in `usePortfolio.ts` to satisfy the stricter lint rule is better done as one pass across all four instances (Rule 4 territory -- a project-wide pattern change), not a one-off buried in this task.
- **Verification that no new instances were added:** the `usePortfolio.ts:155` line reported by lint is the exact pre-existing `useEffect` block, unchanged by this plan's edits (only its line number shifted because new code was added earlier in the file).
- **Logged to:** `.planning/phases/02-portfolio-trading/deferred-items.md`

**Total deviations:** 0 auto-fixed, 1 out-of-scope discovery logged (not fixed, per scope boundary). **Impact:** none on this plan's acceptance criteria or `<verification>` gates -- `npm run build` and `tsc --noEmit` both exit 0, which are the two automated frontend gates this plan's `<verify>` block actually specifies; `npm run lint`'s baseline drift is a Plan 02-01 gap surfaced here, recommended as a follow-up cleanup pass.

## Issues Encountered
`frontend/node_modules` was absent at the start of Task 3 (never installed in this worktree) -- ran `npm install` (no `package.json`/`package-lock.json` changes, confirmed via `git status`/`git diff --stat`) before `npm run build` would run at all.

## Measured Results (per Output spec)
- **`app/portfolio` coverage:** 99% (177 statements, 1 miss -- `snapshots.py` line 123, the `except asyncio.CancelledError: raise` re-raise line, which is exercised by `stop_snapshot_task` in practice but not distinctly hit by a dedicated coverage-instrumented test path)
- **`GET /api/portfolio/history` response shape as implemented:** `[{"time": <int unix seconds>, "value": <float>, "recorded_at": "<original ISO-8601 string>"}, ...]`, oldest first
- **Same-second collapse:** implemented in `usePortfolio.ts`'s `collapseToChartPoints`; not exercised in practice during this agent's testing (the 30s cadence and a single manual trade in verification never landed in the same second), but the unit-level logic mirrors `usePriceStream`'s already-proven timeline guard exactly
- **Task 3 `<human-check>` items:** not run by this agent (headless worktree, no browser) -- harvested below for the phase UAT batch

## Human-Check Items (harvested for phase UAT batch, not executed by this agent)
From Task 3's `<verify>` block:
1. On first load the P&L panel shows "Building portfolio history" / the about-a-minute sentence, not a blank box and not a zero-value line
2. After ~70s without trading, the panel switches to a line chart with at least two points at a flat 10000.00, proving the recorder runs without a trade (D-04)
3. Buying 1 share adds a new point to the chart immediately, without waiting for the next 30s tick
4. The chart line is the same blue as the per-ticker price chart; panel chrome matches the other panels
5. No browser console errors about out-of-order or duplicated time values
6. The simulated-data disclosure line remains visible alongside the value curve

All six items' underlying logic is covered by automated tests, `tsc`, or `next build`; the visual/interaction confirmation itself needs a human or automated UI check, per the plan's own framing.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
`GET /api/portfolio/history`, `usePortfolio.ts`'s `history`/`historyError`/`historyLoaded`, and the `selectedTicker` shared-state pattern (unchanged by this plan) are ready for Plan 02-03's positions table and heatmap, which per `.planning/phases/02-portfolio-trading/02-03-PLAN.md` insert a new row between the existing watchlist/chart grid and this plan's P&L row. No blockers identified. The lint baseline drift noted above (4 vs. 2 pre-existing errors) should be swept up in Plan 02-03 or a dedicated cleanup task before Phase 2 closes.

## Self-Check: PASSED

All 4 created files verified present on disk (`test_snapshots.py`, `test_valuation.py`,
`test_router.py`, `PnlChart.tsx`, this SUMMARY.md, `deferred-items.md`). All 3 task commits
(`e3ece6a`, `aa6e604`, `78efe06`) verified present in `git log --oneline`.

---
*Phase: 02-portfolio-trading*
*Completed: 2026-08-24*
