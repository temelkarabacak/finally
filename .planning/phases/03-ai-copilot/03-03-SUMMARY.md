---
phase: 03-ai-copilot
plan: 03
subsystem: testing
tags: [pytest, vitest, testing-library, fastapi, react, jsdom]

# Dependency graph
requires:
  - phase: 03-01
    provides: chat-half TEST-03/TEST-04 test scaffolding and conventions
provides:
  - Exhaustive portfolio/watchlist route status-code and response-shape matrix (backend)
  - First frontend component test (WatchlistPanel.test.tsx) and first frontend hook test (usePortfolio.test.ts)
  - A jsdom AnimationEvent polyfill and explicit RTL cleanup, both required for any future frontend test that touches animation events or renders multiple times in one file
affects: [03-04, 04-deployment]

# Actuals (#2632)
actuals:
  tokens: 5350
  tasks: 2
  commits: 4

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "vitest.setup.ts polyfills browser APIs jsdom omits (AnimationEvent) so React-DOM's feature detection matches real-browser behavior"
    - "Explicit afterEach(cleanup) from @testing-library/react in test files, since vitest.config.mts has no globals:true to trigger RTL's automatic cleanup registration"
    - "Row-level data-testid of the form {component}-row-{key} for disambiguating repeated rows in a grid under test"

key-files:
  created:
    - frontend/components/WatchlistPanel.test.tsx
    - frontend/hooks/usePortfolio.test.ts
  modified:
    - backend/tests/portfolio/test_router.py
    - backend/tests/watchlist/test_router.py
    - frontend/components/WatchlistPanel.tsx
    - frontend/vitest.setup.ts

key-decisions:
  - "Polyfilled window.AnimationEvent in vitest.setup.ts rather than working around it per-test: jsdom has no AnimationEvent constructor, so React-DOM's vendor-prefix feature detection (react-dom-client.development.js) silently registers a vendor-prefixed listener instead of the standard 'animationend', meaning onAnimationEnd handlers never fire in tests without this fix. The setup file is the only place a fix can land before react-dom's first import."
  - "Added explicit afterEach(cleanup) in WatchlistPanel.test.tsx rather than editing the shared vitest.config.mts: vitest.config.mts lacks globals:true, so React Testing Library's automatic cleanup registration never triggers, and DOM from one test leaks into the next, causing 'multiple elements' errors on data-testid queries."
  - "requirements-completed left empty: TEST-03 and TEST-04 are each split across this plan (portfolio/watchlist half, non-chat half) and 03-04 (chat half). REQUIREMENTS.md traceability stays Pending until both halves land."

patterns-established:
  - "Backend router tests assert exact response-body key sets via set(body.keys()) == {...} rather than spot-checking individual keys, catching both missing and unexpected fields"
  - "Frontend fetch-dependent components are tested by stubbing global.fetch per test with vi.fn() and asserting on recorded call arguments (URL, method, body), never on network effects"

requirements-completed: []

coverage:
  - id: D1
    description: "Every portfolio and watchlist route has proven success and failure status codes plus exact response-shape assertions"
    requirement: "TEST-03"
    verification:
      - kind: unit
        ref: "backend/tests/portfolio/test_router.py"
        status: pass
      - kind: unit
        ref: "backend/tests/watchlist/test_router.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "Backend suite is order-independent: whole-suite and per-directory pytest runs agree"
    requirement: "TEST-03"
    verification:
      - kind: unit
        ref: "pytest tests/portfolio -q && pytest tests/watchlist -q && pytest -q"
        status: pass
    human_judgment: false
  - id: D3
    description: "Price flash (up/down/none) and animation-end clearing are covered by automated frontend tests"
    requirement: "TEST-04"
    verification:
      - kind: unit
        ref: "frontend/components/WatchlistPanel.test.tsx"
        status: pass
    human_judgment: false
  - id: D4
    description: "Watchlist add/remove CRUD, including 409 and 404 branches, is covered by automated frontend tests"
    requirement: "TEST-04"
    verification:
      - kind: unit
        ref: "frontend/components/WatchlistPanel.test.tsx"
        status: pass
    human_judgment: false
  - id: D5
    description: "Portfolio revalue() calculation and formatCurrency display precision are covered by automated frontend tests"
    requirement: "TEST-04"
    verification:
      - kind: unit
        ref: "frontend/hooks/usePortfolio.test.ts"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-08-25
status: complete
---

# Phase 3 Plan 3: Route Matrix and First Frontend Test Coverage Summary

**Exhaustive portfolio/watchlist route status-code and response-shape matrix in pytest, plus the project's first frontend component test (WatchlistPanel) and first frontend hook test (usePortfolio), all offline and hermetic.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-08-25T15:12:01Z
- **Completed:** 2026-08-25T15:27:16Z
- **Tasks:** 2
- **Files modified:** 6 (2 created, 4 modified)

## Accomplishments

- `backend/tests/portfolio/test_router.py` and `backend/tests/watchlist/test_router.py` now assert every documented status code (200/201/204/400/404/409/422) and the exact response-body key set for every portfolio and watchlist route, closing every gap identified by auditing the routers against the existing tests
- Proved the backend suite is order-independent: `pytest tests/portfolio -q`, `pytest tests/watchlist -q`, and the full `pytest -q` (183 tests) all pass independently
- `frontend/components/WatchlistPanel.test.tsx` — the project's first component test — covers price flash up/down/none, animation-end clearing, and add/remove CRUD including the 409/404 error branches
- `frontend/hooks/usePortfolio.test.ts` — the project's first hook test — covers `revalue()`'s market-value/P&L math (including the avg_cost=0 edge case and fractional quantities) and `formatCurrency`'s two-decimal, thousands-separated, en-US-pinned output
- Fixed two frontend test-environment gaps that blocked the plan's own acceptance criteria: RTL cleanup was never registered (no `globals: true`), and jsdom's missing `AnimationEvent` constructor silently broke every `onAnimationEnd` handler in tests

## Task Commits

Each task was committed atomically:

1. **Task 1: Complete the portfolio and watchlist route status-code and response-shape matrix** - `13140c2` (test)
2. **Task 2: First frontend coverage — price flash, watchlist CRUD, and portfolio calculations** - RED `b8ea13e` (test) → GREEN `ea2e1a1` (feat) → fix `0c09076` (fix)

**Plan metadata:** (this commit)

_Note: Task 2 followed RED/GREEN with an additional `fix` commit for test-infrastructure gaps discovered while validating GREEN (see Deviations)._

## Files Created/Modified

- `backend/tests/portfolio/test_router.py` - added per-position key-set assertion, history point-shape assertion, insufficient-shares 400, digit/space ticker 422s, fractional-quantity echo
- `backend/tests/watchlist/test_router.py` - added exact entry key-set assertions on GET/POST, 409 detail-string assertion, invalid-character ticker 422, DELETE empty-body assertion
- `frontend/components/WatchlistPanel.test.tsx` - new; 8 tests covering flash-up/flash-down/no-flash, animationEnd clearing, add/remove CRUD with 409/404 branches
- `frontend/components/WatchlistPanel.tsx` - added `data-testid={\`watchlist-row-${ticker}\`}` to the row `<tr>`, the plan's single production change
- `frontend/hooks/usePortfolio.test.ts` - new; covers `revalue()` and `formatCurrency`
- `frontend/vitest.setup.ts` - added a `window.AnimationEvent` polyfill so React-DOM's animation-event feature detection matches a real browser

## Decisions Made

- Polyfilled `AnimationEvent` in `vitest.setup.ts` instead of testing `clearFlash` some other way (e.g. reaching into the fiber tree): the polyfill fixes the actual environment gap once, for every future test that touches CSS animation events, rather than working around it locally in one test file
- Added `afterEach(cleanup)` directly in `WatchlistPanel.test.tsx` rather than editing the shared `vitest.config.mts` to add `globals: true`: scopes the fix to the file that needs it without changing global test semantics (e.g. auto-injected globals) for the rest of the suite
- Split Task 2's implementation into a pure `feat` commit (the one-line testid) and a separate `fix` commit (test-infrastructure gaps), rather than folding the fixes into the `feat` commit, so the single production change stays exactly as small and reviewable as the plan describes

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] React Testing Library cleanup never ran between tests**
- **Found during:** Task 2 (running the new `WatchlistPanel.test.tsx` after the GREEN implementation)
- **Issue:** `vitest.config.mts` has no `globals: true`, so RTL's automatic `afterEach` cleanup registration (which relies on detecting a global test framework hook) never fires. DOM from earlier tests in the file persisted into later tests, so `screen.getByTestId("watchlist-row-AAPL")` started matching multiple elements and every test after the first failed.
- **Fix:** Added `afterEach(cleanup)` explicitly in `WatchlistPanel.test.tsx`, importing `cleanup` from `@testing-library/react`.
- **Files modified:** `frontend/components/WatchlistPanel.test.tsx`
- **Verification:** All 8 WatchlistPanel tests pass in isolation and as a suite; re-ran `npm test` to confirm no cross-test contamination.
- **Committed in:** `0c09076`

**2. [Rule 3 - Blocking] jsdom has no `AnimationEvent`, so `onAnimationEnd` never fires in tests**
- **Found during:** Task 2 (the "clears the flash class when the CSS animation ends" test, after fixing the cleanup issue above)
- **Issue:** React-DOM feature-detects `"AnimationEvent" in window` at module load to choose between listening for the standard `animationend` event or a vendor-prefixed fallback (`react-dom-client.development.js`). jsdom does not define `AnimationEvent`, so React silently registered a vendor-prefixed listener; a correctly constructed and dispatched `animationend` event (via both `fireEvent.animationEnd` and a raw `dispatchEvent`) never reached the `onAnimationEnd` handler. Confirmed root cause with an isolated minimal repro before applying the fix, per CLAUDE.md's root-cause-first debugging rule.
- **Fix:** Added a `window.AnimationEvent` polyfill (aliased to the native `Event` constructor) in `vitest.setup.ts`, which runs before any test file's imports — and therefore before react-dom's own module-level detection.
- **Files modified:** `frontend/vitest.setup.ts`
- **Verification:** The animationEnd test now passes; full suite re-run confirms no regression (16/16 passing).
- **Committed in:** `0c09076`

---

**Total deviations:** 2 auto-fixed (both Rule 3 — blocking test-infrastructure gaps, not plan-scope changes)
**Impact on plan:** Both fixes were required for the plan's own frontend acceptance criteria to be provable at all; no production behavior changed beyond the plan's single specified `data-testid` addition.

## Issues Encountered

- Frontend `node_modules` was absent in this fresh worktree checkout (`npm test`/`npm run build` failed with `ERR_MODULE_NOT_FOUND`). Ran `npm install` in `frontend/` before writing any tests — this matches the plan's expected environment and is not a deviation, just first-run setup in an isolated worktree.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- This plan closes the whole-app test backfill (portfolio/watchlist route matrix, first frontend component and hook tests) independently of 03-04 — no blocking dependency either direction.
- TEST-03 and TEST-04 in `REQUIREMENTS.md` stay `Pending` in traceability: each is split across this plan (portfolio/watchlist half, non-chat half) and 03-04 (chat half). The orchestrator should mark both `Complete` only once 03-04's chat-route and chat-panel coverage also lands.
- `requirements.ready-ids` and `commit-to-subrepo`/`commit` CLI verbs were unavailable in this worktree (`GSD runtime library is not built`); this SUMMARY and `REQUIREMENTS.md` (unchanged) were committed via plain `git add`/`git commit` instead, per the plan's documented fallback.
- The `vitest.setup.ts` `AnimationEvent` polyfill and the `afterEach(cleanup)` pattern in `WatchlistPanel.test.tsx` are now available precedent for any future frontend test in `frontend/components/` or `frontend/hooks/` that renders more than once per test file or touches CSS animation events (relevant to 03-04's chat panel loading-state tests and future Phase 4 work).

---
*Phase: 03-ai-copilot*
*Completed: 2026-08-25*
