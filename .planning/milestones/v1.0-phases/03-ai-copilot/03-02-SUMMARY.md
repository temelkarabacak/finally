---
phase: 03-ai-copilot
plan: 02
subsystem: ai-chat
tags: [pydantic, fastapi, sqlite, react, vitest, tailwind]
requires:
  - phase: 03-ai-copilot
    provides: "03-01's app/llm/ package (schemas, router, mock.py commentary rules, persistence, ChatDrawer/useChat/ChatMessageBubble/ChatMessageList scaffolding)"
  - phase: 02-trading-and-portfolio
    provides: execute_trade(), TradeError, watchlist/router.py's add/remove rejection rules, add_watchlist_ticker/remove_watchlist_ticker/ticker_has_open_position
provides:
  - "app/llm/executor.py: execute_actions() and apply_watchlist_change() -- composition over execute_trade()/watchlist helpers, never re-implementing validation"
  - "The 12-scenario reference dataset (tests/llm/fixtures/chat_scenarios.py) backing D-11's mock matcher, shared by mock/router/eval tests"
  - "Execution-derived actions payload: HTTP response + persisted chat_messages.actions built only from executor return values"
  - "Inline TradeConfirmationCard (success/REJECTED variants) wired into ChatMessageBubble, with onActionsExecuted refreshing the portfolio panels on a chat-executed fill"
affects: [03-04]
actuals:
  tokens: 9871
  tasks: 3
  commits: 5
tech-stack:
  added: []
  patterns:
    - "Executor composition, not reimplementation: apply_watchlist_change() and execute_actions() call the exact same execute_trade()/add_watchlist_ticker()/remove_watchlist_ticker()/ticker_has_open_position() the manual endpoints call -- zero LLM-path-specific validation"
    - "Execution-derived action reporting: the actions payload the client and chat_messages.actions both see is built exclusively from execute_actions()'s return value; parsed.trades/parsed.watchlist_changes never touch the response (T-03-11, EV-1)"
    - "No outer BEGIN around execute_trade()/apply_watchlist_change() calls -- each already owns its own transaction; wrapping them nests and SQLite raises OperationalError (03-RESEARCH.md Pitfall 1)"
    - "Deterministic mock trade/watchlist regex rules in a fixed order: trade and watchlist patterns checked first, commentary/fallback only when neither matched"
key-files:
  created:
    - backend/tests/llm/fixtures/__init__.py
    - backend/tests/llm/fixtures/chat_scenarios.py
    - backend/tests/llm/test_mock.py
    - backend/app/llm/executor.py
    - backend/tests/llm/test_executor.py
    - frontend/components/TradeConfirmationCard.tsx
    - frontend/components/TradeConfirmationCard.test.tsx
  modified:
    - backend/app/llm/mock.py
    - backend/app/llm/router.py
    - backend/app/llm/__init__.py
    - frontend/components/ChatMessageBubble.tsx
    - frontend/hooks/useChat.ts
    - frontend/components/ChatDrawer.tsx
    - frontend/app/page.tsx
    - frontend/vitest.setup.ts
    - .planning/REQUIREMENTS.md
key-decisions:
  - "handle_chat_message()'s return type changed from ChatResponse | None to tuple[ChatResponse | None, dict | None] so post_chat can return the real execute_actions() output instead of 03-01's hardcoded {trades: [], watchlist_changes: []} stub -- no other call site existed to break"
  - "vitest.setup.ts gained an explicit afterEach(cleanup) -- vitest.config.mts doesn't set test.globals, so @testing-library/react's own auto-cleanup detection never fired; without it, DOM from one test in a file leaked into the next (first component-rendering test in this project, format.test.ts never needed it)"
  - "CHAT-02 and CHAT-03 marked Complete in REQUIREMENTS.md (verified unique to this plan by grepping every 03-*-PLAN.md's requirements: frontmatter); CHAT-06 and UI-08 left Pending -- both are shared with 03-01/03-04 and only the orchestrator should flip a shared ID"
requirements-completed: [CHAT-02, CHAT-03, CHAT-06, UI-08]
coverage:
  - id: D1
    description: "The 12-scenario reference dataset is on disk and the mock matcher reproduces every text-driven scenario deterministically, including fractional-quantity preservation and empty-action-list advice/analysis turns"
    requirement: CHAT-06
    verification:
      - kind: unit
        ref: "backend/tests/llm/test_mock.py (13 tests, parametrized over the 10 text-driven CHAT_SCENARIOS entries plus determinism/fractional/advice assertions)"
        status: pass
    human_judgment: false
  - id: D2
    description: "A chat-requested buy the account can afford fills through execute_trade() and the actions payload carries the real fill price"
    requirement: CHAT-02
    verification:
      - kind: unit
        ref: "backend/tests/llm/test_executor.py::TestExecuteActionsTrades::test_affordable_buy_returns_success_with_fill_price"
        status: pass
    human_judgment: false
  - id: D3
    description: "A trade exceeding cash or held quantity is rejected outright with TradeError.detail as the reason -- never clamped, no trades row written, position quantity unchanged"
    requirement: CHAT-02
    verification:
      - kind: unit
        ref: "backend/tests/llm/test_executor.py::TestExecuteActionsTrades::test_over_cash_buy_rejected_with_reason_and_no_trade_row, ::test_over_holding_sell_rejected_and_position_unchanged"
        status: pass
    human_judgment: false
  - id: D4
    description: "A successful chat-executed buy of a ticker absent from the watchlist calls market_source.add_ticker, exactly as the manual POST /api/portfolio/trade path does"
    requirement: CHAT-02
    verification:
      - kind: unit
        ref: "backend/tests/llm/test_executor.py::TestExecuteActionsTrades::test_successful_buy_of_unwatched_ticker_calls_add_ticker"
        status: pass
    human_judgment: false
  - id: D5
    description: "Watchlist add/remove mirrors watchlist/router.py's own rejection and idempotency rules exactly; removing a ticker with an open position leaves it tracked (no market_source.remove_ticker call)"
    requirement: CHAT-03
    verification:
      - kind: unit
        ref: "backend/tests/llm/test_executor.py::TestApplyWatchlistChange (add-already-present, remove-not-present, remove-with-open-position)"
        status: pass
    human_judgment: false
  - id: D6
    description: "A turn carrying two trades and one watchlist change produces three entries and raises no sqlite3.OperationalError (no nested BEGIN)"
    requirement: CHAT-02
    verification:
      - kind: unit
        ref: "backend/tests/llm/test_executor.py::TestExecuteActionsMultiAction::test_two_trades_plus_watchlist_change_returns_three_entries"
        status: pass
    human_judgment: false
  - id: D7
    description: "The actions payload returned to the client and persisted to chat_messages.actions is constructed only from execute_actions()/apply_watchlist_change() return values -- the model's proposed trades/watchlist_changes lists are never echoed"
    requirement: CHAT-02
    verification:
      - kind: other
        ref: "static grep evidence: '! grep -Eq \"parsed\\.trades\" backend/app/llm/router.py' exits 0"
        status: pass
      - kind: unit
        ref: "backend/tests/llm/test_executor.py::TestExecutionDerivedPersistence::test_rejected_trade_persists_success_false_and_reason"
        status: pass
    human_judgment: false
  - id: D8
    description: "Executed trades render inline as distinct cards below the assistant's message: green left border + fill price for a success, red left border + REJECTED label + reason for a rejection; zero trades render no cards, N trades render N stacked cards, a user message never renders a card"
    requirement: UI-08
    verification:
      - kind: automated_ui
        ref: "frontend/components/TradeConfirmationCard.test.tsx (7 tests: success/rejected rendering, fractional precision, zero/three-card stacking, user-message exclusion) -- npm test"
        status: pass
    human_judgment: false
  - id: D9
    description: "A chat-executed fill refreshes the header/positions/heatmap/P&L panels the same pass a manual TradeBar fill does, via onActionsExecuted wired to usePortfolio's refresh"
    requirement: UI-08
    verification:
      - kind: other
        ref: "frontend/app/page.tsx contains onActionsExecuted={refresh}; npm run build succeeds (TypeScript check passes)"
        status: pass
    human_judgment: false
  - id: D10
    description: "Live-browser walkthrough: chat-executed buy shows a green fill card and drops cash; chat-executed over-budget buy shows a red REJECTED card with the trade-bar's own wording and cash unchanged; chat watchlist add starts PYPL streaming with no card; portfolio analysis returns no card"
    requirement: UI-08
    verification: []
    human_judgment: true
    rationale: "The plan's own Task 3 <human-check> requires a live browser walkthrough that a parallel worktree executor cannot perform. Per project config human_verify_mode=end-of-phase, this is deferred to end-of-phase human verification rather than blocking this plan's completion, matching 03-01's D7 precedent."
duration: ~70min
completed: 2026-08-25
status: complete
---

# Phase 3 Plan 2: Chat-Driven Trade & Watchlist Auto-Execution Summary

**LLM-proposed trades and watchlist changes now auto-execute through the exact `execute_trade()`/watchlist helpers the manual trade bar and watchlist panel call, with the reported actions payload built exclusively from executor return values and rendered inline as success/REJECTED confirmation cards in the chat.**

## Performance

- **Duration:** ~70min
- **Started:** 2026-08-25
- **Completed:** 2026-08-25
- **Tasks:** 3/3
- **Files modified:** 15 (backend: 8, frontend: 6, planning: 1)

## Accomplishments
- Locked the 12-scenario reference dataset (`tests/llm/fixtures/chat_scenarios.py`) backing decision D-11, and extended `mock.py`'s deterministic matcher with trade/watchlist regex rules alongside 03-01's commentary rules — fractional quantities preserved exactly, no ticker or quantity ever invented.
- Built `app/llm/executor.py`: `execute_actions()` and `apply_watchlist_change()` call the unmodified `execute_trade()`/`add_watchlist_ticker()`/`remove_watchlist_ticker()`/`ticker_has_open_position()` — the LLM path has zero validation privilege over the manual path, and a rejected trade is reported honestly (never clamped).
- Wired the executor into `router.py`'s `handle_chat_message()`: both the HTTP `actions` body and the persisted `chat_messages.actions` JSON are now built entirely from `execute_actions()`'s return value, structurally closing the "claimed but not executed" failure mode (T-03-11, AI-SPEC EV-1).
- Added inline `TradeConfirmationCard` (success = green left border + fill price; rejected = red left border + REJECTED label + `execute_trade()`'s own reason string) into `ChatMessageBubble`, and wired `usePortfolio`'s `refresh` into the chat drawer via a new `onActionsExecuted` hook option so a chat-executed fill updates the same panels a manual fill does.

## Task Commits

Each task was committed atomically; Tasks 2-3 followed RED-GREEN (no REFACTOR commit needed — GREEN code was already clean):

1. **Task 1: Lock the 12-scenario reference dataset and complete the mock rule table** — `48e82de` (feat)
2. **Task 2: Auto-execute LLM-proposed trades and watchlist changes** — `3ecb0b4` (test, RED), `5654555` (feat, GREEN)
3. **Task 3: Inline trade confirmation cards in the chat transcript** — `cf71ed9` (test, RED), `8d60d87` (feat, GREEN)

**Plan metadata:** committed separately after this summary (see git log).

## Files Created/Modified
- `backend/tests/llm/fixtures/chat_scenarios.py` — `CHAT_SCENARIOS`, the 12-scenario dataset (plain dicts, no import cycle with `app.llm.mock`)
- `backend/app/llm/mock.py` — extended with `_TRADE_RE`/`_WATCHLIST_RE` regex rules and sentence-assembly helpers, applied before the existing commentary/fallback rules
- `backend/tests/llm/test_mock.py` — parametrized over the 10 text-driven scenarios plus determinism/fractional/advice-scope assertions
- `backend/app/llm/executor.py` — `apply_watchlist_change()`, `execute_actions()`, `_execute_one_trade()`
- `backend/tests/llm/test_executor.py` — CHAT-02/03 coverage: fills, rejections, unwatched-buy tracking, watchlist idempotency, position-held retention, multi-action turns, execution-derived persistence
- `backend/app/llm/router.py` — `handle_chat_message()` now returns `(parsed, actions)`; `post_chat` returns the real `actions` instead of the hardcoded empty stub; per-turn log line reports real trade/rejected/watchlist counts
- `backend/app/llm/__init__.py` — re-exports `execute_actions`/`apply_watchlist_change`
- `frontend/components/TradeConfirmationCard.tsx` — success/REJECTED card variants, `data-testid="trade-card"`/`"trade-card-rejected"`
- `frontend/components/TradeConfirmationCard.test.tsx` — 7 tests covering both variants plus `ChatMessageBubble` stacking/exclusion behavior
- `frontend/components/ChatMessageBubble.tsx` — renders one `TradeConfirmationCard` per `actions.trades` entry below the message text
- `frontend/hooks/useChat.ts` — `useChat()` accepts an optional `onActionsExecuted` callback
- `frontend/components/ChatDrawer.tsx` — forwards `onActionsExecuted` to `useChat()`
- `frontend/app/page.tsx` — `<ChatDrawer onActionsExecuted={refresh} />`
- `frontend/vitest.setup.ts` — registers `afterEach(cleanup)` (deviation, see below)
- `.planning/REQUIREMENTS.md` — CHAT-02/CHAT-03 marked Complete

## Decisions Made
- `handle_chat_message()`'s return type changed to `tuple[ChatResponse | None, dict | None]` — the only way for `post_chat` to surface the real `execute_actions()` output without calling the executor a second time (which would double-execute trades).
- CHAT-02 and CHAT-03 marked Complete by hand in `REQUIREMENTS.md`; CHAT-06 and UI-08 left Pending. Verified by grepping every `03-*-PLAN.md`'s `requirements:` frontmatter: CHAT-02/CHAT-03 appear only in this plan, CHAT-06 is shared with 03-01, UI-08 is shared with 03-01 and 03-04 — the `gsd-tools` CLI was unavailable in this fresh worktree checkout (missing build artifact), so shared IDs were left for the orchestrator per protocol rather than hand-flipped.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `vitest.setup.ts` missing `afterEach(cleanup)` caused DOM leakage across tests in the same file**
- **Found during:** Task 3, first `npm test` run after writing `TradeConfirmationCard.tsx`
- **Issue:** `vitest.config.mts` does not set `test.globals: true`, so `@testing-library/react`'s own auto-cleanup detection (which looks for a global `afterEach`) never registers. `format.test.ts` (03-01) never rendered a DOM node, so this was latent until this plan's `TradeConfirmationCard.test.tsx` became the first component-rendering test — counts of rendered cards accumulated across tests within the file (2, then 6, then 4, instead of 0/3/0).
- **Fix:** Added `import { afterEach } from "vitest"; import { cleanup } from "@testing-library/react"; afterEach(() => cleanup());` to `vitest.setup.ts`.
- **Files modified:** `frontend/vitest.setup.ts`
- **Verification:** All 7 `TradeConfirmationCard.test.tsx` assertions pass in isolation and together; full `npm test` (7/7) and `npm run build` green.
- **Committed in:** `8d60d87` (Task 3 GREEN commit)

**2. [Rule 3 - Blocking] `npm install` had never been run in this fresh worktree checkout**
- **Found during:** Task 3, first `npm test` invocation (`sh: 1: vitest: not found`)
- **Issue:** The worktree's `frontend/node_modules` did not exist — a fresh git worktree checkout does not carry over installed dependencies from the main working tree.
- **Fix:** Ran `npm install --prefix frontend`. No `package.json`/`package-lock.json` changes resulted (dependencies were already correctly declared by 03-01), so nothing new was staged.
- **Files modified:** none (node_modules is gitignored)
- **Verification:** `npm test` and `npm run build` both run and pass afterward.

---

**Total deviations:** 2 auto-fixed (both Rule 3 — blocking issues). **Impact on plan:** None on scope or architecture; both were environment/infra gaps caught and fixed before their respective GREEN commits.

## Issues Encountered
`gsd-tools.cjs` reported `GSD runtime library is not built and cannot be auto-built` when attempting `requirements.ready-ids` in this fresh worktree — handled per the plan's own fallback instructions (see Decisions Made above).

## Known Stubs
None — the `actions` payload stub 03-01 documented ("`{"trades": [], "watchlist_changes": []}` always") is resolved by this plan's `execute_actions()` wiring; `mock.py`'s trade/watchlist rules were the other 03-01-documented stub, also resolved here.

## User Setup Required
None — no new external service configuration required.

## Next Phase Readiness
Ready for 03-04 (malformed-output/timeout router tests, TEST-02/03/04 backfill). Scenarios 11-12 of `CHAT_SCENARIOS` (raw-payload/timeout fixtures, no `user_text`) are already on disk for 03-04 to consume. The `execute_actions()`/`apply_watchlist_change()` surface is stable and composition-only, so 03-04's router-level tests can exercise it without further executor changes.

## Self-Check: PASSED
All 7 created files verified present (`git ls-files`); all 5 task commits
(`48e82de`, `3ecb0b4`, `5654555`, `cf71ed9`, `8d60d87`) verified present in
`git log --oneline`.

---
*Phase: 03-ai-copilot*
*Completed: 2026-08-25*
