---
phase: 03-ai-copilot
plan: 01
subsystem: ai-chat
tags: [litellm, openrouter, cerebras, pydantic, fastapi, sqlite, nextjs, vitest, react]
requires:
  - phase: 02-trading-and-portfolio
    provides: execute_trade(), portfolio_view(), get_watchlist_tickers(), the chat_messages/positions/watchlist schema, the create_*_router factory pattern
provides:
  - "POST /api/chat: one non-streaming {message, actions} JSON response per turn"
  - "app/llm/ package: schemas, prompt assembly, LiteLLM/OpenRouter/Cerebras client, LLM_MOCK matcher, two-transaction persistence, router"
  - "Collapsed-by-default bottom chat drawer wired into the trading terminal (frontend/components/ChatDrawer.tsx + children)"
  - "frontend/vitest.config.mts + vitest.setup.ts: the frontend test harness the rest of Phase 3 depends on"
affects: [03-02, 03-03, 03-04]
actuals:
  tokens: 10651
  tasks: 3
  commits: 3
tech-stack:
  added: [litellm>=1.98.0, pydantic>=2.12.5, vitest, "@testing-library/react", "@testing-library/dom", "@testing-library/jest-dom", jsdom, "@vitejs/plugin-react", vite-tsconfig-paths]
  patterns:
    - "Router factory: create_chat_router(get_conn, market_source, price_cache, mock) mirrors create_portfolio_router/create_watchlist_router exactly"
    - "Two-transaction persistence split: save_chat_message(role=user) commits before the awaited LLM call; save_chat_message(role=assistant) commits after -- zero awaits inside either BEGIN/COMMIT"
    - "Execution-derived action reporting: the actions payload is a fixed {trades: [], watchlist_changes: []} in this task, never built from parsed.trades -- the guardrail 03-02 extends with real executor return values"
    - "asyncio.to_thread() wraps the synchronous litellm.completion() call, mirroring app/market/massive_client.py's existing idiom for the Massive SDK"
key-files:
  created:
    - backend/app/llm/__init__.py
    - backend/app/llm/schemas.py
    - backend/app/llm/prompt.py
    - backend/app/llm/client.py
    - backend/app/llm/mock.py
    - backend/app/llm/persistence.py
    - backend/app/llm/router.py
    - backend/tests/llm/__init__.py
    - backend/tests/llm/conftest.py
    - backend/tests/llm/test_router.py
    - frontend/vitest.config.mts
    - frontend/vitest.setup.ts
    - frontend/lib/format.test.ts
    - frontend/hooks/useChat.ts
    - frontend/components/ChatDrawer.tsx
    - frontend/components/ChatMessageList.tsx
    - frontend/components/ChatMessageBubble.tsx
  modified:
    - backend/app/main.py
    - backend/pyproject.toml
    - backend/uv.lock
    - frontend/package.json
    - frontend/package-lock.json
    - frontend/app/page.tsx
key-decisions:
  - "client.py uses `import litellm` + `litellm.completion(...)` instead of the skill's `from litellm import completion` -- required so the CI hermeticity guard's `monkeypatch.setattr('litellm.completion', _raise)` actually intercepts the call; a bound-name import would leave the patched module attribute unreachable from the call site"
  - "app.llm is imported in main.py after cache/source creation, not in the top import block -- importing litellm triggers python-dotenv loading the project-root .env as a side effect, which would otherwise leak MASSIVE_API_KEY into create_market_data_source()'s decision before the environment is read explicitly (see Deviations)"
  - "actions payload is a structural constant ({trades: [], watchlist_changes: []}) in this task, not built from an executor -- 03-02 adds execute_actions() and this becomes execution-derived, never echoed from the model's parsed.trades"
requirements-completed: [CHAT-01, CHAT-04, CHAT-06, UI-08]
coverage:
  - id: D1
    description: "POST /api/chat returns one complete {message, actions} JSON body, never streamed; empty/missing message returns 422 with zero rows persisted"
    requirement: CHAT-01
    verification:
      - kind: integration
        ref: "backend/tests/llm/test_router.py::TestPostChatValidation, ::TestPostChatSuccess::test_happy_path_returns_message_and_empty_actions"
        status: pass
    human_judgment: false
  - id: D2
    description: "chat_messages holds exactly one user row then one assistant row per successful turn; user row survives independently of the LLM call outcome"
    requirement: CHAT-04
    verification:
      - kind: integration
        ref: "backend/tests/llm/test_router.py::TestPostChatSuccess::test_successful_turn_persists_user_then_assistant_row"
        status: pass
      - kind: unit
        ref: "backend/tests/llm/test_router.py::TestLoadRecentChatMessages"
        status: pass
    human_judgment: false
  - id: D3
    description: "Non-ASCII message content (accented character, emoji, CJK) round-trips byte-identical through SQLite TEXT"
    requirement: CHAT-04
    verification:
      - kind: integration
        ref: "backend/tests/llm/test_router.py::TestPostChatSuccess::test_non_ascii_message_round_trips_exactly"
        status: pass
    human_judgment: false
  - id: D4
    description: "LLM_MOCK=true completes a full turn with litellm.completion provably never invoked (autouse hermeticity guard)"
    requirement: CHAT-06
    verification:
      - kind: unit
        ref: "backend/tests/llm/test_router.py::TestHermeticityGuard::test_live_path_hits_blocked_litellm_completion"
        status: pass
      - kind: integration
        ref: "backend/tests/llm/conftest.py::block_real_llm_calls (autouse) -- full tests/llm suite passes with it active"
        status: pass
    human_judgment: false
  - id: D5
    description: "The prompt sent to the model carries this turn's live cash balance and every open position's ticker + unrealized P&L, read fresh from the fixture cache -- never replayed stale from history"
    requirement: CHAT-01
    verification:
      - kind: unit
        ref: "backend/tests/llm/test_router.py::TestBuildMessagesGrounding::test_build_messages_contains_live_cash_and_positions"
        status: pass
    human_judgment: false
  - id: D6
    description: "An LLM response omitting trades/watchlist_changes parses into ChatResponse with two empty lists, never null"
    requirement: CHAT-01
    verification:
      - kind: unit
        ref: "backend/tests/llm/test_router.py::TestChatResponseDefaults::test_omitted_lists_parse_to_empty_never_null"
        status: pass
    human_judgment: false
  - id: D7
    description: "The chat drawer is collapsed on first load, opens only via the fixed bottom-right toggle (label swaps AI Chat / Close Chat), overlays the grid without reflow, and renders both sides of a conversation with alignment-only differentiation"
    requirement: UI-08
    verification:
      - kind: automated_ui
        ref: "npm run build (Next.js static export succeeds, TypeScript checks pass) + npm test (vitest harness green)"
        status: pass
    human_judgment: true
    rationale: "The plan's own Task 3 <human-check> requires a live browser walkthrough (drawer slide, alignment, wrap behavior, and -- with OPENROUTER_API_KEY set -- one real grounded turn) that a parallel worktree executor cannot perform. Per project config human_verify_mode=end-of-phase, this is deferred to end-of-phase human verification rather than blocking this plan's completion. OPENROUTER_API_KEY is already present and non-empty in the project-root .env, so no 03-USER-SETUP.md was generated."
  - id: D8
    description: "vitest test harness (jsdom, @/ alias resolution via tsconfigPaths) runs green, unblocking every later frontend test in Phase 3"
    requirement: UI-08
    verification:
      - kind: unit
        ref: "frontend/lib/format.test.ts -- npm test --prefix frontend"
        status: pass
    human_judgment: false
duration: ~65min
completed: 2026-08-25
status: complete
---

# Phase 3 Plan 1: End-to-End AI Chat Path Summary

**Thinnest complete AI-chat slice: LiteLLM/OpenRouter/Cerebras structured-output call, two-transaction persistence around the one unavoidable await, a `POST /api/chat` router mirroring the existing factory pattern, and a collapsed-by-default bottom chat drawer, all wired end to end and switchable to a deterministic offline matcher via `LLM_MOCK=true`.**

## Performance
- **Duration:** ~65min
- **Started:** 2026-08-25 (continuation agent; Task 1's package-legitimacy checkpoint was approved by the human before this agent was spawned)
- **Completed:** 2026-08-25T15:06:06Z
- **Tasks:** 3/3 (Task 1 gate approved with no commit; Tasks 2-3 executed and committed)
- **Files modified:** 23

## Accomplishments
- A user can POST a message to `/api/chat` and get back one complete, portfolio-grounded reply — `chat_messages` records exactly `user` then `assistant`, with the user row committed *before* the LLM call so it survives a timeout or malformed response.
- `LLM_MOCK=true` runs the full path offline: a keyword matcher (`mock.py`) stands in for the real model, and an autouse `block_real_llm_calls` fixture proves `litellm.completion` is never reached.
- The chat drawer (collapsed by default, bottom-right toggle) overlays the existing trading grid without reflowing it, and renders user/assistant bubbles distinguished only by alignment, per the locked UI-SPEC.
- Stood up `frontend/vitest.config.mts` + `vitest.setup.ts` — the first frontend test runner in this project — unblocking every later Phase 3 frontend test (TEST-04).

## Task Commits
1. **Task 1: Package legitimacy gate** — approved by the human (verbatim "approved") before this agent was spawned; gate-only task, no commit.
2. **Task 2: Install phase dependencies and stand up the frontend test harness** — `bcff1ac` (chore)
3. **Task 3: End-to-end chat turn** — `75bfdb6` (test, RED: failing `tests/llm` suite against nonexistent `app.llm`), `c1042b4` (feat, GREEN: full `app/llm/` package + frontend drawer, all 9 `tests/llm` tests and all 177 backend tests passing, ruff clean, `npm test`/`npm run build` green)

**Plan metadata:** committed separately after this summary (see git log).

## Files Created/Modified
- `backend/app/llm/schemas.py` — `ChatRequest`, `TradeAction`, `WatchlistChange`, `ChatResponse` (structured-output contract, `default_factory=list` so omitted lists parse to `[]` never `None`)
- `backend/app/llm/prompt.py` — `SYSTEM_PROMPT`, `build_portfolio_context()` (reuses `portfolio_view()`), `build_messages()`
- `backend/app/llm/client.py` — `get_chat_response()`: `asyncio.to_thread`-wrapped `litellm.completion()`, `response_format=ChatResponse`, `timeout=30`, `max_tokens=1024`, catches `APITimeoutError`/`ValidationError`/`JSONDecodeError` and returns `None`
- `backend/app/llm/mock.py` — `mock_chat_response()`: commentary-only keyword matcher (D-11); trade/watchlist rules land in 03-02
- `backend/app/llm/persistence.py` — `save_chat_message()`/`load_recent_chat_messages()`: the two-transaction split, zero awaits inside either `BEGIN`/`COMMIT`
- `backend/app/llm/router.py` — `create_chat_router()`, `handle_chat_message()`, `GENERIC_RETRY_MESSAGE`
- `backend/app/main.py` — mounts `POST /api/chat` via `llm_mock_enabled = os.environ.get("LLM_MOCK", "").strip().lower() == "true"`
- `backend/tests/llm/conftest.py`, `test_router.py` — `chat_client` fixture, `block_real_llm_calls` autouse hermeticity guard, 9 tests covering CHAT-01/04/06 and the grounding/persistence contracts
- `frontend/hooks/useChat.ts` — `useChat()`, `ChatMessage`, `ChatActions`, `ExecutedTrade`, `ExecutedWatchlistChange` types
- `frontend/components/ChatDrawer.tsx`, `ChatMessageList.tsx`, `ChatMessageBubble.tsx` — the drawer component tree
- `frontend/app/page.tsx` — `<ChatDrawer />` rendered as a sibling of `<main>`
- `frontend/vitest.config.mts`, `vitest.setup.ts`, `lib/format.test.ts` — the new frontend test harness
- `backend/pyproject.toml`, `uv.lock`, `frontend/package.json`, `package-lock.json` — dependency installs from Task 2

## Decisions Made
- **`litellm.completion(...)` via module attribute, not `from litellm import completion`.** The plan's own acceptance criteria require `backend/tests/llm/conftest.py`'s autouse fixture to `monkeypatch.setattr("litellm.completion", _raise)`. A `from litellm import completion` binding in `client.py` captures the function reference at import time, so patching the `litellm` module's attribute afterward would not affect the already-bound local name — the guard would silently no-op. Importing `litellm` and calling `litellm.completion(...)` (attribute lookup at call time) makes the patch take effect, confirmed by a dedicated test asserting the guard actually raises.
- **`app.llm` import moved below `create_market_data_source(cache)` in `main.py`, not left in the top import block.** See Deviations below — this is a bug fix, not a stylistic choice.
- **No `03-USER-SETUP.md` generated.** `OPENROUTER_API_KEY` is already present and non-empty in the project-root `.env`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `litellm` import order leaked `MASSIVE_API_KEY` from `.env` into market-source selection**
- **Found during:** Task 3, running the full backend suite (`LLM_MOCK=true uv run pytest -q`) after wiring `app.llm` into `main.py`
- **Issue:** `litellm/__init__.py` unconditionally calls `dotenv.load_dotenv()` on import (when `LITELLM_MODE` is unset, which is the default). The project-root `.env` file has a real `MASSIVE_API_KEY` value. With `from app.llm import create_chat_router` in `main.py`'s top import block (textually before `cache = PriceCache(); source = create_market_data_source(cache)`), `MASSIVE_API_KEY` was already present in `os.environ` by the time `create_market_data_source()` read it — silently selecting `FailoverMarketDataSource` (wrapping `MassiveDataSource`) instead of `SimulatorDataSource`, purely because of an unrelated dependency's import-time side effect. This broke `tests/api/test_app_startup.py::TestAppStartup::test_simulator_selected_under_empty_environment`, which asserts the simulator is chosen under an "empty" (no explicitly exported `MASSIVE_API_KEY`) environment.
- **Fix:** Moved `from app.llm import create_chat_router` to execute *after* `cache = PriceCache()` / `source = create_market_data_source(cache)` in `main.py`, with a `# noqa: E402` and an explanatory comment. This preserves the desired side effect (OPENROUTER_API_KEY still gets loaded from `.env` via the same dotenv call, just slightly later — `litellm.completion()` reads `OPENROUTER_API_KEY` from `os.environ` at call time, not at import time, so ordering doesn't affect it) while ensuring market-source selection reads the environment as it existed before any LLM-related import ran.
- **Files modified:** `backend/app/main.py`
- **Verification:** Full backend suite (177 tests) green under `LLM_MOCK=true`; `test_simulator_selected_under_empty_environment` passes.
- **Commit:** `c1042b4`

**2. [Rule 1 - Bug] `client.py` docstring accidentally contained the literal string the acceptance criteria forbid**
- **Found during:** Task 3, running the acceptance-criteria grep gate (`! grep -q 'asyncio.wait_for' backend/app/llm/client.py`)
- **Issue:** A docstring explaining *why* no outer timeout wrapper is used named the forbidden API directly (`asyncio.wait_for`), which the plan's acceptance criteria greps for as a negative check (to catch an actual second-timeout bug, not prose mentioning it).
- **Fix:** Reworded the docstring to describe the same constraint ("no additional outer timeout wrapper") without the literal API name.
- **Files modified:** `backend/app/llm/client.py`
- **Verification:** `! grep -q 'asyncio.wait_for' backend/app/llm/client.py` passes; full suite still green.
- **Commit:** `c1042b4`

**Total deviations:** 2 auto-fixed (both Rule 1 — bugs). **Impact on plan:** None on scope or architecture; both were caught and fixed before the GREEN commit, with the full test suite as evidence.

## Issues Encountered
None beyond the two auto-fixed deviations above.

## Known Stubs

- **`actions` payload is always `{"trades": [], "watchlist_changes": []}`.** `handle_chat_message()` in `backend/app/llm/router.py` never calls a trade/watchlist executor in this task — there isn't one yet. This is explicit, intentional, and documented in the plan itself: "This task there are no executors yet, so it is `{"trades": [], "watchlist_changes": []}`; plan 03-02 fills it from `execute_actions` return values." `mock.py` likewise implements only the commentary-keyword rules (D-11); the trade/watchlist pattern rules and the shared 12-scenario fixture table are explicitly deferred to plan 03-02 per the plan text. Not a defect — the next wave's starting point.
- **Trade confirmation cards, quick-prompt buttons, and drawer-open history fetch are not built in this task.** The plan's `<files>` list for Task 3 scopes only the message-send/receive path; `03-UI-SPEC.md`'s D-04/D-05 (confirmation cards), D-07/D-08 (quick-prompts), and the drawer-open history GET endpoint are UI-SPEC features not required by this plan's `must_haves`/`acceptance_criteria` and are left for later plans in this phase.

## User Setup Required
None — `OPENROUTER_API_KEY` is already present and non-empty in the project-root `.env`; no `03-USER-SETUP.md` was generated.

## Next Phase Readiness
Ready for 03-02, 03-03. This is wave 1 of 3 in Phase 3 — the `app/llm/` package, the chat router, `chat_messages` persistence discipline, and the frontend drawer/hook/test-harness scaffolding are all in place for 03-02 to add trade/watchlist auto-execution (the `executor.py` module and the 12-scenario fixture table) and for 03-03/03-04 to build on the same drawer component tree and vitest harness.

## Self-Check: PASSED
All 17 created files verified present and tracked (`git ls-files`); all 3 task
commits verified present in git log (`bcff1ac`, `75bfdb6`, `c1042b4`).

---
*Phase: 03-ai-copilot*
*Completed: 2026-08-25*
