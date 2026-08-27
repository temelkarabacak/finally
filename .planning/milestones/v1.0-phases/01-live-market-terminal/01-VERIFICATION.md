---
phase: 01-live-market-terminal
verified: 2026-08-23T20:45:00Z
status: passed
score: 5/5 roadmap success criteria verified; 13/13 requirement IDs satisfied
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: none
  note: "No prior VERIFICATION.md existed for this phase; this is the initial verification."
---

# Phase 1: Live Market Terminal Verification Report

**Phase Goal:** A user opens a browser at port 8000 and watches an editable watchlist of live-streaming prices in the dark trading-terminal UI.
**Verified:** 2026-08-23T20:45:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User opens `http://localhost:8000` on a fresh DB and sees the 10 seeded tickers with prices updating ~2x/sec, flashing green/red with a fading animation | ✓ VERIFIED | `backend/app/db/schema.sql` + `seed.py` (10 default tickers, lazy init, 96-100% test coverage); `backend/app/main.py` wires a single `PriceCache` to the SSE stream at 500ms cadence (`app/market/stream.py:85`, `interval=0.5`); `frontend/app/globals.css` `flash-up`/`flash-down` 500ms keyframes; live `bash scripts/smoke.sh` run (this session) confirmed all 10 tickers present in the first `data:` SSE frame; Task 3 human checkpoint in `01-03-SUMMARY.md` recorded PASS for streaming (item 2) and flash timing (item 3) |
| 2 | User can add/remove a ticker; grid and SSE reflect the change immediately; a removed ticker with an open position keeps streaming | ✓ VERIFIED | `backend/app/watchlist/router.py` POST/DELETE handlers read verbatim (write-DB-then-source-call pattern, `ticker_has_open_position` guard re-evaluated per DELETE call); 9/9 `tests/watchlist/test_router.py` tests pass including `test_delete_with_open_position_keeps_streaming`; `frontend/components/WatchlistPanel.tsx` calls `fetch("/api/watchlist", {method:"POST"})` / `fetch(\`/api/watchlist/${ticker}\`, {method:"DELETE"})` and refetches without tearing down the `EventSource` |
| 3 | Clicking a watchlist row shows a larger chart in the main chart area; every row carries a sparkline accumulated since page load | ✓ VERIFIED | `frontend/components/PriceChart.tsx` (`addSeries(LineSeries,...)`, `setData()` not `update()`, `chart.remove()` on cleanup — v5 API used correctly, confirmed by direct read); `frontend/app/page.tsx` wires `selectedTicker`/`onSelect` between `WatchlistPanel` and `PriceChart`; `frontend/components/Sparkline.tsx` returns `null` for 0 points, a centered mark for 1 point, a flat line when `max === min`, and scales width to the fill fraction of the 120-slot buffer (all read directly, matching the plan's behavior spec exactly); Task 3 checkpoint items 6-7 PASS |
| 4 | Entire interface renders in the dark theme (`#0d1117`/`#1a1a2e`, yellow `#ecad0a`, blue `#209dd7`, purple `#753991`) | ✓ VERIFIED | `frontend/app/globals.css` `@theme` block transcribes all five hex values verbatim (`grep -c` returns 5); no pure-black value found anywhere in the file; purple applied to the watchlist submit button, yellow to the panel heading, blue to `PriceChart`'s series color and the selected-row border — all confirmed by direct code read; Task 3 checkpoint item 1 PASS |
| 5 | `GET /api/health` reports healthy; prices keep streaming when Massive is misconfigured or fails mid-run, falling over to the simulator permanently and never switching back | ✓ VERIFIED | `backend/app/main.py` health handler reads through `FailoverMarketDataSource.active`; `backend/app/market/massive_client.py` trips `_permanently_failed` on the very first exception (no retry/threshold), redacts the API key from the log message, and `_poll_loop` exits; `backend/app/market/failover.py` swaps to a freshly-started `SimulatorDataSource` under an `asyncio.Lock`-guarded idempotent swap; 10/10 `tests/market/test_failover.py` tests pass, including the API-key-redaction and second/concurrent-callback-no-op cases; manually spot-checked by the plan executor with a bad `MASSIVE_API_KEY` (see `01-02-SUMMARY.md` D5/D6) |

**Score:** 5/5 roadmap success criteria verified. All 13 phase requirement IDs (FOUND-01..04, WATCH-01..04, PORT-05, UI-01, UI-02, UI-03, UI-10) trace to passing automated tests, live smoke-run evidence, or the Task 3 human-verify checkpoint (which returned all 9 items PASS per `01-03-SUMMARY.md`).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/main.py` | FastAPI app, lifespan, `/api/health`, static serving, router registration order | ✓ VERIFIED | Read directly; API routers registered before `app.frontend()`; health reports `market_source` honestly through `FailoverMarketDataSource.active` |
| `backend/app/db/schema.sql` | Six-table DDL per PLAN.md §7 | ✓ VERIFIED | Byte-for-byte matches the spec's six tables, `UNIQUE(user_id, ticker)` on `watchlist`/`positions` |
| `backend/app/db/connection.py` | `init_db`, `get_db`, `get_active_tickers`, `get_watchlist_tickers`, mutation queries | ✓ VERIFIED | All functions present, parameter-bound, `get_active_tickers` is a `UNION` (not `UNION ALL`) |
| `backend/app/db/seed.py` | `DEFAULT_WATCHLIST` (10 tickers), `seed_defaults` | ✓ VERIFIED | 100% test coverage per `pytest --cov` run this session |
| `backend/app/watchlist/router.py` | `create_watchlist_router` factory, GET/POST/DELETE | ✓ VERIFIED | 100% statement coverage; 9/9 tests pass |
| `backend/app/market/failover.py` | `FailoverMarketDataSource` wrapper | ✓ VERIFIED | 98% statement coverage; 10/10 tests pass; the single uncovered line (49) is inside the lock-guarded swap block, non-critical |
| `frontend/hooks/usePriceStream.ts` | `usePriceStream` — `prices`, `history`, `timeline`, `status` | ✓ VERIFIED | Read directly; `timeline` dedupe (`Math.floor`, replace/drop/append) matches the spec exactly |
| `frontend/next.config.ts` | `output: 'export'` | ✓ VERIFIED | `npm run build` produces `frontend/out/index.html` |
| `frontend/components/WatchlistPanel.tsx` | Grid, flash, sparkline column, add/remove | ✓ VERIFIED | All columns present, `toFixed(2)` on price and percent, arrow glyph + signed percent (color-independent), keyboard-selectable rows |
| `frontend/components/Sparkline.tsx` | Inline SVG, no library | ✓ VERIFIED | Zero/one/flat-line branches all present and correctly implemented |
| `frontend/components/PriceChart.tsx` | Lightweight Charts v5 wrapper | ✓ VERIFIED | `addSeries(LineSeries,...)`, `setData()`, `chart.remove()` cleanup, `ResizeObserver` |
| `frontend/app/globals.css` | Theme tokens + flash keyframes | ✓ VERIFIED | All 5 required hex values present; `prefers-reduced-motion` both branches present; no `infinite` animation |
| `scripts/smoke.sh` | End-to-end automated gate | ✓ VERIFIED (with caveat) | Ran live this session: all assertions printed "All smoke assertions passed", exit 0. Caveat: after assertions complete, the script's own `trap cleanup EXIT` (`kill "$SERVER_PID"; wait "$SERVER_PID"`) hung indefinitely in this verification environment because the backgrounded `uv run uvicorn` process did not exit after SIGTERM while an SSE connection remained in the `ESTAB` state — required a manual `kill -9` to unblock. This did not affect the assertions themselves (which had already completed and printed pass) but is a real operational fragility in graceful shutdown under an open SSE connection. See Anti-Patterns below. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `frontend/components/WatchlistPanel.tsx` | `backend/app/watchlist/router.py` | `fetch('/api/watchlist', ...)` POST/DELETE | ✓ WIRED | Confirmed by direct read: both call sites present |
| `backend/app/watchlist/router.py` | `backend/app/market/interface.py` | `normalize_ticker()` | ✓ WIRED | Applied in the Pydantic validator, POST body, and DELETE path param |
| `backend/app/watchlist/router.py` | `backend/app/db/connection.py` | `ticker_has_open_position()` | ✓ WIRED | Present inside the DELETE handler, re-evaluated per call |
| `backend/app/market/factory.py` | `backend/app/market/failover.py` | `FailoverMarketDataSource(...)` on the Massive branch | ✓ WIRED | Confirmed; no-key branch still returns bare `SimulatorDataSource` |
| `backend/app/market/massive_client.py` | `backend/app/market/failover.py` | `on_permanent_failure` callback | ✓ WIRED | `primary._on_permanent_failure = self._on_permanent_failure` in `FailoverMarketDataSource.__init__` |
| `frontend/components/PriceChart.tsx` | `lightweight-charts` | `addSeries(LineSeries, ...)` | ✓ WIRED | v5 API used correctly; `^5.2.1` resolved in `package.json` |
| `frontend/components/WatchlistPanel.tsx` | `frontend/components/Sparkline.tsx` | `<Sparkline points={...} />` | ✓ WIRED | Per-row usage confirmed |
| `frontend/app/page.tsx` | `frontend/components/PriceChart.tsx` | `selectedTicker` / `timeline[selectedTicker]` | ✓ WIRED | Confirmed |
| `frontend/components/WatchlistPanel.tsx` | `frontend/app/globals.css` | `flash-up`/`flash-down` classes | ✓ WIRED | Driven by `tick.direction`, applied via `requestAnimationFrame` to force re-trigger |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `WatchlistPanel` rows | `tickers`, `prices[ticker]` | `GET /api/watchlist` (DB) + SSE `prices` state (PriceCache) | Yes — live smoke run confirmed all 10 seeded tickers with a `direction` field in the first SSE frame | ✓ FLOWING |
| `Sparkline` points | `history[ticker]` | Accumulated client-side from SSE `message` events since mount | Yes — capped, real accumulation, not a mock/static array | ✓ FLOWING |
| `PriceChart` series | `timeline[selectedTicker]` | Accumulated client-side from SSE `message` events, deduped/floored | Yes | ✓ FLOWING |
| `/api/health` `market_source` | `source.active` | Live `isinstance` check against the module-scope `source` object | Yes — confirmed by both automated tests and a live manual failover spot-check (per `01-02-SUMMARY.md`) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Backend full suite | `uv run --directory backend --extra dev pytest tests/ -q` | 124 passed | ✓ PASS |
| Backend lint | `uv run --directory backend --extra dev ruff check app/ tests/` | All checks passed | ✓ PASS |
| Backend coverage | `pytest --cov=app --cov-report=term-missing` | 99% overall; `failover.py` 98%, `watchlist/router.py` 100% | ✓ PASS |
| Frontend build | `npm --prefix frontend run build` | Compiled successfully, static pages generated | ✓ PASS |
| Frontend type check | `npx --prefix frontend tsc --noEmit -p tsconfig.json` | Exit 0, no output | ✓ PASS |
| Frontend lint | `npx eslint .` (frontend) | 2 errors in `WatchlistPanel.tsx` (`react-hooks/set-state-in-effect`) | ✗ FAIL (see WR-01 below; not gated by any plan's acceptance criteria) |
| E2E smoke gate | `bash scripts/smoke.sh` | All assertions passed (exit 0 per background task result); server process required manual force-kill afterward | ✓ PASS (assertions); ⚠️ shutdown hang observed |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| FOUND-01 | 01-01 | `GET /api/health` health check | ✓ SATISFIED | `test_health.py` (2 tests), live smoke run |
| FOUND-02 | 01-01 | Lazy SQLite init + seed | ✓ SATISFIED | `test_init.py`, `test_seed.py`, live smoke DB assertion |
| FOUND-03 | 01-01 | FastAPI serves Next.js static export, `/api/*` precedence | ✓ SATISFIED | `test_static_frontend.py`, `main.py` registration order, live smoke run |
| FOUND-04 | 01-01 | Market source starts at lifespan with active ticker set | ✓ SATISFIED | `test_app_startup.py` (4 tests) |
| WATCH-01 | 01-01 | `GET /api/watchlist` with latest prices | ✓ SATISFIED | Live smoke run (10 entries), `watchlist/router.py` |
| WATCH-02 | 01-02 | `POST /api/watchlist` add | ✓ SATISFIED | `test_router.py` (4 add-path tests) |
| WATCH-03 | 01-02 | `DELETE /api/watchlist/{ticker}`, position-aware | ✓ SATISFIED | `test_router.py` (4 delete-path tests) |
| WATCH-04 | 01-01 | SSE stream at ~500ms cadence for active ticker set | ✓ SATISFIED | `app/market/stream.py` (`interval=0.5`), live smoke SSE assertion |
| PORT-05 | 01-02 | Permanent Massive failover | ✓ SATISFIED | `test_failover.py` (10 tests), `failover.py`, `massive_client.py` |
| UI-01 | 01-03 | Watchlist grid: ticker/price/% /sparkline | ✓ SATISFIED | `WatchlistPanel.tsx`, `Sparkline.tsx`, Task 3 checkpoint items 5-6 |
| UI-02 | 01-03 | Price flash, fading, reduced-motion | ✓ SATISFIED | `globals.css` keyframes, Task 3 checkpoint items 3-4 |
| UI-03 | 01-03 | Click row → larger chart | ✓ SATISFIED | `PriceChart.tsx`, Task 3 checkpoint item 7 |
| UI-10 | 01-03 | Dark terminal theme, exact hex values | ✓ SATISFIED | `globals.css` `@theme` block, Task 3 checkpoint item 1 |

**No orphaned requirements.** All 13 IDs listed in ROADMAP.md's Phase 1 row are claimed across the three plans' `requirements` frontmatter and confirmed satisfied in the codebase.

**⚠️ Stale `.planning/REQUIREMENTS.md`:** As flagged by the orchestrator, `.planning/REQUIREMENTS.md` still shows all 13 of these requirement IDs as `Pending` / unchecked (`- [ ]`), and the coverage table at the bottom of that file also shows `Pending` for all 13. This is *not* a phase gap — the actual codebase satisfies every one of them, confirmed above by direct inspection and a live test/smoke run — but the requirements-marking tool was reportedly not run in any of the three isolated worktrees. **The orchestrator should reconcile `.planning/REQUIREMENTS.md` to mark FOUND-01..04, WATCH-01..04, PORT-05, UI-01, UI-02, UI-03, UI-10 as complete** before Phase 2 planning begins, so downstream tooling that reads that file doesn't report false gaps.

### Anti-Patterns Found

No debt markers (`TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER`) or hollow-prop/hardcoded-empty stubs were found in any file modified by this phase (`grep -rnE` scan across `backend/app` and `frontend/app|components|hooks` returned zero matches).

The `01-REVIEW.md` code review (already run for this phase, 0 critical / 5 warning / 4 info) identified real, reproducible issues that I independently re-confirmed in this session rather than trusting the report:

| File | Finding | Severity | Re-confirmed | Impact |
|------|---------|----------|---------------|--------|
| `frontend/components/WatchlistPanel.tsx:60,77` | `react-hooks/set-state-in-effect` — `npx eslint .` exits 1 with 2 errors | ⚠️ Warning | Yes, reproduced this session | Real lint-gate failure; not required by any plan's acceptance criteria (only `build`/`tsc`/`smoke.sh` were gated), so does not block the phase goal, but would break a CI lint step |
| `backend/app/market/massive_client.py:64-73` via `failover.py:71-81` | `MassiveDataSource.stop()` cancels and awaits its own currently-running task (self-cancellation) | ⚠️ Warning | Yes, confirmed by direct code read; all 10 `test_failover.py` tests pass, so it works today | Fragile pattern relying on undocumented asyncio scheduling behavior; a future Python version or an added `await` before the call could turn this into a hang |
| `backend/app/market/failover.py:48-61` vs `:71-81` | `FailoverMarketDataSource` delegating methods (`start`/`stop`/`add_ticker`/`remove_ticker`/`get_tickers`) read `self._active` without the lock that guards the swap | ⚠️ Warning | Yes, confirmed by direct code read | A ticker add/remove racing a failover swap can be silently applied to the source being torn down; narrow window, not exercised by current tests |
| `backend/app/watchlist/router.py:90-95,109-114` | `market_source.add_ticker`/`remove_ticker` calls after the DB write are unguarded | ⚠️ Warning | Yes, confirmed by direct code read | An exception here surfaces as an unhandled 500 even though the watchlist row already committed; low likelihood today (simulator/Massive add/remove don't raise), real risk if a future data source does network I/O in these calls |
| `backend/tests/api/test_static_frontend.py:13-42` | Backup fixture (`static.bak`) not crash-safe across interrupted test runs | ℹ️ Info | Yes, confirmed by direct code read | Test-infrastructure only, not production code |
| *(new, found this session, not in 01-REVIEW.md)* `scripts/smoke.sh` cleanup | After all assertions pass, the trap's `kill "$SERVER_PID"; wait "$SERVER_PID"` hung indefinitely against a live server with an open SSE connection in this verification environment; required a manual `kill -9` to unblock | ⚠️ Warning | Observed directly this session (see the smoke.sh run above) | The smoke gate's *assertions* were unaffected (all passed, exit 0), but the script's own process cleanup is not reliably prompt when an SSE connection is still open at shutdown time — worth a follow-up look before this becomes the basis for Phase 4's E2E harness, which will also need to start/stop the server programmatically |

None of these findings contradict any of the five roadmap success criteria or any plan's `must_haves.truths`/`prohibitions` — they are pre-existing, already-triaged warnings (four of five carried directly from `01-REVIEW.md`) plus one newly observed operational fragility in the smoke script's shutdown path. I am treating all of them as non-blocking for this phase's goal (which is about live, editable, themed price streaming — not clean process shutdown or lint cleanliness) but flagging them for follow-up.

### Human Verification Required

None outstanding. The phase's `checkpoint:human-verify` task (01-03-PLAN.md Task 3) was already resolved during execution — all 9 items (theme, streaming, flash, reduced-motion, color independence, sparklines, chart, watchlist edit, console) returned PASS, documented with a per-item table in `01-03-SUMMARY.md`. I independently re-confirmed the underlying code for each of those items (theme tokens, flash keyframes, sparkline null/flat-line branches, chart `setData`/`addSeries` usage, arrow+percent color-independence) rather than trusting the SUMMARY narrative alone, and found the implementation consistent with what was reportedly verified live.

### Gaps Summary

No gaps found. All five roadmap Success Criteria for Phase 1 are observably true in the running codebase: live SSE-driven price streaming with flash animation, editable watchlist with position-aware removal, per-row sparklines and a clickable per-ticker chart, the exact dark-terminal theme, and a permanent, honestly-reported Massive-to-simulator failover. The full backend test suite (124 tests), ruff, the frontend build, the TypeScript check, and a live `scripts/smoke.sh` run all pass. All 13 requirement IDs are satisfied by direct code inspection, not just SUMMARY claims.

Two items are flagged for the orchestrator/human, not as phase-blocking gaps:
1. **Reconcile `.planning/REQUIREMENTS.md`** — mark the 13 Phase 1 requirement IDs complete; the file is currently stale (shows all as Pending) because the requirements-marking tool didn't run cleanly in the isolated executor worktrees.
2. **Five known code-quality warnings** (one new) from the anti-patterns table above — none block the phase goal, but the `MassiveDataSource.stop()` self-cancellation fragility (WR-02) and the smoke-script shutdown hang are worth a look before Phase 4 builds its Docker/E2E harness on top of this server-lifecycle code.

---

*Verified: 2026-08-23T20:45:00Z*
*Verifier: Claude (gsd-verifier)*
