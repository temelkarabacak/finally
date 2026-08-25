---
phase: 03-ai-copilot
reviewed: 2026-08-25T16:08:15Z
depth: standard
files_reviewed: 36
files_reviewed_list:
  - backend/app/llm/__init__.py
  - backend/app/llm/client.py
  - backend/app/llm/executor.py
  - backend/app/llm/mock.py
  - backend/app/llm/persistence.py
  - backend/app/llm/prompt.py
  - backend/app/llm/router.py
  - backend/app/llm/schemas.py
  - backend/app/main.py
  - backend/pyproject.toml
  - backend/scripts/llm_smoke_check.py
  - backend/tests/llm/__init__.py
  - backend/tests/llm/conftest.py
  - backend/tests/llm/fixtures/__init__.py
  - backend/tests/llm/fixtures/chat_scenarios.py
  - backend/tests/llm/test_client.py
  - backend/tests/llm/test_executor.py
  - backend/tests/llm/test_mock.py
  - backend/tests/llm/test_persistence.py
  - backend/tests/llm/test_router.py
  - backend/tests/llm/test_schemas.py
  - backend/tests/portfolio/test_router.py
  - backend/tests/watchlist/test_router.py
  - frontend/app/page.tsx
  - frontend/components/ChatDrawer.test.tsx
  - frontend/components/ChatDrawer.tsx
  - frontend/components/ChatMessageBubble.tsx
  - frontend/components/ChatMessageList.tsx
  - frontend/components/TradeConfirmationCard.test.tsx
  - frontend/components/TradeConfirmationCard.tsx
  - frontend/components/WatchlistPanel.test.tsx
  - frontend/components/WatchlistPanel.tsx
  - frontend/hooks/useChat.ts
  - frontend/hooks/usePortfolio.test.ts
  - frontend/lib/format.test.ts
  - frontend/package.json
  - frontend/vitest.config.mts
  - frontend/vitest.setup.ts
findings:
  critical: 2
  warning: 4
  info: 2
  total: 8
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-08-25T16:08:15Z
**Depth:** standard
**Files Reviewed:** 36
**Status:** issues_found

## Summary

Reviewed the backend LLM/chat subsystem (`backend/app/llm/*`), its tests, wiring in
`backend/app/main.py`, and the frontend chat drawer / watchlist components that
consume it. The trade/watchlist auto-execution path (`executor.py`) correctly
routes through the same validated `execute_trade`/`add_watchlist_ticker`/
`remove_watchlist_ticker` functions the manual endpoints use, and the
execution-derived-actions design (never echoing the model's own proposed
action list back to the client) is implemented as documented. SQL is fully
parameterized; no injection, secrets, or dangerous-function issues were found.

Two blocking defects were found and proven with a runnable repro, not just
read-through inspection:

1. `handle_chat_message` persists the user's message *before* loading
   conversation history, so every real (non-mock) LLM call sends the user's
   current turn duplicated in the message list — once via the just-persisted
   history row, once via the explicit final `user` turn `build_messages`
   appends. Verified empirically (see CR-01).
2. The frontend `WatchlistPanel` never re-fetches its ticker list after a
   chat-executed watchlist add/remove; `ChatDrawer`'s `onActionsExecuted`
   callback is wired only to `usePortfolio`'s `refresh`, which never touches
   `/api/watchlist`. This breaks PLAN.md §2's explicit requirement that the
   watchlist can be "managed... via the AI chat" — the change happens on the
   backend but is invisible in the watchlist grid until a full page reload.

Several warnings describe uneven/missing error handling in the chat pipeline
(only `APITimeoutError` is special-cased; other litellm/openai exception
types crash the request) and a dead exception branch. Frontend
component/hook tests are solid and the mock-mode reference dataset is well
covered; the two blockers above sit outside what those tests exercise.

## Critical Issues

### CR-01: Every real LLM chat turn duplicates the user's current message in the prompt

**File:** `backend/app/llm/router.py:44-51`
**Issue:**
`handle_chat_message` persists the user's message with `save_chat_message()`
*before* calling `load_recent_chat_messages()`. Since `save_chat_message`
commits synchronously (autocommit connection, explicit `BEGIN`/`COMMIT`, no
`await` in between), the row is already in `chat_messages` by the time
`load_recent_chat_messages(conn, limit=20)` runs a few lines later — so the
"history" it returns includes the current turn's own user message as its
last row. `build_messages()` then appends the identical `user_text` again as
the final message. The result: the model receives the user's current message
twice in a row, and the 20-row window effectively shrinks to 19 *prior*
turns because one slot is consumed by the just-inserted current row.

This also inverts the ordering PLAN.md §9 specifies (load history, *then*
persist the user message, *then* call the model) — the implementation
persists first, which is what causes the leak.

Verified with a direct call to `handle_chat_message` (mock mode, so only
`user_text` mattered for the response but the same `build_messages` code
path ran):
```
First turn history: [{'role': 'user', 'content': 'Hello there first turn'}]
Second turn history: [{'role': 'user', 'content': 'Hello there first turn'},
                       {'role': 'assistant', 'content': "I'm ready to help — ..."},
                       {'role': 'user', 'content': 'Second turn message'}]
Second turn user_text: Second turn message
```
Note `'Second turn message'` appears as the last history row *and* is then
appended a second time as the final user turn by `build_messages`.

**Fix:** Load history before persisting the current turn (matches PLAN.md's
documented order), or exclude the just-inserted row from the window by
filtering it out / persisting after the read:
```python
# 1. Read fresh context and PRIOR history first (no open transaction).
portfolio_ctx = build_portfolio_context(conn, price_cache)
history = load_recent_chat_messages(conn, limit=20)

# 2. THEN persist the user's message (still before the LLM call, per CHAT-04).
save_chat_message(conn, role="user", content=user_text)

messages = build_messages(SYSTEM_PROMPT, portfolio_ctx, history, user_text)
```
Add a regression test asserting the message list passed to `get_chat_response`
never contains the current `user_text` twice.

---

### CR-02: Chat-executed watchlist changes never appear in the watchlist panel without a page reload

**File:** `frontend/app/page.tsx:125`, `frontend/hooks/useChat.ts:69-154`, `frontend/components/WatchlistPanel.tsx:52-61`
**Issue:**
PLAN.md §2/§10 requires the user to be able to "add/remove tickers manually
or via the AI chat." The backend executes chat-proposed watchlist changes
correctly (`executor.py::apply_watchlist_change`), but the frontend never
reflects it:

- `WatchlistPanel` owns its own `tickers` state, fetched once via `refetch()`
  in a mount-only `useEffect` (`WatchlistPanel.tsx:59-61`), and otherwise
  only re-fetched from its own internal `handleAdd`/`handleRemove` handlers.
- `ChatDrawer`'s `onActionsExecuted` prop is wired in `page.tsx` to
  `usePortfolio`'s `refresh`, which only calls `GET /api/portfolio` and
  `GET /api/portfolio/history` (`usePortfolio.ts:127-158`) — it never touches
  `/api/watchlist`.

So when the LLM (or `LLM_MOCK`) executes `{"action": "add", "ticker": "PYPL"}`,
the backend inserts the row and starts streaming its price, but
`WatchlistPanel`'s `tickers` array is never updated — the new ticker simply
never renders in the grid until the user manually reloads the page. The
inverse also holds for a chat-executed remove: the stale row stays visible
and clicking its own remove button will 404 before self-correcting.

This is untested — none of `WatchlistPanel.test.tsx` or `ChatDrawer.test.tsx`
exercise a chat-executed watchlist change's effect on the watchlist grid.

**Fix:** Give `WatchlistPanel` a way to react to chat-driven changes — either
lift its `tickers`/`refetch` state up (or into a shared hook like
`usePortfolio`) and pass a `refreshWatchlist` callback into `ChatDrawer`'s
`onActionsExecuted` alongside the portfolio refresh, e.g.:
```tsx
// page.tsx
const refreshAll = useCallback(async () => {
  await Promise.all([refresh(), refreshWatchlist()]);
}, [refresh, refreshWatchlist]);

<ChatDrawer onActionsExecuted={refreshAll} />
```
with `refreshWatchlist` exposed from `WatchlistPanel` (or a new
`useWatchlist` hook) the same way `usePortfolio` exposes `refresh`.

## Warnings

### WR-01: Only `APITimeoutError` is handled — other LLM/provider errors crash the chat endpoint with an unhandled 500

**File:** `backend/app/llm/client.py:52-62`
**Issue:** `get_chat_response()` catches `APITimeoutError` and
(`ValidationError`, `json.JSONDecodeError`) for malformed structured output,
but `litellm.completion()` via OpenRouter/Cerebras can raise other
`openai.APIError` subclasses — `RateLimitError`, `APIConnectionError`,
`AuthenticationError`, `InternalServerError`, `BadRequestError`, etc. None of
these are caught here, in `handle_chat_message`, or anywhere in
`create_chat_router`/`main.py` (no app-level exception handler is
registered). Any such error propagates as an unhandled exception out of
`POST /api/chat`, producing a generic FastAPI 500 instead of the documented
graceful `GENERIC_RETRY_MESSAGE` behavior the rest of the pipeline
guarantees for timeouts and malformed output. It also means the user's
already-persisted message (step 1) is stranded with a hard failure rather
than the "generic retry" UX the frontend is built to show.
**Fix:** Broaden the catch to the common `openai.APIError` base (or
`litellm.exceptions.APIError`) alongside `APITimeoutError`, logging and
returning `None` the same way the other degraded paths do:
```python
from openai import APIError

...
except APIError as e:
    logger.warning("LLM call failed: %s", e)
    return None
```

### WR-02: `apply_watchlist_change`'s side-effecting calls are not exception-guarded, unlike `_execute_one_trade`

**File:** `backend/app/llm/executor.py:29-63, 66-101, 103-125`
**Issue:** `_execute_one_trade` wraps its post-commit `market_source.add_ticker()`
call in `try/except Exception: logger.exception(...)` so a source failure
never crashes an already-executed trade. `apply_watchlist_change` has no such
guard around its own `market_source.add_ticker()`/`remove_ticker()` calls (or
the `add_watchlist_ticker`/`remove_watchlist_ticker` DB writes). Since
`execute_actions` runs trades first and watchlist changes second in the same
turn, an exception raised while processing a watchlist change means:
(a) any trades from the same turn that already committed are never persisted
to `chat_messages.actions` (the `save_chat_message` assistant-row write never
runs), so the user has no record the trade executed even though cash/position
data has already changed, and (b) the request 500s instead of degrading
gracefully. The concrete data sources' `add_ticker`/`remove_ticker`
implementations are currently pure in-memory list mutations (low likelihood
of throwing today), but the inconsistency with the trade path is a real gap
that would silently worsen if either implementation changes.
**Fix:** Apply the same `try/except Exception: logger.exception(...)` pattern
used in `_execute_one_trade` around the `market_source` calls in
`apply_watchlist_change`, and/or wrap `execute_actions`'s per-item calls so
one failing action never prevents the results of prior successfully-executed
actions in the same turn from being returned/persisted.

### WR-03: `mock.py`'s trade regex misparses common phrasing as a bogus ticker

**File:** `backend/app/llm/mock.py:22, 44-47`
**Issue:** `_TRADE_RE = r"\b(buy|sell)\b\s+(\d+(?:\.\d+)?)\s+(?:shares?\s+of\s+)?([a-z]+)\b"`
treats any bare word immediately following a quantity as the ticker when the
optional `shares of` phrase isn't present. E.g. `"sell 5 shares later"` (no
"of") matches with `ticker="shares"` — normalized/validated by
`TradeAction`'s pattern (`^[A-Z.\-]+$`, letters only) as ticker `SHARES`,
producing a spurious auto-"trade" attempt against a nonsense ticker in
`LLM_MOCK` mode. None of the 12 reference scenarios in
`chat_scenarios.py` exercise this phrasing, so it's untested.
**Fix:** Require the `shares?` word (with or without a trailing `of`) to be
consumed rather than left to fall through to the ticker group, e.g.:
```python
_TRADE_RE = re.compile(
    r"\b(buy|sell)\b\s+(\d+(?:\.\d+)?)\s+(?:shares?\s+of\s+)?"
    r"(?!shares?\b)([a-z]+)\b"
)
```
or require a ticker to be 1-5 letters and explicitly exclude common English
filler words used in trade phrasing.

### WR-04: Dead exception branch in `client.py` — `model_validate_json` never raises `json.JSONDecodeError`

**File:** `backend/app/llm/client.py:19, 58-61`
**Issue:** The `except (ValidationError, json.JSONDecodeError)` clause
assumes pydantic v2's `ChatResponse.model_validate_json()` can raise a raw
`json.JSONDecodeError` for invalid JSON syntax. Verified empirically: it
always raises `pydantic_core.ValidationError` (which subclasses `ValueError`,
not `json.JSONDecodeError`), even for completely invalid JSON:
```
>>> ChatResponse.model_validate_json('not json at all')
pydantic_core._pydantic_core.ValidationError: ...
```
The `json.JSONDecodeError` half of the except tuple is therefore unreachable
dead code, and the accompanying `import json` exists only to support it.
**Fix:** Drop `json.JSONDecodeError` from the except clause and the now-unused
`import json`, or if defensive coverage against a future pydantic/json
behavior change is desired, add a comment explaining that explicitly rather
than implying it's a currently-reachable path.

## Info

### IN-01: `errored` detection relies on exact string equality with `GENERIC_RETRY_MESSAGE`

**File:** `frontend/hooks/useChat.ts:49, 123`
**Issue:** `const errored = body.message === GENERIC_RETRY_MESSAGE;` treats
any 200 response whose `message` field happens to equal
`"Something went wrong — please try again."` verbatim as a degraded turn,
even if it were a genuine (if oddly-worded) LLM/mock reply. This is
documented as intentional in the surrounding comment and is low-risk given
the string is distinctive, but it is a string-equality coupling between
frontend and backend that could silently misclassify a legitimate reply if
either side's copy drifts without the other being updated in lockstep.
**Fix:** Consider a dedicated boolean/flag in the response body (e.g.
`{"message": ..., "errored": true, "actions": ...}`) instead of inferring it
from message-text equality, if this proves fragile in practice.

### IN-02: Array index used as React `key` for the chat message list

**File:** `frontend/components/ChatMessageList.tsx:45`
**Issue:** `messages.map((message, index) => <ChatMessageBubble key={index} ...>)`
uses the array index as the list key. The list is currently append-only so
this is low-risk today, but it's a recognized anti-pattern that can cause
incorrect reconciliation (stale `TradeConfirmationCard` state, wrong
`onAnimationEnd` targets, etc.) if the list is ever filtered, reordered, or
prepended to (e.g. a future "load older messages" feature).
**Fix:** Use a stable identifier per message (e.g. an id returned by the
backend, or a client-generated uuid at append time) instead of the array
index.

---

_Reviewed: 2026-08-25T16:08:15Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
