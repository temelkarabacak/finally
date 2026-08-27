# Phase 3: AI Copilot - Research

**Researched:** 2026-08-25
**Domain:** FastAPI router integration, SQLite transactional persistence, Next.js/React chat UI, offline test infrastructure
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Chat panel placement & collapse**
- D-01: The AI chat panel is a bottom drawer, not a left/right sidebar — slides up from the bottom edge of the screen.
- D-02: The drawer overlays (floats) on top of the existing grid rather than pushing/reflowing the watchlist/chart/portfolio layout — simpler to implement, accepted tradeoff that it can obscure content underneath while open.
- D-03: Collapsed by default on first page load — the user sees the full trading grid first and opens chat via a toggle.

**Inline action confirmations**
- D-04: A successful AI-executed trade renders as a summary card inline in the chat (ticker, side, quantity, fill price) — visually distinct from conversational text, not just a sentence.
- D-05: A rejected trade (failed validation) reuses the same summary card component but styled as failed (red border / "REJECTED" label). Reversible — a card-styling variant.
- D-06: AI-executed watchlist changes get simpler treatment than trades — plain text in the assistant's reply, no card.

**Chat starter experience**
- D-07: On first opening the (empty) chat, the user sees suggested quick-prompt buttons above the input.
- D-08: Clicking a quick-prompt sends it immediately rather than filling the input box.

**Timeout / retry UX**
- D-09: The 30-second timeout's generic retry message renders as an error bubble inline in the chat thread (assistant-message-style), not a toast/banner.
- D-10: The user's original message stays in the input box after a timeout so they can resend with one click.

**Mock mode demo behavior**
- D-11: With `LLM_MOCK=true`, mock responses are pattern-recognizing (keyword/rule-based matcher) rather than one fixed canned response. Costly to change later — TEST-02/03/04 and Phase 4's E2E scenario are written against this rule set.

### Claude's Discretion
- Message bubble styling (alignment, color-coding using locked theme tokens).
- System prompt wording/tone (PLAN.md §9 gives the substance).
- Exact mock-mode pattern rules (D-11 locks the approach, not the rule table).
- `uv add litellm pydantic` — mechanical, not a design decision.
- Chat message persistence/DB write ordering — follow the same "no await inside the transaction" discipline as Phase 2.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CHAT-01 | `POST /api/chat` returns one complete JSON response, no streaming | `create_chat_router` factory pattern (§ Architecture Patterns, Pattern 1); AI-SPEC §2-4 owns the LLM call itself |
| CHAT-02 | LLM trades auto-execute through the same validation as manual trades | Reuse `execute_trade()` from `app.portfolio.trades` directly — see Don't Hand-Roll |
| CHAT-03 | LLM watchlist changes auto-execute | New `apply_watchlist_change()` wrapping `add_watchlist_ticker`/`remove_watchlist_ticker` + `market_source.add_ticker`/`remove_ticker`, mirroring `watchlist/router.py` |
| CHAT-04 | Chat history persists; user message saved before LLM call, assistant after success | Explicit-transaction pattern (§ Architecture Patterns, Pattern 2), two-transaction split |
| CHAT-05 | 30s timeout aborts with generic retry message, no trade, not persisted | AI-SPEC §3-4 owns the timeout mechanics; this doc covers what NOT to write to `chat_messages` on that path |
| CHAT-06 | `LLM_MOCK=true` → deterministic mock responses | `os.environ.get("LLM_MOCK", "")` pattern mirrors `factory.py`'s `MASSIVE_API_KEY` check (§ Common Pitfalls) |
| UI-08 | Docked/collapsible chat panel, loading state, inline confirmations | § Architecture Patterns, Pattern 3 (frontend chat drawer structure) |
| TEST-02 | Backend tests: LLM structured-output parsing incl. malformed responses | AI-SPEC §5 (EV-2) owns the dimension; § Validation Architecture maps it to concrete pytest files |
| TEST-03 | Backend tests: route status codes/response shapes for portfolio/watchlist/chat | `backend/tests/portfolio/test_router.py` is the pattern to mirror for `backend/tests/llm/test_router.py` |
| TEST-04 | Frontend tests: price flash, watchlist CRUD, portfolio calc, chat rendering/loading | No test runner exists yet — § Environment Availability and § Architecture Patterns, Pattern 4 (vitest setup) |
</phase_requirements>

## Summary

This phase's LLM call mechanics (framework, prompt shape, structured-output schema, mock strategy, evaluation plan) are already fully locked in `03-AI-SPEC.md` §2–4b and must not be re-derived. What remains open — and what this document covers — is how the new `app/llm/` package plugs into the rest of the already-built FastAPI/SQLite/Next.js codebase: the router factory signature, the two-transaction persistence split around the (awaited) LLM call, reuse of `execute_trade()`/watchlist helpers instead of reimplementing validation, the frontend drawer/message-list/confirmation-card component tree built on the existing hook conventions, and — critically — standing up a frontend test runner that does not exist yet (TEST-04 has zero current infrastructure).

Three findings from this pass materially change the plan: (1) there is no `apply_watchlist_change()` helper anywhere in the codebase — AI-SPEC's Section 4 pattern names it but it must be written new, as a thin wrapper around `app.db.add_watchlist_ticker`/`remove_watchlist_ticker` plus `market_source.add_ticker`/`remove_ticker`, following the exact DB-write-then-await-source order already used in `watchlist/router.py`; (2) `backend/app/llm/__pycache__` and `backend/tests/llm/__pycache__` contain compiled bytecode (`client.py`, `executor.py`, `context.py`, `mock.py`, `router.py`, `schema.py`) from an entirely different, non-ancestor commit (`d4010c1`, on a branch this history was reset from) — the actual `.py` source files do not exist on this branch and the directories are otherwise empty; these are harmless (Python cannot import orphaned bytecode without matching source) but should be deleted as housekeeping before the new modules land, since the stale filenames look confusingly similar to the new plan; (3) `frontend/package.json` has zero test tooling installed (no `vitest`, `jest`, `@testing-library/*`) — TEST-04 requires a from-scratch test runner install, and the official Next.js 16 guide's manual-setup package list differs slightly from what AI-SPEC's eval planner suggested (see § Standard Stack).

**Primary recommendation:** Build `app/llm/router.py` as `create_chat_router(get_conn, market_source, price_cache, mock: bool)` mirroring `create_portfolio_router`/`create_watchlist_router` exactly; call the *existing* `execute_trade()` and new thin `apply_watchlist_change()` for every LLM-proposed action rather than writing new validation; split chat persistence into two explicit `BEGIN`/`COMMIT` blocks (user message before the `await` LLM call, assistant message + actions after) with zero awaits inside either transaction, exactly as Phase 2's `execute_trade()` already does; and install `vitest` + `@testing-library/react` + `jsdom` + `@vitejs/plugin-react` (+ `vite-tsconfig-paths` for the TS path aliases already used via `@/`) per the official Next.js 16 Vitest guide before writing any frontend test.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| LLM call (completion, structured output, mock) | API / Backend | — | Already implemented as `app/llm/client.py`+`mock.py` per AI-SPEC §3; a pure backend concern, no client-side LLM access ever |
| Portfolio/watchlist context assembly for the prompt | API / Backend | Database / Storage | Reads live prices from `PriceCache` (in-process) and DB via existing `portfolio_view()`/`get_watchlist_tickers()` — no new data layer |
| Trade/watchlist auto-execution | API / Backend | Database / Storage | Must call the *existing* `execute_trade()` (Database-tier writes happen there); LLM layer never duplicates validation |
| Chat message persistence | Database / Storage | API / Backend | `chat_messages` table already exists in schema; API layer owns transaction boundaries around it |
| Chat drawer, message list, confirmation cards, quick-prompts | Browser / Client | — | Pure React state (open/closed, message list, input) — no SSR needed, matches existing `"use client"` component pattern |
| 30s timeout / malformed-output safe-degrade | API / Backend | — | Structural guardrail lives entirely server-side (AI-SPEC §6); frontend only renders whatever the API returns |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `litellm` | `>=1.98.0` (latest `1.98.0`, released 2026-08-22) | LLM call + provider routing to Cerebras via OpenRouter | Locked by AI-SPEC §2/§3 and `.claude/skills/cerebras/SKILL.md`; not an open decision |
| `pydantic` | `>=2.13.0` (latest `2.13.4`, released 2026-05-06) | `response_format` structured-output contract, request/response models | Already the pattern used in `portfolio/router.py`/`watchlist/router.py` (`BaseModel` + `field_validator`); adding it for LLM schemas is consistent, not new |

### Supporting (Frontend test infra — new for this phase)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `vitest` | `4.1.11` (latest) | Test runner (Vite-native, fast, ESM-first) | TEST-04 — official Next.js 16 recommendation over Jest |
| `@testing-library/react` | `16.3.2` (latest) | Component rendering/querying in tests | Every component test (chat rendering, price flash, watchlist CRUD) |
| `@testing-library/dom` | `10.4.1` (latest) | Peer dep of `@testing-library/react`, DOM query primitives | Installed alongside, per official guide |
| `jsdom` | `30.0.1` (latest) | Browser-like DOM environment for vitest | `environment: 'jsdom'` in `vitest.config.mts` |
| `@vitejs/plugin-react` | `6.1.0` (latest) | JSX/Fast Refresh transform for Vite/vitest | Required in `vitest.config.mts` plugins array |
| `vite-tsconfig-paths` | `6.1.1` (latest) | Resolves the `@/` path alias already used throughout `frontend/` (`@/components/...`, `@/hooks/...`) | Without it, vitest cannot resolve the existing import style — see Pitfall 3 |
| `@testing-library/jest-dom` | `7.0.1` (latest) | `toBeInTheDocument()`-style matchers | Optional — the official Next.js guide's minimal example does not require it (uses `toBeDefined()`), but is near-universal in practice for readable assertions |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| vitest | Jest + `next/jest` | Also officially supported by Next.js, but the project's tooling is already 100% Vite-free-yet-modern (Next 16, Turbopack-era); vitest is the current Next.js-recommended default for new projects and shares config style with nothing else already in the repo, so it's a wash — vitest chosen for lighter config and faster watch mode, consistent with AI-SPEC's suggestion |
| `@testing-library/jest-dom` | Bare vitest `expect` + manual DOM assertions | jest-dom matchers are what most React Testing Library examples (including Next's own) assume; skipping it means writing more verbose assertions for no real benefit |

**Installation:**
```bash
# Backend (mechanical, per CONTEXT.md Claude's Discretion)
cd backend
uv add litellm pydantic

# Frontend test infra (TEST-04 — nothing currently installed)
npm install --prefix frontend -D vitest @testing-library/react @testing-library/dom \
  @testing-library/jest-dom jsdom @vitejs/plugin-react vite-tsconfig-paths
```

**Version verification:** `litellm` and `pydantic` versions confirmed live against the PyPI JSON API (`pypi.org/pypi/<pkg>/json`) on 2026-08-25 — `litellm` latest is exactly `1.98.0` (matches the AI-SPEC floor), `pydantic` latest is `2.13.4`. Frontend package versions confirmed via `npm view <pkg> version` on 2026-08-25.

## Package Legitimacy Audit

| Package | Registry | Published (latest) | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|---------------------|-----------|-------------|---------|-------------|
| `litellm` | PyPI | 2026-08-22 | unknown (PyPI download stats unavailable to checker) | litellm.ai (project site; GitHub: BerriAI/litellm) | SUS (`too-new`, `unknown-downloads`) | Approved — see note below |
| `pydantic` | PyPI | 2026-05-06 | unknown (PyPI download stats unavailable to checker) | github.com/pydantic/pydantic | SUS (`unknown-downloads`) | Approved — see note below |
| `vitest` | npm | 2026-08-18 | 93.3M/week | github.com/vitest-dev/vitest | SUS (`too-new`) | Approved — see note below |
| `@testing-library/react` | npm | 2026-01-19 | 54.7M/week | github.com/testing-library/react-testing-library | OK | Approved |
| `@testing-library/jest-dom` | npm | 2026-08-09 | 61.2M/week | github.com/testing-library/jest-dom | SUS (`too-new`) | Approved — see note below |
| `jsdom` | npm | 2026-07-29 | 94.6M/week | github.com/jsdom/jsdom | SUS (`too-new`) | Approved — see note below |
| `@vitejs/plugin-react` | npm | 2026-08-20 | 83.5M/week | github.com/vitejs/vite-plugin-react | SUS (`too-new`) | Approved — see note below |
| `vite-tsconfig-paths` | npm | 2026-02-11 | 32.4M/week | github.com/aleclarson/vite-tsconfig-paths | OK | Approved |
| `@testing-library/dom` | npm | 2025-07-27 | 66.9M/week | github.com/testing-library/dom-testing-library | OK | Approved |

**Packages removed due to [SLOP] verdict:** none.

**Packages flagged as suspicious [SUS]:** `litellm`, `pydantic`, `vitest`, `@testing-library/jest-dom`, `jsdom`, `@vitejs/plugin-react`. **Note on these six flags:** the automated checker's `too-new`/`unknown-downloads` signals are measuring *most recent publish date*, not package age — every flagged package is an extremely well-established, canonical, high-download-count project (all six have official GitHub org repos matching their npm/PyPI scope, and the five npm packages each show 30M–95M weekly downloads). The `too-new` signal is firing because these are actively-maintained projects with a release in the last ~2 weeks, which is normal cadence, not a legitimacy signal. `litellm`/`pydantic` show `unknown-downloads` only because the checker has no PyPI download-count source, not because downloads are actually low — both are locked, named dependencies in `03-AI-SPEC.md` and `.claude/skills/cerebras/SKILL.md` (pydantic is also already a transitive dependency of the installed `fastapi>=0.138.0`). **Planner should still insert a lightweight `checkpoint:human-verify` before the `npm install`/`uv add` steps** per protocol, but this audit's own evidence (repo ownership, download volume) supports proceeding without a blocking pause.

## Architecture Patterns

### System Architecture Diagram

```
Browser (chat drawer)                    FastAPI process                         SQLite (chat_messages,
  │                                         │                                      positions, watchlist,
  │ 1. POST /api/chat {message}             │                                      users_profile)
  ├─────────────────────────────────────►   │
  │                                         │ 2. save_chat_message(role="user")    │
  │                                         ├──────────────BEGIN/COMMIT───────────►│
  │                                         │                                      │
  │                                         │ 3. build_portfolio_context()         │
  │                                         │    ←── reads PriceCache (in-proc) ────┤ (positions/watchlist
  │                                         │    ←── reads DB (positions/watchlist) │  read-only, no txn)
  │                                         │                                      │
  │                                         │ 4. load_recent_chat_messages(20)      │
  │                                         │    ←──────────── SELECT ─────────────►│
  │                                         │                                      │
  │                                         │ 5. await get_chat_response(messages) │
  │                                         │    (asyncio.to_thread → LiteLLM →     │
  │                                         │     OpenRouter → Cerebras)            │
  │                                         │    [OUTSIDE any open transaction]     │
  │                                         │        │                              │
  │                                    ┌────┴─ None? (timeout/malformed) ─────┐    │
  │                                    │ yes → generic retry msg,             │    │
  │  ◄─────────── 200 + retry text ────┤       nothing further persisted     │    │
  │                                    └────┬──────────────────────────────── ┘    │
  │                                         │ no                                   │
  │                                         │ 6. execute_trade() / apply_watchlist_ │
  │                                         │    change() for each proposed action │
  │                                         ├──────────BEGIN/COMMIT (per action,───►│
  │                                         │           existing trade txn)         │
  │                                         │                                      │
  │                                         │ 7. save_chat_message(role="assistant",│
  │                                         │    actions=<executor return values>) │
  │                                         ├──────────────BEGIN/COMMIT───────────►│
  │  ◄──── 200 {message, actions} ──────────┤                                      │
  │                                         │                                      │
  │ 8. render message bubble +               │                                      │
  │    trade/watchlist confirmation cards    │                                      │
```

### Recommended Project Structure
```
backend/app/llm/
├── __init__.py       # exports create_chat_router, ChatResponse, get_chat_response
├── client.py          # completion() wrapper (AI-SPEC §3) — get_chat_response()
├── schemas.py          # ChatResponse, TradeAction, WatchlistChange (AI-SPEC §4b)
├── prompt.py            # SYSTEM_PROMPT + build_messages(history, portfolio_ctx, user_text)
├── context.py            # build_portfolio_context(conn, price_cache) -- NEW, not in AI-SPEC's file list
├── executor.py            # execute_actions(conn, cache, market_source, parsed) -> (executed_trades, executed_changes)
├── persistence.py          # save_chat_message(), load_recent_chat_messages() -- the two-transaction split
├── mock.py                  # LLM_MOCK=true pattern-matcher (D-11)
└── router.py                  # create_chat_router(get_conn, market_source, price_cache, mock: bool)

backend/tests/llm/
├── conftest.py         # chat_client fixture (mirrors portfolio_client), autouse network-block fixture
├── fixtures/
│   └── chat_scenarios.py  # the 12 scenarios from AI-SPEC §5 -- shared by mock.py tests AND router tests
├── test_schemas.py      # ChatResponse/TradeAction/WatchlistChange validation (TEST-02)
├── test_client.py        # get_chat_response() timeout/malformed-output branches (TEST-02, mocked litellm.completion)
├── test_mock.py            # mock.py pattern-matcher against all 12 scenarios (CHAT-06)
├── test_executor.py         # execute_actions() against real execute_trade()/apply_watchlist_change() (CHAT-02/03)
├── test_persistence.py        # transaction split: user row survives timeout, assistant row only after success (CHAT-04/05)
└── test_router.py               # HTTP-level: status codes, response shape, mock-mode E2E (TEST-03)

frontend/
├── vitest.config.mts        # NEW -- jsdom environment, react + tsconfig-paths plugins
├── vitest.setup.ts           # NEW -- imports @testing-library/jest-dom matchers
├── components/
│   ├── ChatDrawer.tsx          # NEW -- D-01/D-02/D-03: collapsed-by-default bottom overlay + toggle
│   ├── ChatMessageList.tsx      # NEW -- scrolling history, quick-prompts when empty (D-07/D-08)
│   ├── ChatMessageBubble.tsx     # NEW -- user vs assistant styling, error-bubble variant (D-09/D-10)
│   └── TradeConfirmationCard.tsx  # NEW -- success/REJECTED variants (D-04/D-05)
├── hooks/
│   └── useChat.ts                  # NEW -- mirrors usePortfolio.ts's fetch/state/error pattern
└── __tests__/ or co-located *.test.tsx  # TEST-04 -- see Pattern 4
```

### Pattern 1: Router Factory (mirror existing convention exactly)

**What:** Every existing router (`create_watchlist_router`, `create_portfolio_router`, `create_stream_router`) is a plain function taking `get_conn: Callable[[], sqlite3.Connection]` plus whatever collaborators it needs, returning a fresh `APIRouter` per call — no dependency-injection framework, no module-level router object.

**When to use:** Every new route in this codebase, including chat.

**Example:**
```python
# Source: backend/app/portfolio/router.py:42-52 (read this session)
def create_portfolio_router(
    get_conn: Callable[[], sqlite3.Connection],
    market_source: MarketDataSource,
    price_cache: PriceCache,
) -> APIRouter:
    """Create the portfolio router with injected DB connection, source, and cache.

    Factory pattern (mirrors create_watchlist_router): returns a fresh
    APIRouter per call so tests can build it repeatedly.
    """
    router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])
    ...
    return router
```

Chat router should follow this exactly:
```python
def create_chat_router(
    get_conn: Callable[[], sqlite3.Connection],
    market_source: MarketDataSource,
    price_cache: PriceCache,
    mock: bool = False,
) -> APIRouter:
    router = APIRouter(prefix="/api/chat", tags=["chat"])

    @router.post("")
    async def post_chat(request: ChatRequest) -> dict:
        conn = get_conn()
        result = await handle_chat_message(conn, market_source, price_cache, request.message, mock)
        if result is None:
            return {"message": GENERIC_RETRY_MESSAGE, "actions": {"trades": [], "watchlist_changes": []}}
        return result

    return router
```
Mount in `backend/app/main.py` alongside the other three (`app.include_router(create_chat_router(get_db, source, cache, mock=llm_mock_enabled))`), same registration-order rule (`/api/*` before `app.frontend(...)`) already documented at `main.py:82-83`.

### Pattern 2: Explicit-Transaction Split Around an Awaited Call

**What:** `backend/app/portfolio/trades.py:1-19` (module docstring, read this session) documents *why* the connection is opened `autocommit=True` and every multi-write operation wraps itself in explicit `BEGIN`/`COMMIT`/`ROLLBACK` with **zero awaits inside the block** — a coroutine only yields at an `await`, so a block with no await inside it is what serializes concurrent writers on the single-threaded event loop. `execute_trade()` (`trades.py:126-147`, read this session) is the concrete precedent: `conn.execute("BEGIN")` → four synchronous writes (`positions`, `trades`, `users_profile`, `portfolio_snapshots` via `record_snapshot()`) → `conn.execute("COMMIT")`, wrapped in `try/except` with `ROLLBACK` on any exception.

**Why this matters for chat specifically:** the LLM call is the one `await` in the entire request that cannot be avoided (up to 30s). It must never be inside a `BEGIN`/`COMMIT` block, or it would hold the SQLite writer lock (single-writer database) for the full LLM round-trip, blocking the 30s snapshot task and any trade the user submits from the trade bar in another tab.

**When to use:** Chat message persistence splits into exactly two transactions, with the LLM call and action execution *between* them, never inside either:

```python
# Transaction 1 -- before the await, in its own commit (CHAT-04)
conn.execute("BEGIN")
try:
    conn.execute(
        "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
        "VALUES (?, ?, 'user', ?, NULL, ?)",
        (uuid.uuid4().hex, user_id, user_text, now_iso),
    )
    conn.execute("COMMIT")
except Exception:
    conn.execute("ROLLBACK")
    raise

# NOT in a transaction -- reads only, no writes:
portfolio_ctx = build_portfolio_context(conn, price_cache)
history = load_recent_chat_messages(conn, limit=20)
messages = build_messages(SYSTEM_PROMPT, portfolio_ctx, history, user_text)

# The one await in the request -- deliberately outside any BEGIN/COMMIT:
parsed = mock_chat_response(user_text) if mock else await get_chat_response(messages)
if parsed is None:
    return None  # CHAT-05: nothing further persisted, no trade executed

# Each action call is itself already a self-contained transaction
# (execute_trade() opens its own BEGIN/COMMIT -- do NOT wrap these in an
# outer transaction, that would nest BEGINs, which SQLite rejects):
executed_trades = []
for t in parsed.trades:
    try:
        executed_trades.append({"success": True, **execute_trade(conn, price_cache, t.ticker, t.side, t.quantity)})
    except TradeError as err:
        executed_trades.append({"success": False, "ticker": t.ticker, "side": t.side,
                                  "quantity": t.quantity, "reason": err.detail})
executed_changes = [apply_watchlist_change(conn, market_source, c) for c in parsed.watchlist_changes]

# Transaction 2 -- after the await and all executions (CHAT-04/CHAT-05)
conn.execute("BEGIN")
try:
    conn.execute(
        "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
        "VALUES (?, ?, 'assistant', ?, ?, ?)",
        (uuid.uuid4().hex, user_id, parsed.message,
         json.dumps({"trades": executed_trades, "watchlist_changes": executed_changes}), now_iso2),
    )
    conn.execute("COMMIT")
except Exception:
    conn.execute("ROLLBACK")
    raise
```

**A subtlety not covered in AI-SPEC §4:** `execute_trade()` already opens and commits its own `BEGIN`/`COMMIT` internally (including its own `record_snapshot()` call). Do not wrap the loop over `parsed.trades` in an *additional* outer transaction — nested `BEGIN` statements are a SQLite error (`sqlite3.OperationalError: cannot start a transaction within a transaction`). Each trade/watchlist-change call commits independently; only the two `chat_messages` INSERTs need their own explicit transaction wrapper, matching how `execute_trade()` itself is called from `portfolio/router.py:76-78` — as a bare function call, no surrounding transaction.

### Pattern 3: `apply_watchlist_change()` — new helper, not existing

**What:** Neither `app/db/connection.py` nor `app/watchlist/router.py` expose a single "apply this change" function — the router inlines `add_watchlist_ticker`/`remove_watchlist_ticker` plus a conditional `market_source.add_ticker`/`remove_ticker` call. AI-SPEC §4's core-pattern snippet calls `apply_watchlist_change(conn, c)` as if it already exists; it does not. Build it as a thin wrapper reusing the exact DB-write-then-await-source order already established:

```python
# New file: backend/app/llm/executor.py
async def apply_watchlist_change(
    conn: sqlite3.Connection,
    market_source: MarketDataSource,
    change: WatchlistChange,  # {ticker, action: "add"|"remove"}
) -> dict:
    """Mirrors watchlist/router.py's add/remove logic exactly (read this
    session, router.py:79-115) so the LLM path can never diverge from the
    manual-endpoint path's rejection/idempotency rules."""
    ticker = normalize_ticker(change.ticker)
    if change.action == "add":
        inserted = add_watchlist_ticker(conn, ticker)
        if not inserted:
            return {"success": False, "ticker": ticker, "action": "add", "reason": "already on watchlist"}
        await market_source.add_ticker(ticker)
        return {"success": True, "ticker": ticker, "action": "add"}
    else:  # "remove"
        removed = remove_watchlist_ticker(conn, ticker)
        if not removed:
            return {"success": False, "ticker": ticker, "action": "remove", "reason": "not on watchlist"}
        if not ticker_has_open_position(conn, ticker):
            await market_source.remove_ticker(ticker)
        return {"success": True, "ticker": ticker, "action": "remove"}
```

**When to use:** Called once per `WatchlistChange` in `parsed.watchlist_changes`, same loop shape as the trades loop in Pattern 2.

### Pattern 4: Frontend Chat Drawer + Vitest Component Test

**What:** New components follow the existing `"use client"` + typed-props + hook-driven-state convention seen in `TradeBar.tsx`/`WatchlistPanel.tsx`. The drawer is a fixed-position overlay (D-01/D-02), collapsed by default (D-03), toggled from the header.

**Example (drawer skeleton, following `TradeBar.tsx`'s prop/state shape):**
```tsx
// New: frontend/components/ChatDrawer.tsx
"use client";
import { useState } from "react";
import { useChat } from "@/hooks/useChat";

export function ChatDrawer() {
  const [open, setOpen] = useState(false); // D-03: collapsed by default
  const { messages, sendMessage, sending, error, draft, setDraft } = useChat();

  return (
    <>
      <button onClick={() => setOpen((v) => !v)} className="fixed bottom-4 right-4 ...">
        {open ? "Close Chat" : "AI Chat"}
      </button>
      {open && (
        // D-01/D-02: bottom-anchored overlay, does not reflow the grid above it
        <div className="fixed inset-x-0 bottom-0 z-50 h-96 border-t border-terminal-border bg-terminal-panel">
          {/* ChatMessageList, quick-prompts when messages.length === 0 (D-07/D-08),
              input box that preserves `draft` on timeout (D-10) */}
        </div>
      )}
    </>
  );
}
```

**Vitest config, per the official Next.js 16 guide (read this session — `frontend/node_modules/next/dist/docs/01-app/02-guides/testing/vitest.md:63-88`):**
```ts
// New: frontend/vitest.config.mts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tsconfigPaths from 'vite-tsconfig-paths'

export default defineConfig({
  plugins: [tsconfigPaths(), react()],
  test: { environment: 'jsdom', setupFiles: ['./vitest.setup.ts'] },
})
```
```ts
// New: frontend/vitest.setup.ts
import '@testing-library/jest-dom/vitest'
```
Add to `frontend/package.json` scripts: `"test": "vitest run"` (use `run` not the bare watch-mode default, since CI/`npm test` must exit, not hang — the official guide's plain `vitest` script watches by default).

### Anti-Patterns to Avoid
- **Echoing `parsed.trades`/`parsed.watchlist_changes` directly into the persisted `actions` JSON or the client response.** AI-SPEC §5's EV-1 and Section 6's "Execution-derived action reporting" guardrail require the `actions` payload to be built *only* from `execute_trade()`/`apply_watchlist_change()` return values — never from what the model *asked for*. This is the single most important invariant in the whole phase (CFM #1).
- **Wrapping the trades/watchlist-changes execution loop in its own outer `BEGIN`/`COMMIT`.** `execute_trade()` already manages its own transaction; nesting fails at the SQLite level (Pattern 2 above).
- **Adding a second `asyncio.wait_for(..., timeout=30)` around `get_chat_response()`.** AI-SPEC §3 Pitfall 4 already prohibits this — `completion(timeout=30)` is the only timeout; a second one risks a lost handle to the still-running thread-pool call.
- **Building a fresh sqlite3 connection or transaction helper for chat instead of reusing `get_conn()`.** The whole app relies on exactly one process-wide connection (`app/db/connection.py:18` `_connection` singleton, `check_same_thread=False`); a second connection object risks the WAL-mode multi-connection subtleties Phase 2 deliberately avoided.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Trade validation (insufficient cash/shares) | A parallel "LLM trade validator" | `app.portfolio.trades.execute_trade()` (already imports and re-exports via `app.portfolio.__init__`) | AI-SPEC §6 explicitly requires this — the LLM path gets zero privilege over the manual path; duplicating validation is exactly how CFM #3 (invented tickers/quantities) becomes exploitable |
| Watchlist add/remove idempotency (`INSERT OR IGNORE`, position-referenced-ticker retention) | New watchlist mutation logic in `app/llm/` | `app.db.add_watchlist_ticker`/`remove_watchlist_ticker`/`ticker_has_open_position` (already exported from `app/db/__init__.py:30-43`) | Same reasoning — one source of truth for watchlist mutation rules |
| Portfolio/position P&L math for the prompt context | Recomputing market value / unrealized P&L from raw rows | `app.portfolio.valuation.portfolio_view()` / `position_views()` | Already the single place this arithmetic lives (`valuation.py:1-6` docstring, read this session) — three existing surfaces (GET /api/portfolio, trade response, snapshot recorder) already share it; a fourth (chat context) should too, not a fifth formula |
| Frontend test runner config | Hand-writing a custom Vite/Node test harness | `vitest` + official Next.js 16 manual-setup guide | Confirmed current guidance directly from `next` package docs shipped in `node_modules` this session — do not improvise a config |
| SSE/price-context reads inside the chat handler | A second subscription to the price stream | Direct `price_cache.get_price(ticker)` / `price_cache.get_all()` calls (same `PriceCache` instance injected into every other router) | `PriceCache` is explicitly the one shared in-memory source (`main.py:24-26` comment, read this session) — a second read path risks staleness the SSE stream doesn't have |

**Key insight:** Every "don't hand-roll" item in this table already has exactly one implementation living in this codebase from Phases 1–2. The chat module's job is almost entirely *composition* — call the existing functions in the right order, with the right transaction boundaries around the one new I/O operation (the LLM call) — not net-new business logic.

## Common Pitfalls

### Pitfall 1: Nested `BEGIN` from wrapping `execute_trade()` in an outer transaction
**What goes wrong:** `sqlite3.OperationalError: cannot start a transaction within a transaction` raised when the loop over `parsed.trades` opens its own `BEGIN` around calls to `execute_trade()`, which internally opens its own `BEGIN`.
**Why it happens:** Pattern-matching Phase 2's "wrap multi-writes in BEGIN/COMMIT" guidance too literally, without noticing `execute_trade()` is itself already the unit of transaction.
**How to avoid:** Only the two `chat_messages` INSERTs get explicit transaction wrappers in the new chat code; `execute_trade()`/`apply_watchlist_change()` calls are bare function calls, exactly as `portfolio/router.py:76-78` already calls `execute_trade()` with no surrounding `BEGIN`.
**Warning signs:** Any `sqlite3.OperationalError` in `backend/tests/llm/test_executor.py` during a multi-trade scenario (AI-SPEC scenario #10, "buy + watchlist add in one turn").

### Pitfall 2: Stale `__pycache__` confusion in `app/llm/`/`tests/llm/`
**What goes wrong:** `backend/app/llm/__pycache__/` and `backend/tests/llm/__pycache__/` currently contain `.pyc` files for `client.py`, `context.py`, `executor.py`, `mock.py`, `router.py`, `schema.py` — filenames that closely match this phase's planned module names — but the corresponding `.py` source files do not exist anywhere in this branch's history. `git log --all` traces them to commit `d4010c1` ("complete FinAlly implementation and integration testing"), which is **not an ancestor of the current `finally-gsd` branch** (confirmed via `git merge-base --is-ancestor`) — a prior, structurally different implementation attempt (that version also had `app/db/queries.py`, `models.py`, `app/dependencies.py`, none of which exist now) whose compiled bytecode was never cleaned from the working tree.
**Why it happens:** `__pycache__/` is gitignored (confirmed: `git status --porcelain` on those paths returns nothing, `git ls-files` returns nothing), so it survived branch resets that the tracked source did not.
**How to avoid:** Python cannot execute orphaned `.pyc` files without matching `.py` source present (import machinery requires the source or an `__init__.py` alongside), so this is not a functional risk — but delete both directories (`rm -rf backend/app/llm/__pycache__ backend/tests/llm/__pycache__`) as a first task in this phase's plan, purely so a developer inspecting the directory isn't misled into thinking prior work exists.
**Warning signs:** `ls backend/app/llm/` showing anything other than the newly-created files during Wave 0 of execution.

### Pitfall 3: vitest cannot resolve `@/` imports without `vite-tsconfig-paths`
**What goes wrong:** Every existing component (`WatchlistPanel.tsx`, `TradeBar.tsx`, `usePortfolio.ts`) imports via `@/components/...`/`@/hooks/...`/`@/lib/...`. Vitest (unlike Next's own webpack/Turbopack build) does not read `tsconfig.json`'s `paths` mapping by default.
**Why it happens:** Vitest runs on Vite, which resolves modules independently of Next.js's bundler; the official guide includes `vite-tsconfig-paths` specifically for TypeScript projects for this reason (confirmed: `node_modules/next/dist/docs/.../testing/vitest.md:33-44`, "Using TypeScript" install line).
**How to avoid:** Include `tsconfigPaths()` in the vitest plugins array (Pattern 4 above) from the very first test file — retrofitting it after several test files already exist means revisiting every import.
**Warning signs:** `Cannot find module '@/components/...' or its corresponding type declarations` errors the moment the first component test imports anything from the existing tree.

### Pitfall 4: `LLM_MOCK` env var read pattern must match the project's existing string-comparison convention
**What goes wrong:** A naive `bool(os.environ.get("LLM_MOCK"))` treats the literal string `"false"` as truthy (any non-empty string is truthy in Python), silently defeating the mock/live switch and making CI accidentally call the real API if `LLM_MOCK=false` is set explicitly rather than left unset.
**Why it happens:** Python's truthiness rules for strings are a classic footgun; PLAN.md §5 specifies `LLM_MOCK=true`/absent as the two states, implying an explicit equality check is required, not a bare truthiness check.
**How to avoid:** Mirror `factory.py:27`'s exact pattern for `MASSIVE_API_KEY` (`.strip()` then check), adapted for a boolean flag: `os.environ.get("LLM_MOCK", "").strip().lower() == "true"`.
**Warning signs:** `LLM_MOCK=false uv run pytest` (as opposed to simply unset) making a real network call during CI.

### Pitfall 5: Frontend test script must not default to watch mode in CI
**What goes wrong:** The official guide's suggested `package.json` script is `"test": "vitest"`, which runs in interactive watch mode and never exits — a CI/offline test run (per the phase's own TEST-04 requirement: "full backend and frontend unit suites run offline and green") would hang indefinitely.
**Why it happens:** Watch mode is vitest's sensible local-dev default, but the guide's example is written for interactive development, not CI.
**How to avoid:** Use `"test": "vitest run"` in `package.json` (Pattern 4 above) so `npm test` exits with a status code.
**Warning signs:** A CI job or `npm test` invocation that never returns.

## Code Examples

### Chat request/response Pydantic models (mirroring `AddTickerRequest`'s validator convention)
```python
# Source: pattern from backend/app/watchlist/router.py:23-34 (read this session)
class ChatRequest(BaseModel):
    """Request body for POST /api/chat."""
    message: str = Field(min_length=1)
```
A `min_length=1` field validator produces the 422-on-empty-message behavior implied by AI-SPEC §5 EV-7 ("rejects empty/missing message with 422") for free, matching the existing `TradeRequest`/`AddTickerRequest` pattern exactly — no custom validator needed for this field.

### Test fixture pattern (mirrors `portfolio_client` in `backend/tests/portfolio/test_router.py:35-53`)
```python
# New: backend/tests/llm/conftest.py
@pytest.fixture
def chat_client(initialized_db, monkeypatch):
    """TestClient wired to a real temp-DB connection, a fake source, seeded
    cache, and LLM_MOCK forced on so no test ever reaches the network."""
    monkeypatch.setenv("LLM_MOCK", "true")
    conn = initialized_db
    source = FakeMarketSource()  # reuse from tests/portfolio/test_trades.py
    cache = PriceCache()
    for ticker, price in SEED_PRICES.items():
        cache.update(ticker, price)

    app = FastAPI()
    app.include_router(create_chat_router(lambda: conn, source, cache, mock=True))

    with TestClient(app) as client:
        yield client, conn, source, cache


@pytest.fixture(autouse=True)
def block_real_llm_calls(monkeypatch):
    """CI hermeticity guard (AI-SPEC §5): if mock mode ever regresses and a
    test path reaches litellm.completion, fail loudly instead of needing a
    real API key."""
    def _raise(*args, **kwargs):
        raise RuntimeError("litellm.completion() called in a test — mock mode regression")
    monkeypatch.setattr("litellm.completion", _raise)
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Backend framework | `pytest>=8.3.0` + `pytest-asyncio>=0.24.0` + `pytest-cov>=5.0.0` (already installed, `backend/pyproject.toml:16-22`) |
| Backend config file | `backend/pyproject.toml:31-37` (`[tool.pytest.ini_options]`, `asyncio_mode = "auto"`) |
| Frontend framework | `vitest` (not yet installed — see § Standard Stack) |
| Frontend config file | `frontend/vitest.config.mts` (new, see Pattern 4) |
| Quick run command (backend) | `LLM_MOCK=true uv run --directory backend --extra dev pytest tests/llm -q` |
| Quick run command (frontend) | `npm run test --prefix frontend -- --run <path>` (or `vitest run <path>` once configured) |
| Full suite command (backend) | `LLM_MOCK=true uv run --directory backend --extra dev pytest -q --cov=app` |
| Full suite command (frontend) | `npm test --prefix frontend` (with `"test": "vitest run"`, see Pitfall 5) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CHAT-01 | POST /api/chat returns one complete response, no streaming | integration | `pytest tests/llm/test_router.py -x` | ❌ Wave 0 |
| CHAT-02 | Trades auto-execute via existing validation | integration | `pytest tests/llm/test_executor.py -x` | ❌ Wave 0 |
| CHAT-03 | Watchlist changes auto-execute | integration | `pytest tests/llm/test_executor.py -x` | ❌ Wave 0 |
| CHAT-04 | History persists; write ordering around the LLM call | unit | `pytest tests/llm/test_persistence.py -x` | ❌ Wave 0 |
| CHAT-05 | 30s timeout: no trade, not persisted | unit | `pytest tests/llm/test_client.py -x` (mocked `APITimeoutError`) | ❌ Wave 0 |
| CHAT-06 | LLM_MOCK deterministic responses | unit | `pytest tests/llm/test_mock.py -x` | ❌ Wave 0 |
| UI-08 | Chat panel UI (drawer, loading, confirmations) | component | `vitest run components/ChatDrawer.test.tsx` | ❌ Wave 0 |
| TEST-02 | Structured-output parsing incl. malformed | unit | `pytest tests/llm/test_schemas.py tests/llm/test_client.py -x` | ❌ Wave 0 |
| TEST-03 | Route status codes/response shapes | integration | `pytest tests/llm/test_router.py tests/portfolio/test_router.py tests/watchlist/test_router.py -x` | Partial — portfolio/watchlist exist, chat ❌ |
| TEST-04 | Frontend price flash/CRUD/portfolio calc/chat rendering | component | `vitest run` | ❌ — zero frontend tests currently exist at all |

### Sampling Rate
- **Per task commit:** relevant quick-run command above for the module just touched
- **Per wave merge:** full backend suite (`pytest -q --cov=app`) + full frontend suite (`npm test`)
- **Phase gate:** both full suites green before `/gsd-verify-work`; per AI-SPEC §5, hermeticity guard (`block_real_llm_calls` fixture) must also pass

### Wave 0 Gaps
- [ ] `backend/tests/llm/conftest.py` — `chat_client` fixture + `block_real_llm_calls` autouse fixture
- [ ] `backend/tests/llm/fixtures/chat_scenarios.py` — the 12 scenarios from AI-SPEC §5, shared across `test_mock.py`/`test_router.py`
- [ ] `frontend/vitest.config.mts` + `frontend/vitest.setup.ts` — no test runner exists at all yet
- [ ] `frontend/package.json` — add `"test": "vitest run"` script and the seven devDependencies from § Standard Stack
- [ ] Delete `backend/app/llm/__pycache__/` and `backend/tests/llm/__pycache__/` (Pitfall 2) before adding new source files, to avoid confusion during review

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `@testing-library/jest-dom` is worth installing even though the official Next.js guide's minimal example omits it | Standard Stack | Low — purely a DX/readability choice; omitting it just means more verbose `expect` assertions, no functional risk |
| A2 | The six npm/PyPI packages flagged `SUS` by the automated legitimacy checker are legitimate despite the flag (based on download counts and matching official GitHub orgs found during this session, not a manual per-package deep audit) | Package Legitimacy Audit | Low-medium — if any is in fact compromised, a `checkpoint:human-verify` before install (as the protocol requires regardless of my assessment) is the actual safety net, not this research |
| A3 | `execute_trade()` and `apply_watchlist_change()` calls made from inside the chat handler need no additional locking beyond what SQLite's autocommit + explicit-transaction pattern already provides, because (per `trades.py`'s own docstring) the single-threaded event loop already serializes any code path with no `await` between `BEGIN` and `COMMIT` | Architecture Patterns, Pattern 2 | Medium if wrong — a race between a chat-triggered trade and a trade-bar trade would show up as a lost update; the existing precedent (Phase 2 security review, T-02-11, per STATE.md) makes this a very well-tested assumption, not a novel one |

**If this table is empty:** N/A — see entries above; none of these are compliance/security-critical, all are low-to-medium risk implementation details already grounded in read source.

## Open Questions

1. **Should `apply_watchlist_change()` and the trade-execution loop live in `app/llm/executor.py` as shown, or should the router call `app.portfolio`/`app.watchlist` functions directly inline (skipping an `executor.py` module)?**
   - What we know: AI-SPEC's recommended project structure (§3) does include `router.py` calling helper functions, implying some intermediate layer; the existing `tests/llm/__pycache__` stale bytecode (from the unrelated prior attempt) happens to include an `executor.py` file, which is circumstantial but not authoritative.
   - What's unclear: whether the planner should treat "executor.py" as a hard module boundary or let the planner's own task-breakdown decide file granularity.
   - Recommendation: Non-blocking — either grouping works given the existing codebase's willingness to have small (`snapshots.py`, `valuation.py`) or larger single-purpose files; leave to planner discretion, informed by natural task boundaries (one task per file tends to work well in this codebase's history).

2. **Does the frontend need a `useChat` hook at all, or can `ChatDrawer.tsx` manage its own `fetch`/state inline (as `TradeBar.tsx` does for trade submission)?**
   - What we know: `usePortfolio.ts`/`usePriceStream.ts` are hooks because their state (prices, portfolio) is shared across multiple sibling components (`WatchlistPanel`, `PriceChart`, `PositionsTable`, `PortfolioHeatmap` all consume `prices`); `TradeBar.tsx` has no hook — it owns its form state locally since nothing else needs it.
   - What's unclear: chat message list state is likely only consumed by the drawer's own children (`ChatMessageList`, `ChatMessageBubble`), which argues against a hook per the `TradeBar` precedent — but a hook still aids testability (mockable in isolation for `ChatDrawer.test.tsx`).
   - Recommendation: A small `useChat` hook is still worth it purely for testability (vitest can test hook logic separately from render output via `@testing-library/react`'s `renderHook`), even though no sibling component needs the shared state — planner should treat this as a testing-ergonomics decision, not an architectural one.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `uv` | Backend dependency install/test run | ✓ | — (repo convention, `backend/CLAUDE.md`) | — |
| `npm` | Frontend dependency install/test run | ✓ | — (repo convention) | — |
| PyPI registry reachability | `uv add litellm pydantic` | ✓ (verified live during this research session) | — | — |
| npm registry reachability | `npm install` for vitest stack | ✓ (verified live during this research session) | — | — |
| `OPENROUTER_API_KEY` | Real (non-mock) LLM calls | Not verified in this session (reading `.env` contents is out of scope/denied by the sandbox boundary) | — | `LLM_MOCK=true` makes every automated test and CI path independent of this key entirely — the phase's own design goal |
| Network access to `openrouter.ai`/Cerebras | Real (non-mock) LLM calls, and the AI-SPEC-recommended manual live-smoke-check script | Not verified in this session | — | All required tests (TEST-02/03/04) run under `LLM_MOCK=true` and need no network; the live smoke check is explicitly a manual, non-CI, developer action per AI-SPEC §5 |

**Missing dependencies with no fallback:** none — every requirement in this phase's success criteria is satisfiable under `LLM_MOCK=true`.

**Missing dependencies with fallback:** `OPENROUTER_API_KEY`/network access — not needed for any automated test in this phase (see above); needed only for the developer's own manual verification that live mode actually works, which is explicitly out of CI scope per AI-SPEC §5's "Live smoke check" guidance.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Single hardcoded `user_id="default"`, no login, explicitly out of scope (REQUIREMENTS.md "Out of Scope") |
| V3 Session Management | No | No sessions — single-user local app |
| V4 Access Control | No | No multi-user boundary to enforce |
| V5 Input Validation | Yes | Pydantic `BaseModel` + `field_validator` on `ChatRequest.message` (min_length=1); ticker/quantity validation for LLM-proposed trades reuses `execute_trade()`'s existing `_TICKER_PATTERN`/`math.isfinite`/`quantity > 0` checks (`trades.py:79-82`) — the LLM path never bypasses these |
| V6 Cryptography | No | No new cryptographic operations in this phase; `OPENROUTER_API_KEY` handling is env-var passthrough to LiteLLM, same pattern as existing `MASSIVE_API_KEY` (`factory.py:27`) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via chat message content causing the LLM to propose unauthorized/oversized trades | Tampering / Elevation of Privilege | Structural: every proposed trade/watchlist change still passes through `execute_trade()`'s unmodified validation (insufficient cash/shares rejected outright, never clamped) — an injected instruction cannot bypass business-rule validation, only *request* an action that then gets rejected the same way a manual bad request would |
| Sensitive data (raw LLM prompts/responses containing portfolio figures) logged at `info` level, ending up in container logs indefinitely | Information Disclosure | AI-SPEC §4b already specifies: raw responses logged only at `warning`, truncated to ~500 chars, only on the malformed-output path — never full prompts/responses at `info` |
| Secrets (`OPENROUTER_API_KEY`) leaking into a client-visible response or error message | Information Disclosure | Existing pattern: `GET /api/health` explicitly documents "Never reports the API key" (`main.py:69-72`); the chat router must follow the same discipline — HTTPException details for chat failures should never include raw LiteLLM/HTTP error bodies that might echo request headers |
| A malformed/adversarial LLM response causing a crash instead of a safe degrade (this is functionally also a DoS-adjacent Tampering concern, not just correctness) | Denial of Service | AI-SPEC §6's structured-output validation gate — `ChatResponse.model_validate_json()` wrapped in `try/except (ValidationError, json.JSONDecodeError)` |

## Sources

### Primary (HIGH confidence)
- `backend/app/portfolio/router.py`, `backend/app/portfolio/trades.py`, `backend/app/watchlist/router.py`, `backend/app/db/connection.py`, `backend/app/db/schema.sql`, `backend/app/main.py`, `backend/app/market/factory.py`, `backend/app/portfolio/valuation.py`, `backend/app/portfolio/__init__.py`, `backend/app/watchlist/__init__.py`, `backend/app/db/__init__.py`, `backend/app/market/__init__.py` — all read directly this session
- `frontend/app/page.tsx`, `frontend/hooks/usePortfolio.ts`, `frontend/hooks/usePriceStream.ts`, `frontend/lib/format.ts`, `frontend/components/TradeBar.tsx`, `frontend/components/WatchlistPanel.tsx`, `frontend/app/globals.css`, `frontend/package.json` — all read directly this session
- `backend/tests/conftest.py`, `backend/tests/portfolio/test_router.py`, `backend/tests/portfolio/test_trades.py` — read directly this session
- `frontend/node_modules/next/dist/docs/01-app/02-guides/testing/vitest.md` — official Next.js 16 docs shipped with the installed package, read directly this session
- PyPI JSON API (`pypi.org/pypi/litellm/json`, `pypi.org/pypi/pydantic/json`) — queried live this session for version/publish-date verification
- `npm view <pkg> version` — queried live this session for all seven frontend test-tooling packages
- `git log --all`, `git merge-base --is-ancestor`, `git status --porcelain`, `git ls-files` — run this session to trace the stale `__pycache__` provenance (Pitfall 2)
- `03-AI-SPEC.md`, `03-CONTEXT.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `.planning/config.json`, `.claude/skills/cerebras/SKILL.md` — read directly this session

### Secondary (MEDIUM confidence)
- Package legitimacy checker (`gsd_run query package-legitimacy check`) — automated heuristic output, cross-checked against download counts/repo URLs in the same tool output (§ Package Legitimacy Audit note on `too-new` false positives)

### Tertiary (LOW confidence)
- None — this phase's non-AI-SPEC scope was fully groundable in existing source + official docs + live registry queries.

## Metadata

**Confidence breakdown:**
- Standard stack (backend): HIGH — locked by AI-SPEC/CONTEXT.md, versions verified live against PyPI
- Standard stack (frontend test infra): HIGH — sourced from official Next.js 16 docs shipped in the repo's own `node_modules`, versions verified live against npm
- Architecture (router/transaction patterns): HIGH — every pattern is a direct read of existing, already-shipped Phase 1/2 source with cited line numbers
- Architecture (new `apply_watchlist_change`/`executor.py` design): MEDIUM — necessarily new code with no existing precedent to cite verbatim, though it composes only already-verified existing functions
- Pitfalls: HIGH — five of five are grounded in either a direct source-code read (Pitfalls 1, 2, 4) or the official Next.js docs (Pitfalls 3, 5), not speculation
- Security domain: HIGH — ASVS applicability judgments follow directly from REQUIREMENTS.md's explicit out-of-scope list and existing `main.py`/`trades.py` patterns already read

**Research date:** 2026-08-25
**Valid until:** 30 days (stable backend patterns); frontend test-tooling versions should be re-verified if planning is delayed more than ~2 weeks, given the `too-new` signal reflects genuinely active release cadence on several packages
