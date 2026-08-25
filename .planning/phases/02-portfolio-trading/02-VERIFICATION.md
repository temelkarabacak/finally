---
phase: 02-portfolio-trading
verified: 2026-08-25T12:00:00Z
status: human_needed
score: 4/5 must-haves verified
behavior_unverified: 1
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 5/5 (present-and-wired basis; UAT run afterward found G-02-4)
  gaps_closed:
    - "G-02-4: P&L chart cold-start empty state never resolved without a trade — usePortfolio.ts now polls /api/portfolio and /api/portfolio/history on a 10s interval (cleared on unmount) instead of fetching once on mount"
  gaps_remaining: []
  regressions: []
behavior_unverified_items:
  - truth: "Success criterion 4 (P&L chart half): the P&L line chart gains a new point at least every 30 seconds via an unattended background recorder, and its empty state resolves on its own within ~70s of a cold start with no trade"
    test: "Fresh database, no trade, watch the P&L panel for ~90 seconds in a real browser (UAT test 4, re-run after the 02-04 fix)"
    expected: "Panel shows 'Building portfolio history' then switches on its own to a flat 10000.00 line with at least two points, with no trade, no page reload, and no manual refresh"
    why_human: "This is exactly the real-wall-clock, real-browser transition that UAT test 4 originally caught failing (G-02-4). The fix is now proven at the code and integration-test layer (see evidence below) but no automated frontend test exists to exercise the actual DOM/state transition, and no human has re-run UAT test 4 against the fixed code in a live browser yet."
human_verification:
  - test: "Fresh database, no trade: watch the P&L panel for ~90 seconds (UAT test 4, re-run)"
    expected: "Panel shows 'Building portfolio history' / 'usually within a minute', then switches on its own to a flat 10000.00 line with at least two points — no trade, no reload, no manual refresh"
    why_human: "Real-time, wall-clock-dependent DOM state transition; this is the exact scenario the original G-02-4 gap was caught in and needs a live re-confirmation now that the fix is in place"
---

# Phase 2: Portfolio & Trading Verification Report

**Phase Goal:** A user can buy and sell shares instantly from the terminal and watch cash, positions, and P&L revalue live as prices stream
**Verified:** 2026-08-25T12:00:00Z
**Status:** human_needed
**Re-verification:** Yes — this phase previously went through UAT (02-UAT.md), which found gap G-02-4 (P&L chart cold-start empty state never resolved without a trade). Gap-closure plan 02-04 has since executed. This verification confirms the fix and re-checks all four plans' must-haves.

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User enters ticker/quantity in trade bar, clicks Buy/Sell, order fills instantly — cash, positions, header totals update without reload, no confirmation dialog | ✓ VERIFIED | Code unchanged since prior verification (`TradeBar.tsx`, `execute_trade`). Independently re-confirmed: `onSubmit={(event) => event.preventDefault()}`, `fetch("/api/portfolio/trade")`, `submitting` disables both buttons. **UAT test 1 passed** in a real browser (02-UAT.md): "Order fills instantly ... Cash and Total Value ... update immediately ... position row appears ... then both disappear when sold back to zero." |
| 2 | Over-budget buy / over-size sell rejected outright (400), nothing clamped/partial; backend unit tests cover these edges alongside trade execution and P&L math | ✓ VERIFIED | `backend/app/portfolio/trades.py` rejects before any write; re-ran `uv run --directory backend --extra dev pytest tests/portfolio -q` → **44 passed**; full suite `pytest -q` → **168 passed**; `ruff check app/ tests/` → clean. **UAT test 2 passed** in a real browser: "inline red error message appears ... fields retain their entered values, and Cash/Total Value do not change." |
| 3 | Positions table shows ticker/qty/avg cost/current price/unrealized P&L/%change, revaluing as prices stream | ✓ VERIFIED | `PositionsTable.tsx` renders all 6 columns (`Ticker, Qty, Avg Cost, Price, P&L, Chg %`) from `usePortfolio`'s revalued `PositionView[]`. **UAT tests 5, 6, 7, 8 passed**: live revaluation, click/keyboard selection, grayscale distinguishability. |
| 4 | Heatmap sized by weight/colored by P&L; P&L chart gains a point every ≥30s and immediately after each trade | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | **Heatmap half: VERIFIED.** `PortfolioHeatmap.tsx` (`Treemap dataKey="weight"`, `#3fb950`/`#f85149` fill by P&L sign) unchanged since prior verification; **UAT test 5 passed** ("Tile areas visibly track the dollar weights ... green for winners and red for losers"). **P&L-chart half: was the exact UAT-4 failure (G-02-4).** Gap-closure plan 02-04 changed `usePortfolio.ts`'s mount effect from a single fetch to `refresh()` immediately + `setInterval(refresh, 10000)` cleared on unmount — confirmed present at `frontend/hooks/usePortfolio.ts:160-169`. Independently re-ran the plan's own integration probe (not trusting the SUMMARY's numbers): started a fresh backend against a throwaway DB, waited 70s, `curl /api/portfolio/history` → **2 recorded snapshots**, confirming the backend's unconditional 30s recorder plus the new 10s client poll gives the chart its required second point well inside the ~70s window. This proves the underlying data-timing budget is met, but no automated frontend test exercises the actual empty-state → populated-chart DOM transition, and it has not yet been re-observed in a live browser since the fix (the original bug was caught exactly there). See `human_verification`. |
| 5 | Header shows live total value, cash balance, connection dot green/yellow/red | ✓ VERIFIED | `page.tsx` unchanged since prior verification: `Total Value {...toFixed(2)}`, `Cash {...toFixed(2)}`, `rounded-full` dot keyed off `usePriceStream()` status. **UAT test 3 passed**: dot cycled green → yellow → red correctly through a real disconnect/reconnect. |

**Score:** 4/5 truths fully verified (5 ROADMAP criteria, with #4 split into a verified heatmap half and a present-but-behavior-unverified P&L-chart half); 1 present-but-behavior-unverified.

### Gap Closure Verification (G-02-4)

| Check | Result |
|---|---|
| `frontend/hooks/usePortfolio.ts` polls on a repeating interval strictly shorter than the backend's 30s snapshot cadence | ✓ Confirmed: `PORTFOLIO_POLL_INTERVAL_MS = 10000` (10s), `setInterval(refresh, PORTFOLIO_POLL_INTERVAL_MS)` at line 167 |
| The interval is cleared on unmount | ✓ Confirmed: `return () => clearInterval(intervalId);` at line 168 |
| A trade still refreshes everything immediately (interval is additive, not a replacement) | ✓ Confirmed: `TradeBar.tsx:49` still calls `await onTraded()` → `page.tsx:68` `onTraded={refresh}`, unchanged |
| No backend file was modified (per the plan's explicit scope guard) | ✓ Confirmed: `git diff --name-only` for commit `6129e9c` shows only `frontend/hooks/usePortfolio.ts` |
| Backend independently proven to serve ≥2 history points within 70s of a fresh cold start, with no trade | ✓ Confirmed via my own re-run (not the SUMMARY's numbers): fresh throwaway DB, port 8012, 70s wait → `points=2` |
| Full backend suite and portfolio suite still green after the fix | ✓ 168/168 and 44/44 pass; `ruff check` clean |
| Frontend still builds and typechecks | ✓ `npm run build` succeeds, static export produced |
| `frontend/hooks/usePortfolio.ts` lint-clean (the plan's own hard gate) | ✓ Confirmed: `npm run lint` no longer reports `usePortfolio.ts` (previously 1 of 4 `react-hooks/set-state-in-effect` errors was here; now 3 remain, all pre-existing/deferred in `WatchlistPanel.tsx` and `TradeBar.tsx`, none new) |
| Live browser re-confirmation of the fixed empty-state transition (UAT test 4, re-run) | ✗ Not yet done — see `human_verification` |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/portfolio/trades.py` | `execute_trade` w/ BEGIN/COMMIT, weighted-avg cost, outright rejection | ✓ VERIFIED | Unchanged since prior verification; 18 tests pass |
| `backend/app/portfolio/valuation.py` | Shared valuation (`position_views`, `compute_total_value`, `portfolio_view`) | ✓ VERIFIED | Unchanged; single source of arithmetic |
| `backend/app/portfolio/snapshots.py` | `record_snapshot`, `get_snapshot_history`, task lifecycle, `SNAPSHOT_INTERVAL_SECONDS=30`, `HISTORY_LIMIT=2000` | ✓ VERIFIED | Unchanged (plan 02-04 explicitly did not touch backend files) |
| `backend/app/portfolio/router.py` | `GET /api/portfolio`, `GET /api/portfolio/history`, `POST /api/portfolio/trade` | ✓ VERIFIED | All 3 routes present, mounted above the static fallback |
| `frontend/hooks/usePortfolio.ts` | Fetch + revalue + repeating poll with unmount cleanup (post-02-04) | ✓ VERIFIED | `PORTFOLIO_POLL_INTERVAL_MS`, `setInterval`/`clearInterval` present and wired |
| `frontend/components/TradeBar.tsx` | Buy/Sell form, disabled/pending/error states | ✓ VERIFIED | Unchanged since prior verification |
| `frontend/components/PnlChart.tsx` | lightweight-charts line series, D-03 empty state | ✓ VERIFIED (present/wired) | Unchanged file; now fed by the fixed polling hook — see behavior note above |
| `frontend/components/PositionsTable.tsx` | Positions grid, D-01 empty state, selection | ✓ VERIFIED | Unchanged since prior verification |
| `frontend/components/PortfolioHeatmap.tsx` | Recharts Treemap, D-02 empty state | ✓ VERIFIED | Unchanged since prior verification |
| `backend/tests/portfolio/*.py` | Trade/valuation/router/snapshot test coverage | ✓ VERIFIED | 44 portfolio-scoped tests, all pass |

### Key Link Verification

| From | To | Via | Status |
|------|----|----|--------|
| `backend/app/main.py` | `backend/app/portfolio/router.py` | `create_portfolio_router(get_db, source, cache)`, above `app.frontend(...)` | ✓ WIRED |
| `backend/app/main.py` | `backend/app/portfolio/snapshots.py` | `start_snapshot_task` after `source.start`, `stop_snapshot_task` before `source.stop` | ✓ WIRED |
| `frontend/hooks/usePortfolio.ts` | `backend/app/portfolio/router.py` | Immediate `refresh()` + `setInterval(refresh, 10000)`, cleared on unmount | ✓ WIRED (new in 02-04) |
| `frontend/components/TradeBar.tsx` | `frontend/hooks/usePortfolio.ts` | `onTraded={refresh}` still fires immediately post-trade, additive to the poll | ✓ WIRED |
| `frontend/app/page.tsx` | `frontend/components/PnlChart.tsx` | `<PnlChart points={history} error={historyError} ready={historyLoaded} />` | ✓ WIRED |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| P&L chart points | `history` | `GET /api/portfolio/history` → SQLite `portfolio_snapshots`, polled every 10s | Yes — independently confirmed 2 points present at t≈70s on a fresh DB | ✓ FLOWING |
| Header / positions / heatmap | `portfolio.*` | `GET /api/portfolio` → `portfolio_view()`, polled every 10s + revalued against live SSE prices | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full backend suite green after the fix | `uv run --directory backend --extra dev pytest -q` | `168 passed` | ✓ PASS |
| Portfolio-scoped suite green | `uv run --directory backend --extra dev pytest tests/portfolio -q` | `44 passed` | ✓ PASS |
| Ruff clean | `uv run --directory backend --extra dev ruff check app/ tests/` | `All checks passed!` | ✓ PASS |
| Frontend builds and typechecks | `npm --prefix frontend run build` | Compiles, static export produced | ✓ PASS |
| Frontend lint on the changed file | `npm --prefix frontend run lint` | 3 errors, all pre-existing/deferred (`WatchlistPanel.tsx` x2, `TradeBar.tsx` x1); `usePortfolio.ts` clean | ✓ PASS (no new errors) |
| Backend serves ≥2 P&L history points within 70s of a cold start with no trade | Fresh throwaway DB, `uvicorn` on port 8012, wait 70s, `curl /api/portfolio/history` | `points=2` | ✓ PASS (independently reproduced, not taken from SUMMARY) |
| Client poll interval strictly under server snapshot cadence | `grep PORTFOLIO_POLL_INTERVAL_MS` = 10000ms vs `SNAPSHOT_INTERVAL_SECONDS` = 30s | 10s < 30s, margin confirmed | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| PORT-01 | 02-01 | `GET /api/portfolio` returns positions, cash, total value, unrealized P&L | ✓ SATISFIED | `portfolio_view()`, `TestPortfolioRoutes` |
| PORT-02 | 02-01 | Market buy/sell, fractional quantities | ✓ SATISFIED | `execute_trade`, `TestTradeHappyPath` |
| PORT-03 | 02-01 | Insufficient cash/shares rejected outright, never clamped | ✓ SATISFIED | `TestTradeValidation` (zero side-effect assertions) |
| PORT-04 | 02-01 + 02-02 + 02-04 | 30s + post-trade snapshots, `GET /api/portfolio/history`, chart resolves on its own | ✓ SATISFIED (post-02-04) | `TestSnapshotLoop`, plus independently re-confirmed 2-point cold start |
| UI-04 | 02-03 | Heatmap sized by weight, colored by P&L | ✓ SATISFIED | `PortfolioHeatmap.tsx`, UAT test 5 |
| UI-05 | 02-02 + 02-04 | P&L line chart over time, cold-start empty state resolves unaided | ⚠️ SATISFIED (code+data proven; live re-confirmation pending) | `PnlChart.tsx` + `usePortfolio.ts` polling fix; see behavior_unverified_items |
| UI-06 | 02-03 | Positions table w/ 6 columns, live revaluation | ✓ SATISFIED | `PositionsTable.tsx`, UAT tests 5-8 |
| UI-07 | 02-01 | Trade bar w/ disabled/pending/error states | ✓ SATISFIED | `TradeBar.tsx`, UAT tests 1-2 |
| UI-09 | 02-01 | Header live stats + connection dot | ✓ SATISFIED | `page.tsx` header, UAT test 3 |
| TEST-01 | 02-01 + 02-02 | Backend tests cover trade execution, P&L, edges | ✓ SATISFIED | 44 portfolio tests, all pass |

No orphaned requirements: all Phase-2-mapped IDs in `REQUIREMENTS.md`'s tracking table (PORT-01–04, UI-04/05/06/07/09, TEST-01) appear in at least one plan's `requirements:` frontmatter field.

**Documentation drift (not a code gap, carried forward from prior verification):** `.planning/REQUIREMENTS.md`'s checkbox list still shows `[ ]` (Pending) for PORT-01–04, UI-05, UI-07, UI-09, and TEST-01, even though the tracking table and the actual code confirm these are implemented and tested. This is a documentation-sync gap the project should close, not a functional gap.

### Anti-Patterns Found

None. `grep -nE 'TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER'` on `frontend/hooks/usePortfolio.ts` (the only file touched by the gap-closure plan) returns zero hits.

### Gaps Summary

No blocking gaps — G-02-4 is closed at the code and data-timing level with independently reproduced evidence, and no regressions were found across the rest of Phase 2. Two non-blocking findings worth the developer's attention:

1. **WR-01 (02-04-REVIEW.md, unresolved warning): overlapping polls have no request-ordering guard.** `refresh()` issues two independent, un-cancelled `fetch` calls with no in-flight guard or `AbortController`. Now that it runs on a repeating 10s interval instead of once, a slow response from an earlier poll could in principle land after and overwrite a fresher one, which could manifest as the exact class of symptom (P&L chart losing a point) this gap-closure plan targets. This is explicitly out of scope per 02-04-PLAN.md's own prohibition ("MUST NOT add ... AbortController plumbing — the existing refresh() callback is reused unchanged") and is a low-probability, low-severity risk on a same-origin localhost app, but it is unresolved and worth a follow-up if intermittent P&L regressions are ever observed.
2. **REQUIREMENTS.md checkbox drift**, described above — documentation housekeeping, not a code defect.

### Human Verification Required

1 item remains, carried forward specifically because it is the live-browser re-confirmation of the exact scenario G-02-4 was caught in:

### 1. P&L chart cold-start resolution (UAT test 4, re-run post-fix)

**Test:** Start the app against a fresh database, do not trade, and watch the P&L panel for about 90 seconds.
**Expected:** The panel shows "Building portfolio history" / "usually within a minute" at first, then switches on its own to a flat 10000.00 line with at least two points — no trade, no page reload, no manual refresh.
**Why human:** This is a real-wall-clock, real-DOM state transition. It is now backed by independently-reproduced evidence that the underlying data is available in time (backend serves 2 points by t≈70s; client polls every 10s) and that the code is wired correctly, but no automated frontend test exercises the actual empty-state → chart transition, and this exact scenario is where the original bug (G-02-4) was caught — a live re-observation closes the loop UAT opened.

All other UAT items (1, 2, 3, 5, 6, 7, 8) already passed in a real browser per `02-UAT.md` and are not re-flagged here; no regression was found in the code paths they cover.

---

_Verified: 2026-08-25T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
