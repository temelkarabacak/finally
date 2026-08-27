---
phase: 03-ai-copilot
plan: 04
subsystem: ai-chat
tags: [fastapi, pydantic, sqlite, litellm, react, vitest, tailwind]
requires:
  - phase: 03-ai-copilot
    provides: "03-01's app/llm/ package (client.py, router.py, persistence.py, schemas.py) and drawer/hook scaffolding; 03-02's execute_actions()/TradeConfirmationCard"
provides:
  - "GET /api/chat/history: persisted transcript reader, bounded limit query param (1-200), 200+[] on an empty database"
  - "load_chat_history() in app/llm/persistence.py -- distinct from load_recent_chat_messages(), the model-context reader"
  - "Proven degradation contract: timeout and four classes of malformed structured output collapse to one identical GENERIC_RETRY_MESSAGE body, zero trades executed, zero assistant rows persisted"
  - "backend/scripts/llm_smoke_check.py: standalone developer script for the one live check mock mode cannot provide"
  - "Chat drawer starter experience: first-open-only history fetch, three quick-prompt buttons, Loading conversation.../Thinking... states, and an inline red-bordered error bubble shared by both the backend's 200-degraded reply and a genuine network/transport failure"
affects: [03-05, 04]
actuals:
  tokens: 11918
  tasks: 3
  commits: 6
tech-stack:
  added: []
  patterns:
    - "Two transcript readers, one table: load_chat_history() (role/content/actions, for the UI) stays structurally separate from load_recent_chat_messages() (role/content only, for the model context) so the model prompt can never replay a prior turn's actions payload"
    - "Frontend degradation detection by string equality: useChat.ts's GENERIC_RETRY_MESSAGE constant is used two ways -- to synthesize a message when no backend body is available at all (thrown fetch, non-ok status), and to detect -- by comparing body.message against it -- that a 200 response IS the backend's own degraded reply, marking it errored for the red-bordered bubble"
    - "Standalone script convention (backend/scripts/): __main__ guard, no pytest import, documents its network/cost requirement in the module docstring, matches market_data_demo.py's existing shape"
key-files:
  created:
    - backend/tests/llm/test_persistence.py
    - backend/tests/llm/test_schemas.py
    - backend/tests/llm/test_client.py
    - backend/scripts/llm_smoke_check.py
    - frontend/components/ChatDrawer.test.tsx
  modified:
    - backend/app/llm/persistence.py
    - backend/app/llm/router.py
    - backend/app/llm/__init__.py
    - backend/tests/llm/test_router.py
    - frontend/hooks/useChat.ts
    - frontend/components/ChatDrawer.tsx
    - frontend/components/ChatMessageList.tsx
    - frontend/components/ChatMessageBubble.tsx
    - .planning/REQUIREMENTS.md
key-decisions:
  - "Task 2's test_schemas.py/test_client.py/test_router.py additions proved the degradation contract already held from 03-01's client.py -- no production code change was needed there. The RED->GREEN split for that task is between the proving tests (RED-only commit, all 68 assertions passed immediately since the behavior pre-existed) and the genuinely new backend/scripts/llm_smoke_check.py (real RED->GREEN, file didn't exist)."
  - "chat-history-loading and chat-thinking testids/logic live in ChatMessageList.tsx (per the plan's own Task 3 action-text paragraph for that file); chat-quick-prompts and QUICK_PROMPTS live in ChatDrawer.tsx. One acceptance-criteria bullet's prose grouped all three testids under a single sentence naming ChatDrawer.tsx, which read literally would put all three there -- interpreted as feature-level (verified by the passing ChatDrawer.test.tsx suite mounting the whole tree) rather than single-file, since the plan's own detailed action text assigns them to two different files and duplicating the logic to satisfy a literal single-file grep would fight the plan's own design."
  - "key_links frontmatter names an 'isError' pattern for the ChatMessageBubble<->router.py link; the plan's own Task 3 action text says 'Add an errored marker' verbatim. Implemented as message.errored (matching the action text, the authoritative source) -- the key_links pattern string is a planner-authored hint, not matched literally in code."
requirements-completed: [CHAT-04, CHAT-05, TEST-02, TEST-03, TEST-04, UI-08]
coverage:
  - id: D1
    description: "GET /api/chat/history serves the persisted transcript: 200+[] empty, 200+4-entries oldest-first with role/content/actions after two turns, limit=1 returns the single most recent message, limit outside [1,200] returns 422"
    requirement: CHAT-04
    verification:
      - kind: integration
        ref: "backend/tests/llm/test_router.py::TestGetChatHistory (4 tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The 20-row model-context window is proven at the 19/20/21-row boundary, always most-recent, oldest-first; load_recent_chat_messages() output keys are exactly {role, content}, never actions"
    requirement: CHAT-04
    verification:
      - kind: unit
        ref: "backend/tests/llm/test_persistence.py::TestLoadRecentChatMessagesWindow (4 tests)"
        status: pass
    human_judgment: false
  - id: D3
    description: "A turn whose LLM call returns None leaves exactly one user row in chat_messages and zero trades rows; the user row's created_at is at or before the assistant row's on a successful turn"
    requirement: CHAT-05
    verification:
      - kind: unit
        ref: "backend/tests/llm/test_persistence.py::TestNoneLlmResultLeavesOnlyUserRow, ::TestSaveChatMessageOrdering"
        status: pass
    human_judgment: false
  - id: D4
    description: "ChatResponse.model_validate_json raises on free-form prose, truncated JSON, missing message, and wrong-typed quantity; defaults both action lists to [] when omitted; TradeAction rejects a digit/space in the ticker and a zero/negative quantity"
    requirement: TEST-02
    verification:
      - kind: unit
        ref: "backend/tests/llm/test_schemas.py (9 tests)"
        status: pass
    human_judgment: false
  - id: D5
    description: "get_chat_response() returns None on APITimeoutError and on each malformed payload class, logging at WARNING and never at ERROR or above on either branch"
    requirement: TEST-02
    verification:
      - kind: unit
        ref: "backend/tests/llm/test_client.py (6 tests)"
        status: pass
    human_judgment: false
  - id: D6
    description: "POST /api/chat on a timeout and on a malformed response both return 200 with the identical, imported GENERIC_RETRY_MESSAGE and actions={trades:[],watchlist_changes:[]}; resending after a timeout produces two user rows and zero assistant rows"
    requirement: TEST-03
    verification:
      - kind: integration
        ref: "backend/tests/llm/test_router.py::TestChatDegradation (3 tests)"
        status: pass
    human_judgment: false
  - id: D7
    description: "backend/scripts/llm_smoke_check.py sends real prompts through get_chat_response with mock mode off and reports whether structured-output parsing survived the wire to Cerebras -- the only check that can detect the OpenRouter adapter dropping response_format"
    requirement: TEST-02
    verification: []
    human_judgment: true
    rationale: "The plan's own Task 2 <human-check> requires OPENROUTER_API_KEY and a live network call, which a worktree executor does not run. Per project config human_verify_mode=end-of-phase, deferred to end-of-phase human verification, matching 03-01 D7's precedent. OPENROUTER_API_KEY is already present in the project-root .env."
  - id: D8
    description: "The drawer fetches /api/chat/history exactly once, only after first open (not on mount, not again on close/reopen); while pending shows only the Loading conversation... line; once resolved empty, shows the framing line and exactly three quick-prompt buttons whose click sends that exact text immediately without touching the input box; once resolved non-empty, restores prior turns including trade cards from persisted actions, and the quick-prompt block never reappears"
    requirement: UI-08
    verification:
      - kind: automated_ui
        ref: "frontend/components/ChatDrawer.test.tsx (9 tests) -- npm test"
        status: pass
    human_judgment: false
  - id: D9
    description: "While a send is in flight, the Send button is disabled and relabelled Sending... and a Thinking... indicator sits at the bottom of the message list"
    requirement: TEST-04
    verification:
      - kind: automated_ui
        ref: "frontend/components/ChatDrawer.test.tsx::'disables Send and shows the thinking indicator while a send is in flight'"
        status: pass
    human_judgment: false
  - id: D10
    description: "A rejected fetch and a backend 200-degraded reply both render the identical assistant-side bubble: border-down, the generic string verbatim, and the typed input value left untouched for a one-click resend"
    requirement: UI-08
    verification:
      - kind: automated_ui
        ref: "frontend/components/ChatDrawer.test.tsx (2 tests: rejected fetch, 200-degraded reply)"
        status: pass
    human_judgment: false
  - id: D11
    description: "Live-browser six-step walkthrough: no history request before toggle click, framing line + 3 quick prompts on a fresh database, immediate send with Thinking/Sending state, reload-and-reopen restores prior turns and trade cards, a forced failure shows the red-bordered bubble with the typed text preserved, and a long pasted message scrolls/wraps within a bounded input height"
    requirement: UI-08
    verification: []
    human_judgment: true
    rationale: "The plan's own Task 3 <human-check> requires a live browser walkthrough that a parallel worktree executor cannot perform. Per project config human_verify_mode=end-of-phase, deferred to end-of-phase human verification, matching 03-01 D7 and 03-02 D10's precedent."
duration: ~40min
completed: 2026-08-25
status: complete
---

# Phase 3 Plan 4: Chat Resilience & Starter Experience Summary

**GET /api/chat/history restores a reloaded conversation with its trade cards; timeout and four classes of malformed structured output now collapse to one proven, shared generic-retry body that executes nothing and persists no assistant row; and the drawer greets an empty conversation with three one-click quick prompts instead of a blank box.**

## Performance

- **Duration:** ~40min
- **Started:** 2026-08-25
- **Completed:** 2026-08-25
- **Tasks:** 3/3
- **Files modified:** 14 (backend: 8, frontend: 5, planning: 1)

## Accomplishments
- `GET /api/chat/history` serves the persisted transcript (200+`[]` on an empty database, bounded `limit` query param via `Query(default=50, ge=1, le=200)`), backed by a new `load_chat_history()` that stays structurally separate from the model-context reader `load_recent_chat_messages()` -- proven correct at the 19/20/21-row context-window boundary.
- Proved -- with row-level database assertions and parametrized malformed-payload fixtures, not just inspection -- that a timeout and four distinct classes of malformed LLM output (prose, truncated JSON, missing field, wrong-typed field) all degrade to the identical `GENERIC_RETRY_MESSAGE` body, execute zero trades, and persist zero assistant rows; the pre-call user row survives every failure mode untouched.
- Added `backend/scripts/llm_smoke_check.py`, the one manual live check that can detect the OpenRouter adapter silently dropping `response_format` before it reaches Cerebras -- something `LLM_MOCK=true` can never exercise by construction.
- The chat drawer now fetches its transcript once per page session (only after first open, never eagerly), shows an honest `Loading conversation…` line while that resolves, offers three fixed one-click quick prompts on a genuinely empty conversation, shows a `Thinking…` indicator with a disabled/relabelled Send button while a turn is in flight, and renders one shared red-bordered error bubble for both a backend 200-degraded reply and a real network/transport failure -- always leaving the typed message in the input box for a one-click resend.

## Task Commits

1. **Task 1: Serve the persisted transcript and prove the two-transaction write ordering** -- `37b3fd8` (test, RED), `3afad83` (feat, GREEN)
2. **Task 2: Prove safe degradation on timeout and malformed structured output** -- `249d6ed` (test, proving 03-01's existing degradation contract -- all 68 assertions passed against unchanged production code), `3d71cb7` (feat, GREEN -- the genuinely new `llm_smoke_check.py`)
3. **Task 3: Drawer starter experience, loading states, and the inline error bubble** -- `1686bf2` (test, RED), `27379ef` (feat, GREEN)

No REFACTOR commits were needed -- each GREEN commit's code was already clean.

**Plan metadata:** committed separately after this summary (see git log).

## Files Created/Modified
- `backend/app/llm/persistence.py` -- `load_chat_history(conn, limit=50, user_id=DEFAULT_USER_ID)`, the transcript reader for the UI
- `backend/app/llm/router.py` -- `GET /api/chat/history` with `Query(default=50, ge=1, le=200)`
- `backend/app/llm/__init__.py` -- re-exports `load_chat_history`
- `backend/tests/llm/test_persistence.py` -- 19/20/21-row window boundary, `load_chat_history` unit tests, None-result row assertions, save-order assertion
- `backend/tests/llm/test_router.py` -- `TestGetChatHistory` (status/shape matrix) and `TestChatDegradation` (HTTP-level timeout/malformed/resend), plus a `live_chat_client` fixture (mock=False) for patching `litellm.completion` directly
- `backend/tests/llm/test_schemas.py` -- parametrized malformed-payload suite, default-empty-list case, `TradeAction` field validators
- `backend/tests/llm/test_client.py` -- `get_chat_response` timeout/malformed degradation with `caplog` level assertions
- `backend/scripts/llm_smoke_check.py` -- new standalone developer script, new `backend/scripts/` directory
- `frontend/hooks/useChat.ts` -- `loadHistory()`, `historyLoaded`, exported `GENERIC_RETRY_MESSAGE`, `errored` message marker
- `frontend/components/ChatDrawer.tsx` -- `QUICK_PROMPTS` (3 fixed prompts), framing line, first-open history fetch, bounded-height `<textarea>` input
- `frontend/components/ChatMessageList.tsx` -- `chat-history-loading` line, `chat-thinking` indicator; fixed a jsdom `scrollIntoView` crash surfaced by the first test to mount this tree
- `frontend/components/ChatMessageBubble.tsx` -- `border-down` error variant driven by `message.errored`
- `frontend/components/ChatDrawer.test.tsx` -- 9 tests covering the full Task 3 behavior list
- `.planning/REQUIREMENTS.md` -- CHAT-05 and TEST-02 marked Complete (verified unique to this plan)

## Decisions Made
- Task 2's tests prove an already-correct contract from 03-01's `client.py` rather than driving new production code -- documented above under key-decisions, with the RED/GREEN split landing between the proving-tests commit and the genuinely new smoke-script commit.
- `message.errored` (not `isError`) is the field name, matching the plan's own Task 3 action text verbatim; the `key_links` frontmatter's `isError` pattern string is treated as a planner hint, not a literal code requirement.
- `chat-history-loading`/`chat-thinking` live in `ChatMessageList.tsx`, `chat-quick-prompts`/`QUICK_PROMPTS` live in `ChatDrawer.tsx` -- following the plan's own per-file action-text assignment over one acceptance-criteria bullet's looser prose grouping (see key-decisions).
- CHAT-05 and TEST-02 marked Complete by hand in `REQUIREMENTS.md`; CHAT-04, TEST-03, TEST-04, UI-08 left Pending for the orchestrator to reconcile. Verified by grepping every `03-*-PLAN.md`'s `requirements:` frontmatter: CHAT-05 and TEST-02 appear only in this plan; CHAT-04 is shared with 03-01, TEST-03/TEST-04 are shared with 03-03, UI-08 is shared with 03-01/03-02 -- the `gsd-tools` CLI reported a missing build artifact (`GSD runtime library is not built`) in this fresh worktree checkout, so shared IDs were left per protocol rather than hand-flipped.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `ChatMessageList.tsx`'s auto-scroll crashed on a jsdom `TypeError: scrollIntoView is not a function`**
- **Found during:** Task 3, first `npm test` run against the new `ChatDrawer.test.tsx`
- **Issue:** jsdom does not implement `Element.scrollIntoView`. `bottomRef.current?.scrollIntoView({ block: "end" })` only optional-chains the ref itself, not the method -- since `scrollIntoView` is `undefined` on a jsdom node, calling it as a function throws. This was latent since no prior test in the suite mounted `ChatMessageList` (03-01/03-02's component tests exercised `ChatMessageBubble`/`TradeConfirmationCard` in isolation); `ChatDrawer.test.tsx` is the first to mount the full tree.
- **Fix:** Changed to `bottomRef.current?.scrollIntoView?.({ block: "end" })`, optional-chaining the method reference too. No behavior change in a real browser (which always has the method).
- **Files modified:** `frontend/components/ChatMessageList.tsx`
- **Verification:** All 9 `ChatDrawer.test.tsx` assertions pass; full `npm test` (31/31) and `npm run build` green.
- **Committed in:** `27379ef` (Task 3 GREEN commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 -- bug). **Impact on plan:** None on scope or architecture; a pre-existing latent bug caught and fixed before the GREEN commit, with the full test suite as evidence.

## Issues Encountered
`npm install --prefix frontend` had never been run in this fresh worktree checkout (`sh: 1: vitest: not found` on first `npm test`) -- same environment gap 03-02 documented for its own worktree. Ran `npm install`; no `package.json`/`package-lock.json` changes resulted since dependencies were already correctly declared.

`gsd-tools.cjs` reported `GSD runtime library is not built and cannot be auto-built` when attempting `requirements.ready-ids` in this fresh worktree -- handled per the plan's own fallback instructions (see Decisions Made above), matching 03-02's precedent.

## Known Stubs
None -- every deliverable this plan scoped (transcript route, degradation proof, smoke script, drawer starter experience) is fully wired, not stubbed. The two deferred human-checks (D7, D11) are explicit `human_judgment: true` coverage entries, not undocumented gaps.

## User Setup Required
None -- `OPENROUTER_API_KEY` is already present and non-empty in the project-root `.env`; no `03-USER-SETUP.md` was generated.

## Next Phase Readiness
This is the last plan in Phase 3 (AI Copilot). All three of its tasks are complete, all automated verification is green (`LLM_MOCK=true uv run --directory backend --extra dev pytest -q`: 242/242; `npm test --prefix frontend`: 31/31; `ruff check app/ tests/ scripts/`: clean; `npm --prefix frontend run build`: succeeds). Two human-check items remain deferred per `human_verify_mode: end-of-phase` (the live smoke script confirming `response_format` survives the wire, and the six-step drawer browser walkthrough) -- both are `OPENROUTER_API_KEY`-gated and already satisfied by an existing key in `.env`, so nothing blocks running them. Phase 3 is ready for end-of-phase verification once this plan is merged.

## Self-Check: PASSED
All 5 created files verified present (`git ls-files`); all 6 task commits
(`37b3fd8`, `3afad83`, `249d6ed`, `3d71cb7`, `1686bf2`, `27379ef`) verified
present in `git log --oneline`.

---
*Phase: 03-ai-copilot*
*Completed: 2026-08-25*
