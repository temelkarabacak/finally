---
phase: 02-portfolio-trading
plan: 01
subsystem: portfolio
tags: [trading, sqlite-transactions, fastapi, portfolio-valuation, react]
requires:
  - phase: 01-market-data-and-watchlist
    provides: PriceCache, MarketDataSource.add_ticker, watchlist router patterns, seeded schema
provides:
  - "GET /api/portfolio and POST /api/portfolio/trade behind create_portfolio_router"
  - "execute_trade: explicit BEGIN/COMMIT transaction wrapping positions + trades + cash + snapshot writes"
  - "portfolio_view/compute_total_value/position_views shared valuation used by every downstream plan"
  - "TradeBar.tsx and usePortfolio.ts frontend contracts for Plans 02-02/02-03/02-04"
  - "Header live stats (Total Value, Cash, connection dot)"
affects: [02-02-snapshots-and-pnl-chart, 02-03-heatmap-and-positions-table, phase-03-llm-copilot]
actuals:
  tokens: 10352
  tasks: 2
  commits: 3
tech-stack:
  added: []
  patterns:
    - "Explicit SQL BEGIN/COMMIT/ROLLBACK around multi-statement writes on an autocommit=True connection, with zero await between them"
    - "Weighted-average-cost formula with no zero-quantity special case"
    - "Single shared valuation function (portfolio_view/position_views/compute_total_value) consumed by the router, the trade response, and the snapshot recorder"
key-files:
  created:
    - backend/app/portfolio/__init__.py
    - backend/app/portfolio/valuation.py
    - backend/app/portfolio/trades.py
    - backend/app/portfolio/snapshots.py
    - backend/app/portfolio/router.py
    - backend/tests/portfolio/__init__.py
    - backend/tests/portfolio/test_trades.py
    - frontend/hooks/usePortfolio.ts
    - frontend/components/TradeBar.tsx
  modified:
    - backend/app/main.py
    - frontend/app/page.tsx
key-decisions:
  - "Rejection detail strings match the UI-SPEC copywriting contract verbatim (insufficient_cash/insufficient_shares/no_price), so the frontend never needs its own error-string mapping"
  - "Header Total Value/Cash render '--' only until the first successful /api/portfolio fetch, then freeze at last-known values on any later fetch failure (per the backstop truth), rather than reverting to '--' on every failure"
  - "sum() over position-derived totals seeded with 0.0 so an empty portfolio serializes holdings_value/unrealized_pnl as JSON floats, not ints"
requirements-completed: [PORT-01, PORT-02, PORT-03, PORT-04, UI-07, UI-09, TEST-01]
coverage:
  - id: D1
    description: "Buy/sell market orders fill instantly at the cached price with fractional quantities, no confirmation dialog"
    requirement: "PORT-02"
    verification:
      - kind: unit
        ref: "backend/tests/portfolio/test_trades.py::TestTradeHappyPath"
        status: pass
    human_judgment: false
  - id: D2
    description: "GET /api/portfolio returns cash, positions, holdings_value, total_value, unrealized_pnl"
    requirement: "PORT-01"
    verification:
      - kind: unit
        ref: "backend/tests/portfolio/test_trades.py::TestTradeHappyPath::test_get_portfolio_reports_position_with_live_price"
        status: pass
    human_judgment: false
  - id: D3
    description: "Insufficient cash / insufficient shares / no cached price are each rejected outright (400) with zero side effects"
    requirement: "PORT-03"
    verification:
      - kind: unit
        ref: "backend/tests/portfolio/test_trades.py::TestTradeValidation"
        status: pass
    human_judgment: false
  - id: D4
    description: "Every successful trade writes positions/trades/cash/snapshot inside one explicit transaction; a mid-transaction failure rolls back cleanly"
    requirement: "PORT-04"
    verification:
      - kind: unit
        ref: "backend/tests/portfolio/test_trades.py::TestTradeTransaction::test_rollback_on_mid_transaction_failure_leaves_db_untouched"
        status: pass
    human_judgment: false
  - id: D5
    description: "Trade bar submits buy/sell with disabled, pending, and inline-error states; prefills from ticker selection"
    requirement: "UI-07"
    verification:
      - kind: unit
        ref: "npx tsc --noEmit -p frontend/tsconfig.json (exit 0); npm run build (exit 0)"
        status: pass
    human_judgment: true
    rationale: "Visual/interaction polish (disabled styling, Submitting… label, error placement) needs a human eyeball per the plan's <human-check> list; compiles and builds cleanly but was not clicked through in a browser by this agent"
  - id: D6
    description: "Header shows live Total Value, Cash, and a green/yellow/red connection dot"
    requirement: "UI-09"
    verification:
      - kind: unit
        ref: "npx tsc --noEmit -p frontend/tsconfig.json (exit 0); npm run build (exit 0)"
        status: pass
    human_judgment: true
    rationale: "Live-updating header values and dot color transitions need a human eyeball per the plan's <human-check> list; not exercised in a running browser by this agent"
  - id: D7
    description: "Backend unit tests cover trade execution, weighted-average-cost math, and insufficient-cash/insufficient-shares edges"
    requirement: "TEST-01"
    verification:
      - kind: unit
        ref: "uv run --extra dev pytest tests/portfolio -v (18 passed)"
        status: pass
    human_judgment: false
duration: ~35min
completed: 2026-08-24
status: complete
---

# Phase 2 Plan 1: Buy and Sell Shares End to End Summary

**Market-order trade execution (buy/sell, fractional shares, explicit-transaction integrity) wired from a new `backend/app/portfolio/` package through `POST /api/portfolio/trade` and `GET /api/portfolio` to a new `TradeBar` + `usePortfolio` frontend, with the header showing live total value, cash, and a connection-status dot.**

## Performance
- **Duration:** ~35min
- **Started:** 2026-08-24T05:1X:XXZ (approx, plan load)
- **Completed:** 2026-08-24T05:48:46Z
- **Tasks:** 2 completed (both `<acceptance_criteria>` gates cleared)
- **Files modified:** 11 (9 created, 2 modified across the 3 commits)

## Accomplishments
- `execute_trade` wraps positions + trades + cash + snapshot writes in an explicit `BEGIN`/`COMMIT` (rollback on any exception) on the `autocommit=True` shared connection, closing the partial-trade-application risk flagged in `.planning/STATE.md`
- Weighted-average-cost math (`new_position_after_buy`) uses one formula for every buy, including reopening a fully-closed position, with no zero-quantity special case
- A user can buy/sell a fractional-share market order end to end: trade bar → REST → price cache → SQLite transaction → portfolio read → header, all covered by an end-to-end test
- 18 backend tests (`backend/tests/portfolio/test_trades.py`) cover the happy path, every rejection code (with an explicit assert that nothing was written), epsilon-tolerant full close, avg_cost preservation on sell, active-ticker-set cleanup, and a genuine rollback proof via a connection proxy

## Task Commits
1. **Task 1: Buy and sell a share end to end** - `58b902d` (feat) — portfolio package, router mount, TradeBar/usePortfolio, header extension, happy-path test
2. **Task 2: Prove the transaction and the rejection paths** - `a21aa56` (test) — 15 additional tests across `TestPositionMath`/`TestTradeValidation`/`TestTradeTransaction`

**Plan metadata:** (this commit, docs)

## Files Created/Modified
- `backend/app/portfolio/valuation.py` - `position_views`/`compute_total_value`/`portfolio_view`, the single valuation source for the router, trade response, and (later) the snapshot loop
- `backend/app/portfolio/trades.py` - `execute_trade`/`new_position_after_buy`/`TradeError`, the explicit-transaction trade engine
- `backend/app/portfolio/snapshots.py` - `record_snapshot`, the write-half helper called both from inside a trade transaction and (in Plan 02-03) a background loop
- `backend/app/portfolio/router.py` - `create_portfolio_router`/`TradeRequest`, `GET`/`POST` handlers mirroring `watchlist/router.py`'s factory pattern
- `backend/app/portfolio/__init__.py` - public API re-exports
- `backend/app/main.py` - mounts the portfolio router above the static frontend fallback
- `backend/tests/portfolio/test_trades.py` - 18 tests: happy path, position math, validation, transaction integrity
- `frontend/hooks/usePortfolio.ts` - fetch + client-side `revalue()` against the live SSE price map
- `frontend/components/TradeBar.tsx` - ticker/quantity/Buy/Sell with disabled, pending, and inline-error states, prefilled from `selectedTicker`
- `frontend/app/page.tsx` - header extended with Total Value/Cash/connection dot, `<TradeBar>` mounted below the header

## Decisions Made
- Header Total Value/Cash freeze at last-known values on a post-load fetch failure rather than reverting to `--`, matching the UI-SPEC backstop truth exactly (implemented by keying the display on `portfolio !== null`, not a separate `loaded` flag, after catching a null-pointer risk during self-review — see Deviations)
- `sum()` calls over position-derived totals seeded with `0.0` so an empty portfolio's `holdings_value`/`unrealized_pnl` serialize as JSON floats (`0.0`), not ints (`0`), matching the interface contract's stated types

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Header would crash on a first-load portfolio-fetch failure**
- **Found during:** Task 1, writing `page.tsx`'s header stat cluster
- **Issue:** The initial implementation used `loaded ? portfolio!.total_value.toFixed(2) : "--"`. `usePortfolio`'s `loaded` flag is set `true` in a `finally` block regardless of fetch success, so a failed *first* fetch would leave `loaded === true` and `portfolio === null`, and the non-null assertion (`portfolio!`) would throw at render time.
- **Fix:** Changed the condition to `portfolio ? portfolio.total_value.toFixed(2) : "--"`, keyed directly on the value being non-null rather than on the `loaded` flag. This also correctly implements the UI-SPEC backstop truth (freeze at last-known value on a later failure, never crash, never blank).
- **Files modified:** `frontend/app/page.tsx`
- **Verification:** `npx tsc --noEmit` passes (would not have caught the runtime-only crash, since `portfolio!` is a valid assertion at the type level); reasoned through manually before committing.
- **Commit:** `58b902d` (included in the Task 1 commit, not separately)

**2. [Rule 1 - Bug] Empty-portfolio totals serialized as JSON ints instead of floats**
- **Found during:** Post-Task-2 self-check, manually exercising `GET /api/portfolio` on a fresh database
- **Issue:** `sum(generator)` on an empty generator returns Python `int 0`; `round(0, 2)` stays `int`, so `holdings_value`/`unrealized_pnl` on a brand-new account serialized as JSON `0` instead of `0.0` — harmless to JS callers (which don't distinguish) but inconsistent with the interface contract's stated `float` types.
- **Fix:** Passed `0.0` as the `start` argument to every `sum()` call over position-derived totals in `valuation.py`.
- **Files modified:** `backend/app/portfolio/valuation.py`
- **Verification:** Re-ran the manual `GET /api/portfolio` check — confirmed `0.0` in the response; full suite (142 tests) still green; `ruff check` clean.
- **Commit:** `cd21fb9`

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs, both caught during this agent's own implementation/self-check, not pre-existing issues). **Impact:** both are low-severity correctness/consistency fixes with no behavior change to trade execution; neither affects PORT-01–04 acceptance criteria, which were verified after both fixes landed.

## TDD Gate Compliance

Task 2 (`type="auto" tdd="true"`) extended `test_trades.py` with 15 new tests targeting the behaviors listed in the plan's `<behavior>` block. All 15 passed on the first run against the Task 1 implementation of `trades.py` — no RED phase failure was observed, and consequently no `trades.py` changes were needed to make them pass (the plan explicitly permits touching `trades.py` only if a test reveals a defect; none did). This is recorded per the fail-fast RED-phase guidance: the tests were read against the plan's behavior list and the implementation's actual logic before being judged sufficient, rather than assumed correct because they passed. The commit sequence is `test(02-01)` only (no `feat(02-01)` gate exists for this task since no implementation changed) — a deliberate omission per the plan's own instruction, not a process gap.

## Issues Encountered
None beyond the two auto-fixed deviations above.

## Human-Check Items (harvested for phase UAT batch, not executed by this agent)

This agent ran headless in a worktree with no browser. The following `<human-check>` items from Task 1's `<verify>` block are deferred to the phase-level UAT/verification pass:
1. Header right side shows Total Value, Cash, and a coloured connection dot; dot green while prices stream
2. Fresh database: Total Value and Cash both read `10000.00`, monospace, two decimals
3. Buy 2 AAPL via the trade bar: Cash drops by ~2×AAPL price, Total Value stays roughly flat, no reload, no confirmation dialog
4. Clicking a watchlist row fills the trade bar's ticker field
5. Buying 100000 shares shows an inline insufficient-cash message, both fields keep their values, Cash unchanged
6. Selling an unheld ticker shows an inline insufficient-shares message
7. Header updates smoothly over 30s of streaming with no flash on Total Value/Cash
8. No uncaught browser console errors

All eight items' underlying logic is covered by automated tests or `tsc`/`next build`, but the visual/interaction confirmation itself needs a human or an automated UI check, per the plan's own framing (backend-verifiable logic vs. `<human-check>` visual confirmation).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
`backend/app/portfolio/valuation.py`'s `compute_total_value`/`record_snapshot` are ready for Plan 02-02's 30-second background snapshot loop and `GET /api/portfolio/history` endpoint — both were deliberately left as thin, transaction-agnostic building blocks per the plan's interface contract. `TradeBar`/`usePortfolio`'s `selectedTicker` prefill wiring (D-07) and the blue selection-highlight convention (D-08) are ready for Plan 02-03's positions table and heatmap to plug into the same `page.tsx` state. No blockers identified.

## Self-Check: PASSED

All 10 created files verified present on disk (5 `backend/app/portfolio/` modules, 2
`backend/tests/portfolio/` files, 2 frontend files, this SUMMARY.md). All 4 commits
(`58b902d`, `a21aa56`, `cd21fb9`, `87078cf`) verified present in `git log`.

---
*Phase: 02-portfolio-trading*
*Completed: 2026-08-24*
