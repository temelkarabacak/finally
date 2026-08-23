---
phase: 01-live-market-terminal
plan: 02
subsystem: watchlist + market-data-resilience
tags: [fastapi, sqlite, sse, nextjs, watchlist, failover, pytest]

# Dependency graph
requires:
  - phase: 01-01
    provides: "backend/app/db/ lazy-init schema, app/main.py entry point, PriceCache, market factory, frontend usePriceStream hook"
provides:
  - "backend/app/watchlist/: create_watchlist_router(get_conn, market_source, price_cache) -> APIRouter with GET/POST/DELETE"
  - "backend/app/db/connection.py: add_watchlist_ticker, remove_watchlist_ticker, ticker_has_open_position"
  - "backend/app/market/failover.py: FailoverMarketDataSource with .active, .failed_over"
  - "backend/app/market/massive_client.py: MassiveDataSource.permanently_failed, on_permanent_failure callback"
  - "GET /api/health market_source field"
  - "frontend/components/WatchlistPanel.tsx: inline add/remove watchlist UI"
affects: [01-03-terminal-ui, portfolio-phase, ai-copilot-phase, docker-phase]

# Actuals (#2632)
actuals:
  tokens: 12463
  tasks: 2
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Router-per-call factory (create_watchlist_router) mirroring create_stream_router, so tests can build repeatedly without routes piling up"
    - "Database write before market-source call in POST/DELETE handlers: if the source call fails, the row still reflects intent and the next startup reconciles from get_active_tickers()"
    - "ticker_has_open_position re-evaluated from the database on every DELETE call (not cached), so a second DELETE always hits the 404 branch and never reaches the source twice"
    - "FailoverMarketDataSource wrapper keeps massive_client.py and simulator.py mutually unaware, preserving the one-directional import graph (factory -> simulator/massive_client; both -> interface/cache/models)"
    - "asyncio.Lock-guarded idempotent swap in FailoverMarketDataSource._on_permanent_failure: a doubled or concurrent callback starts no second simulator"
    - "API key redaction: before logging a Massive exception message, replace any occurrence of self._api_key with [REDACTED], since some providers echo credentials back in auth/URL error text"

key-files:
  created:
    - backend/app/watchlist/__init__.py
    - backend/app/watchlist/router.py
    - backend/app/market/failover.py
    - backend/tests/watchlist/__init__.py
    - backend/tests/watchlist/test_router.py
    - backend/tests/market/test_failover.py
    - frontend/components/WatchlistPanel.tsx
  modified:
    - backend/app/db/connection.py
    - backend/app/db/__init__.py
    - backend/app/main.py
    - backend/app/market/factory.py
    - backend/app/market/massive_client.py
    - backend/app/market/__init__.py
    - backend/tests/market/test_factory.py
    - backend/tests/api/test_health.py
    - backend/tests/api/test_static_frontend.py
    - frontend/app/page.tsx
    - scripts/smoke.sh

key-decisions:
  - "FailoverMarketDataSource wraps a MassiveDataSource rather than massive_client.py importing SimulatorDataSource directly (Pattern 3 in 01-RESEARCH.md) -- keeps both fully-tested modules mutually unaware and preserves the existing one-directional import graph, at the cost of the factory's Massive branch now returning a different concrete type (Pitfall 4, handled by updating the two isinstance assertions in test_factory.py)"
  - "Redact self._api_key from an exception's message text (not just avoid formatting the attribute directly) before logging on permanent failure -- the behavior spec and T-01-11 explicitly require that an exception message which happens to embed the key never reaches a log record, which is a stricter and more realistic threat than only avoiding an explicit self._api_key format arg"
  - "scripts/smoke.sh's exact-match /api/health body assertion updated for the new market_source field -- a Rule 1 fix directly caused by Task 2's health-handler change, not itself in the plan's files_modified list but required for the plan's own verification gate to pass"

patterns-established:
  - "AddTickerRequest Pydantic model with a field_validator that normalizes and rejects out-of-pattern tickers, giving FastAPI's automatic 422 for both empty input and invalid characters without manual exception handling in the route body"

requirements-completed: [WATCH-02, WATCH-03, PORT-05]

coverage:
  - id: D1
    description: "POST /api/watchlist adds a normalized ticker to the database and the running market-data source; a duplicate (including with surrounding whitespace/lowercase) returns 409 with exactly one row surviving; empty/whitespace-only input returns 422 with no row and no source call"
    requirement: "WATCH-02"
    verification:
      - kind: unit
        ref: "backend/tests/watchlist/test_router.py::TestWatchlistRouter::test_post_adds_ticker_normalized_and_to_source"
        status: pass
      - kind: unit
        ref: "backend/tests/watchlist/test_router.py::TestWatchlistRouter::test_post_duplicate_ticker_returns_409_and_keeps_one_row"
        status: pass
      - kind: unit
        ref: "backend/tests/watchlist/test_router.py::TestWatchlistRouter::test_post_empty_ticker_returns_422_no_row_no_source_call"
        status: pass
      - kind: unit
        ref: "backend/tests/watchlist/test_router.py::TestWatchlistRouter::test_post_normalizes_before_duplicate_check"
        status: pass
      - kind: manual_procedural
        ref: "curl -X POST /api/watchlist against a running dev server (this session)"
        status: pass
    human_judgment: false
  - id: D2
    description: "DELETE /api/watchlist/{ticker} removes the row and stops the price feed when no open position holds the ticker; keeps the ticker streaming (row gone from watchlist, still in the source and cache) when an open position holds it; unknown ticker returns 404; a second DELETE for the same ticker hits 404 and never calls the source a second time"
    requirement: "WATCH-03"
    verification:
      - kind: unit
        ref: "backend/tests/watchlist/test_router.py::TestWatchlistRouter::test_delete_with_no_open_position_removes_from_everything"
        status: pass
      - kind: unit
        ref: "backend/tests/watchlist/test_router.py::TestWatchlistRouter::test_delete_with_open_position_keeps_streaming"
        status: pass
      - kind: unit
        ref: "backend/tests/watchlist/test_router.py::TestWatchlistRouter::test_delete_unknown_ticker_returns_404_no_source_call"
        status: pass
      - kind: unit
        ref: "backend/tests/watchlist/test_router.py::TestWatchlistRouter::test_delete_twice_returns_204_then_404_source_called_once"
        status: pass
      - kind: manual_procedural
        ref: "curl -X DELETE /api/watchlist/PYPL twice against a running dev server (this session): 204 then 404"
        status: pass
    human_judgment: false
  - id: D3
    description: "A user can type a ticker into the watchlist panel input and press Enter to add it, and click a per-row remove control to remove it, without tearing down the SSE EventSource; a 409/404 surfaces as a brief inline message"
    requirement: "WATCH-02, WATCH-03"
    verification:
      - kind: unit
        ref: "backend/tests/watchlist/test_router.py::TestWatchlistRouter (API surface WatchlistPanel.tsx calls)"
        status: pass
      - kind: integration
        ref: "npm --prefix frontend run build && bash scripts/smoke.sh"
        status: pass
    human_judgment: true
    rationale: "Automated coverage proves the API contract WatchlistPanel.tsx calls into and that the production build succeeds; visually confirming the inline add/remove UX in a real browser (typing, Enter, the x control, the inline error message) still benefits from a human look before Phase 1 closes."
  - id: D4
    description: "The first Massive API failure of any kind (no retry count, no threshold) permanently trips MassiveDataSource.permanently_failed, invokes the on_permanent_failure callback exactly once, and _poll_loop terminates so no further Massive calls are ever made for the remainder of the process lifetime"
    requirement: "PORT-05"
    verification:
      - kind: unit
        ref: "backend/tests/market/test_failover.py::TestMassivePermanentFailureGuard::test_first_poll_failure_trips_permanently_failed_and_invokes_callback_once"
        status: pass
      - kind: unit
        ref: "backend/tests/market/test_failover.py::TestMassivePermanentFailureGuard::test_no_further_fetch_calls_after_trip_across_multiple_intervals"
        status: pass
      - kind: unit
        ref: "backend/tests/market/test_failover.py::TestMassivePermanentFailureGuard::test_poll_loop_terminates_after_permanent_failure"
        status: pass
    human_judgment: false
  - id: D5
    description: "FailoverMarketDataSource starts with .active as the Massive source and .failed_over False; on permanent failure .active becomes a SimulatorDataSource seeded with the transferred ticker set, .failed_over becomes True, and a doubled or concurrent callback is a no-op that starts no second simulator; add_ticker/remove_ticker/stop route to whichever source is active"
    requirement: "PORT-05"
    verification:
      - kind: unit
        ref: "backend/tests/market/test_failover.py::TestFailoverMarketDataSource::test_starts_with_massive_active_and_not_failed_over"
        status: pass
      - kind: unit
        ref: "backend/tests/market/test_failover.py::TestFailoverMarketDataSource::test_failure_swaps_active_to_simulator_and_transfers_tickers"
        status: pass
      - kind: unit
        ref: "backend/tests/market/test_failover.py::TestFailoverMarketDataSource::test_second_and_concurrent_failure_callback_is_a_no_op"
        status: pass
      - kind: unit
        ref: "backend/tests/market/test_failover.py::TestFailoverMarketDataSource::test_after_failover_add_remove_stop_route_to_simulator_not_massive"
        status: pass
      - kind: unit
        ref: "backend/tests/market/test_failover.py::TestFailoverMarketDataSource::test_price_cache_receives_updates_after_swap"
        status: pass
      - kind: unit
        ref: "backend/tests/market/test_failover.py::TestFailoverMarketDataSource::test_factory_created_source_fails_over_end_to_end"
        status: pass
      - kind: manual_procedural
        ref: "uvicorn run with MASSIVE_API_KEY=obviously-bad-test-key (this session): /api/health flips to simulator after the first failed poll"
        status: pass
    human_judgment: false
  - id: D6
    description: "GET /api/health reports market_source (massive/simulator), reading through FailoverMarketDataSource.active so a completed failover is reported honestly; a Massive exception message that embeds the API key never reaches a log record"
    requirement: "PORT-05"
    verification:
      - kind: unit
        ref: "backend/tests/api/test_health.py::TestHealth::test_returns_200_and_reports_simulator_under_empty_environment"
        status: pass
      - kind: unit
        ref: "backend/tests/market/test_failover.py::TestMassivePermanentFailureGuard::test_exception_message_embedding_api_key_never_reaches_log"
        status: pass
      - kind: manual_procedural
        ref: "grep for the fake key in the uvicorn log output (this session): zero matches"
        status: pass
    human_judgment: false

duration: 55min
completed: 2026-08-23
status: complete
---

# Phase 1 Plan 2: Editable Watchlist + Massive Failover Summary

**Watchlist CRUD (GET/POST/DELETE) wired end to end through DB, source, and UI, plus a permanent Massive-to-simulator failover with API-key log redaction — closing the CONCERNS.md gap where the old code retried a failing provider forever.**

## Performance

- **Duration:** ~55 min
- **Tasks:** 2 of 2 (both `type="auto" tdd="true"`, no checkpoints)
- **Files modified:** 18 (9 created, 9 modified, plus this SUMMARY and REQUIREMENTS.md)

## Accomplishments

- `backend/app/db/connection.py`: `add_watchlist_ticker` (INSERT OR IGNORE, relies on the `UNIQUE(user_id, ticker)` constraint so concurrent adds converge on one row), `remove_watchlist_ticker`, `ticker_has_open_position` — all parameter-bound
- `backend/app/watchlist/router.py`: `create_watchlist_router(get_conn, market_source, price_cache)` factory mirroring `create_stream_router`; `AddTickerRequest` normalizes and rejects invalid tickers via a Pydantic `field_validator`; POST writes the DB before calling the source, DELETE re-evaluates `ticker_has_open_position` from the database on every call so a repeated DELETE can never reach the source twice
- `frontend/components/WatchlistPanel.tsx`: inline add input (Enter to submit) and per-row remove control, refetching `GET /api/watchlist` after each mutation without tearing down the SSE `EventSource`; 409/404 surface as an inline message
- `backend/app/market/failover.py`: `FailoverMarketDataSource` wraps a `MassiveDataSource`, delegates all `MarketDataSource` methods to whichever source is currently active, and swaps to a freshly seeded `SimulatorDataSource` exactly once (`asyncio.Lock`-guarded) on permanent failure, transferring the tracked ticker set
- `backend/app/market/massive_client.py`: `on_permanent_failure` callback + `permanently_failed` property; the very first exception of any kind (no retry count, no threshold) trips the flag, redacts the API key from the exception message if echoed back, awaits the callback, and `_poll_loop` exits so no further Massive calls are ever made
- `backend/app/main.py`: `GET /api/health` now reports `market_source` (`"massive"`/`"simulator"`), reading through `FailoverMarketDataSource.active` so a completed failover is reported honestly instead of still claiming the provider it started with
- 19 new backend tests (9 watchlist router, 10 failover/guard); full backend suite at 124 passing, `ruff check` clean, `failover.py` at 98% and `watchlist/router.py` at 100% statement coverage
- Manually verified both slices end to end against a running dev server: POST/DELETE watchlist round-trip, and a bad `MASSIVE_API_KEY` triggering the permanent failover with the key confirmed absent from the log output

## Task Commits

Each task was committed atomically:

1. **Task 1: Add and remove watchlist tickers end to end** — `d1c6a37` (feat)
2. **Task 2: Permanent Massive failover — one-way trip to the simulator (PORT-05)** — `7dfcad7` (feat)

**Plan metadata:** committed alongside this SUMMARY (see final metadata commit)

## Files Created/Modified

- `backend/app/watchlist/__init__.py`, `backend/app/watchlist/router.py` — watchlist CRUD router
- `backend/app/market/failover.py` — `FailoverMarketDataSource` wrapper
- `backend/tests/watchlist/__init__.py`, `backend/tests/watchlist/test_router.py` — 9 tests covering the full behavior block
- `backend/tests/market/test_failover.py` — 10 tests covering the guard and the wrapper
- `frontend/components/WatchlistPanel.tsx` — inline add/remove watchlist UI
- `backend/app/db/connection.py`, `backend/app/db/__init__.py` — three new watchlist mutation queries, re-exported
- `backend/app/main.py` — router mounted before `app.frontend()`; health handler reports `market_source`
- `backend/app/market/factory.py` — Massive branch wraps in `FailoverMarketDataSource`
- `backend/app/market/massive_client.py` — permanent-failure guard, callback, key redaction
- `backend/app/market/__init__.py` — export `FailoverMarketDataSource`
- `backend/tests/market/test_factory.py` — two `isinstance` assertions updated to check `.active` (Pitfall 4)
- `backend/tests/api/test_health.py`, `backend/tests/api/test_static_frontend.py` — updated for the new health body shape
- `frontend/app/page.tsx` — renders `<WatchlistPanel/>`, holds `selectedTicker` state for Plan 01-03
- `scripts/smoke.sh` — health-body assertion updated for `market_source` (Rule 1 fix)

## Decisions Made

- `FailoverMarketDataSource` wrapper over a direct `massive_client.py -> simulator.py` import, per Pattern 3 in `01-RESEARCH.md` — keeps both fully-tested modules mutually unaware
- API key redaction operates on the exception's rendered message text, not only on avoiding a direct `self._api_key` format argument — the stricter, more realistic mitigation for T-01-11 (a provider might echo the key back in an auth/URL error)
- `scripts/smoke.sh`'s health-body assertion updated as an in-scope Rule 1 fix, since it is the plan's own verification gate and was broken by Task 2's health-handler change

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `scripts/smoke.sh` health-body assertion broke after Task 2's health handler change**
- **Found during:** Task 2, final `bash scripts/smoke.sh` verification run
- **Issue:** `scripts/smoke.sh` asserted `GET /api/health` returned exactly `{"status":"ok"}`; Task 2 added a `market_source` field to that response per the plan's own interface contract, so the exact-match assertion started failing
- **Fix:** Updated the assertion to `{"status":"ok","market_source":"simulator"}`
- **Files modified:** `scripts/smoke.sh`
- **Verification:** `bash scripts/smoke.sh` passes
- **Commit:** `7dfcad7`

**2. [Rule 1 - Bug] `backend/tests/api/test_static_frontend.py` pinned the old exact health body**
- **Found during:** Task 2, `pytest tests/market/ tests/api/` run
- **Issue:** `test_api_health_answers_when_static_has_no_index` asserted `response.json() == {"status": "ok"}`, which broke for the same reason as the smoke script
- **Fix:** Updated to assert `status == "ok"` and `market_source == "simulator"` separately
- **Files modified:** `backend/tests/api/test_static_frontend.py`
- **Verification:** `pytest tests/api/test_static_frontend.py -q` passes
- **Commit:** `7dfcad7`

**3. [Rule 2 - Missing critical functionality] Exception message key-redaction was missing from the first implementation pass**
- **Found during:** Task 2, running the new `test_exception_message_embedding_api_key_never_reaches_log` test against the first draft of the permanent-failure log line
- **Issue:** The initial implementation logged the raw exception message via lazy `%s` formatting (matching the plan's literal action text), but the plan's own `<behavior>` block and threat `T-01-11` require that an exception message which happens to embed the API key never reach a log record — a real scenario when a provider echoes credentials back in an auth/URL error
- **Fix:** Before logging, replace any occurrence of `self._api_key` within the exception's rendered message with `[REDACTED]`
- **Files modified:** `backend/app/market/massive_client.py`
- **Verification:** `test_exception_message_embedding_api_key_never_reaches_log` passes; manually confirmed with a real bad key that the log output contains zero matches for the key string
- **Commit:** `7dfcad7`

---

**Total deviations:** 3 auto-fixed (2 bugs, 1 missing critical functionality)
**Impact on plan:** All three were direct, in-scope consequences of Task 2's health-response and log-safety changes required by the plan's own interface contract and threat register — no scope creep beyond what PORT-05 already specified.

## Issues Encountered

None beyond the deviations above.

## User Setup Required

None — no external service configuration required. `MASSIVE_API_KEY` and `OPENROUTER_API_KEY` remain optional/unused for automated verification; failover was manually spot-checked with a deliberately invalid key.

## Next Phase Readiness

- `backend/app/watchlist/router.py` is the complete WATCH-01/02/03 surface; Plan 01-03 (terminal UI) can build the flash animation, sparkline, and larger per-ticker chart on top of `WatchlistPanel.tsx` and the `selectedTicker` state already threaded through `page.tsx` without touching this plan's wiring
- `FailoverMarketDataSource` is exported from `app.market` and consumed transparently by `app/main.py` — Phase 2 (portfolio) and Phase 3 (AI copilot) never need to know whether the underlying source is Massive or the simulator, only that `app.state.source`/`create_market_data_source(cache)` return something satisfying `MarketDataSource`
- `ticker_has_open_position` is exercised by real tests now (against a manually-inserted `positions` row) even though the `positions` table stays empty in production until Phase 2 wires trade execution — no rework needed when that phase lands
- No blockers identified for Plan 01-03

## Self-Check: PASSED

All new files confirmed tracked in git (`git status --short` clean after both commits): `backend/app/watchlist/__init__.py`, `router.py`, `backend/tests/watchlist/__init__.py`, `test_router.py`, `backend/app/market/failover.py`, `backend/tests/market/test_failover.py`, `frontend/components/WatchlistPanel.tsx`. Both commits (`d1c6a37`, `7dfcad7`) confirmed present in `git log --oneline`. Full backend suite (124 tests), `ruff check`, `npm run build`, and `scripts/smoke.sh` all verified green in this session.

---
*Phase: 01-live-market-terminal*
*Completed: 2026-08-23*
