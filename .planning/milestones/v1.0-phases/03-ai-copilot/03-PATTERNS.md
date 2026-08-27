# Phase 3: AI Copilot - Pattern Map

**Mapped:** 2026-08-25
**Files analyzed:** 22 (backend: 9 new source + 7 new test; frontend: 4 components + 1 hook + 2 config)
**Analogs found:** 22 / 22 (all have at least a role-match; several exact)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `backend/app/llm/router.py` | route | request-response | `backend/app/watchlist/router.py` (factory shape) + `backend/app/portfolio/router.py` (single-await pattern) | exact |
| `backend/app/llm/schemas.py` | model | transform | `backend/app/portfolio/router.py` (`TradeRequest`) / `backend/app/watchlist/router.py` (`AddTickerRequest`) | exact |
| `backend/app/llm/executor.py` | service | CRUD (composition) | `backend/app/watchlist/router.py` (add/remove logic to lift into `apply_watchlist_change`) + `backend/app/portfolio/router.py` (trade-loop shape) | role-match (new composition, no direct precedent) |
| `backend/app/llm/persistence.py` | service | CRUD (transactional) | `backend/app/portfolio/trades.py` (`execute_trade` BEGIN/COMMIT/ROLLBACK block) | exact (transaction discipline) |
| `backend/app/llm/context.py` | service | transform | `backend/app/portfolio/valuation.py` (`portfolio_view`) | role-match |
| `backend/app/llm/client.py` | service | request-response (external API) | none in-repo (external LLM call) — use `.claude/skills/cerebras/SKILL.md` directly | no analog |
| `backend/app/llm/mock.py` | service | event-driven (rule matcher) | none in-repo — use `backend/app/market/factory.py`'s env-var branching style only | partial (env pattern only) |
| `backend/app/llm/prompt.py` | utility | transform | none in-repo — new | no analog |
| `backend/app/main.py` (modified) | config/wiring | request-response | itself (existing router mounting block, lines 78-80) | exact |
| `backend/tests/llm/conftest.py` | test | request-response fixture | `backend/tests/portfolio/test_router.py` fixture section (not yet read in full, but `chat_client` mirrors `portfolio_client` per RESEARCH.md §Code Examples) | exact |
| `backend/tests/llm/test_router.py` | test | request-response | `backend/tests/portfolio/test_router.py` | exact |
| `backend/tests/llm/test_client.py` | test | request-response (mocked) | none in-repo — new | no analog |
| `backend/tests/llm/test_mock.py` | test | event-driven | none in-repo — new | no analog |
| `backend/tests/llm/test_executor.py` | test | CRUD | `backend/tests/portfolio/test_trades.py` (execute_trade tests) | role-match |
| `backend/tests/llm/test_persistence.py` | test | CRUD (transactional) | `backend/tests/portfolio/test_trades.py` | role-match |
| `backend/tests/llm/test_schemas.py` | test | transform | pydantic validator tests pattern in `test_router.py`'s ticker-validation cases | role-match |
| `frontend/hooks/useChat.ts` | hook | request-response | `frontend/hooks/usePortfolio.ts` | exact |
| `frontend/components/ChatDrawer.tsx` | component | request-response | `frontend/components/TradeBar.tsx` | exact |
| `frontend/components/ChatMessageList.tsx` | component | transform (render) | `frontend/components/WatchlistPanel.tsx` (list rendering, not read this pass but implied by RESEARCH.md) | role-match |
| `frontend/components/ChatMessageBubble.tsx` | component | transform (render) | `frontend/components/TradeBar.tsx` (conditional styling by state) | role-match |
| `frontend/components/TradeConfirmationCard.tsx` | component | transform (render) | `frontend/components/TradeBar.tsx` (success/error styling: `text-down` class) | role-match |
| `frontend/vitest.config.mts` / `vitest.setup.ts` | config | — | none in-repo — official Next.js 16 docs (`node_modules/next/dist/docs/.../testing/vitest.md`) | no analog (external doc) |

## Pattern Assignments

### `backend/app/llm/router.py` (route, request-response)

**Analog:** `backend/app/watchlist/router.py` (factory signature) + `backend/app/portfolio/router.py` (error-to-HTTP mapping)

**Imports pattern** (`backend/app/watchlist/router.py` lines 1-18):
```python
from __future__ import annotations

import logging
import re
import sqlite3
from collections.abc import Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.db import add_watchlist_ticker, get_watchlist_tickers, remove_watchlist_ticker
from app.db import ticker_has_open_position as db_ticker_has_open_position
from app.market import MarketDataSource, PriceCache
from app.market.interface import normalize_ticker
```

**Factory pattern** (`backend/app/watchlist/router.py` lines 60-70, `backend/app/portfolio/router.py` lines 42-52):
```python
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
Chat router adds a `mock: bool = False` fourth parameter per RESEARCH.md Pattern 1; keep the `prefix="/api/chat", tags=["chat"]` convention identical.

**Error handling pattern** (`backend/app/portfolio/router.py` lines 70-90):
```python
@router.post("/trade")
async def trade(request: TradeRequest) -> dict:
    """Execute a market order. Rejections return 400 with a human-readable reason."""
    conn = get_conn()
    try:
        result = execute_trade(
            conn, price_cache, request.ticker, request.side, request.quantity
        )
    except TradeError as err:
        raise HTTPException(status_code=400, detail=err.detail) from err

    if request.side == "buy":
        try:
            await market_source.add_ticker(request.ticker)
        except Exception:
            logger.exception(
                "add_ticker failed after a committed buy of %s", request.ticker
            )
    return result
```
Chat's own timeout/malformed-output path returns 200 with a generic retry message rather than raising (per CONTEXT.md D-09/CHAT-05) — do not reuse the `HTTPException` pattern for that specific branch; reserve `HTTPException` for genuinely invalid requests (e.g., empty `message` via pydantic 422).

---

### `backend/app/llm/schemas.py` (model, transform)

**Analog:** `backend/app/portfolio/router.py` lines 26-39 (`TradeRequest`)

**Validator pattern** (verbatim, copy the shape):
```python
class TradeRequest(BaseModel):
    """Request body for POST /api/portfolio/trade."""

    ticker: str = Field(min_length=1)
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0)

    @field_validator("ticker")
    @classmethod
    def _normalize_and_validate(cls, value: str) -> str:
        normalized = normalize_ticker(value)
        if not normalized or not _TICKER_PATTERN.match(normalized):
            raise ValueError("ticker must contain only letters, '.', and '-'")
        return normalized
```
`ChatRequest` needs only `message: str = Field(min_length=1)` (RESEARCH.md Code Examples) — the empty-message-422 behavior is free from `min_length=1`, no custom validator needed. `TradeAction`/`WatchlistChange` (LLM structured-output schema, per PLAN.md §9) should reuse the same `ticker` normalize-and-validate pattern since they get echoed to `execute_trade()`/`apply_watchlist_change()`.

---

### `backend/app/llm/persistence.py` (service, CRUD transactional)

**Analog:** `backend/app/portfolio/trades.py` lines 126-147 (the `BEGIN`/`COMMIT`/`ROLLBACK` block inside `execute_trade`)

**Core transaction pattern** (copy exactly, adapt table/columns):
```python
conn.execute("BEGIN")
try:
    conn.execute(
        "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(user_id, ticker) DO UPDATE SET quantity=excluded.quantity, "
        "avg_cost=excluded.avg_cost, updated_at=excluded.updated_at",
        (uuid.uuid4().hex, user_id, ticker, new_qty, new_avg_cost, now_iso),
    )
    conn.execute(
        "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (uuid.uuid4().hex, user_id, ticker, side, quantity, price, now_iso),
    )
    conn.execute(
        "UPDATE users_profile SET cash_balance = ? WHERE id = ?", (new_cash, user_id)
    )
    record_snapshot(conn, compute_total_value(conn, cache, user_id), user_id, now_iso)
    conn.execute("COMMIT")
except Exception:
    conn.execute("ROLLBACK")
    raise
```
Module docstring (`backend/app/portfolio/trades.py` lines 1-19) explains *why*: autocommit=True connection, zero awaits inside BEGIN/COMMIT block, single-threaded event loop serialization. Copy this reasoning into `persistence.py`'s docstring since it now governs a second call site (chat's two-transaction split around the awaited LLM call, per RESEARCH.md Pattern 2). Critical: `save_chat_message()` (user) commits BEFORE the `await get_chat_response(...)` call; `save_chat_message()` (assistant) commits AFTER action execution — never wrap the LLM `await` or the `execute_trade()`/`apply_watchlist_change()` calls inside a `BEGIN`/`COMMIT` block (see Pitfall 1 in RESEARCH.md — nested BEGIN raises `sqlite3.OperationalError`).

---

### `backend/app/llm/executor.py` (service, CRUD composition)

**Analog:** `backend/app/watchlist/router.py` lines 79-115 (add/remove logic to extract into `apply_watchlist_change`)

**Watchlist add pattern** (lines 79-95):
```python
@router.post("", status_code=201)
async def add_to_watchlist(request: AddTickerRequest) -> dict:
    conn = get_conn()
    ticker = normalize_ticker(request.ticker)

    inserted = add_watchlist_ticker(conn, ticker)
    if not inserted:
        raise HTTPException(status_code=409, detail="Ticker already on watchlist")

    await market_source.add_ticker(ticker)
    return _entry_for(ticker, price_cache)
```

**Watchlist remove pattern** (lines 97-115):
```python
@router.delete("/{ticker}", status_code=204)
async def remove_from_watchlist(ticker: str) -> None:
    conn = get_conn()
    normalized = normalize_ticker(ticker)

    removed = remove_watchlist_ticker(conn, normalized)
    if not removed:
        raise HTTPException(status_code=404, detail="Ticker not on watchlist")

    if not db_ticker_has_open_position(conn, normalized):
        await market_source.remove_ticker(normalized)
```
`apply_watchlist_change()` in `executor.py` must convert the `HTTPException`-raising branches into a returned `{"success": False, "reason": ...}` dict instead (chat auto-executes, never surfaces raw HTTP errors to the LLM caller) — same DB-write-then-await-source order, same idempotency semantics (409/404 become `success: False` with a reason string).

**Trade loop pattern** — reuse `execute_trade()` directly, imported from `backend/app/portfolio/trades.py`:
```python
from app.portfolio.trades import TradeError, execute_trade
```
Do not reimplement validation — call `execute_trade(conn, price_cache, ticker, side, quantity)` and catch `TradeError` per action, exactly as `backend/app/portfolio/router.py` lines 75-80 does for the manual endpoint.

---

### `backend/app/main.py` (modified — router mounting)

**Analog:** itself, lines 78-84 (existing mounting block)

```python
app.include_router(create_watchlist_router(get_db, source, cache))
app.include_router(create_portfolio_router(get_db, source, cache))
app.include_router(create_stream_router(cache))

# Registered last: /api/* routes above always win because FastAPI resolves
# routes in registration order, and only unmatched paths fall through here.
app.frontend(
    "/",
    directory=Path(__file__).resolve().parents[1] / "static",
    fallback="index.html",
    check_dir=False,
)
```
Add `app.include_router(create_chat_router(get_db, source, cache, mock=llm_mock_enabled))` in the same block, before the `app.frontend(...)` call. Determine `llm_mock_enabled` with the exact env-comparison idiom `backend/app/market/factory.py:27` uses for `MASSIVE_API_KEY` (`.strip()` then explicit equality — never bare truthiness; RESEARCH.md Pitfall 4): `os.environ.get("LLM_MOCK", "").strip().lower() == "true"`.

---

### `frontend/hooks/useChat.ts` (hook, request-response)

**Analog:** `frontend/hooks/usePortfolio.ts` (fetch/state/error pattern, lines 111-177)

**Imports pattern** (lines 1-5):
```typescript
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import type { PriceTick } from "@/hooks/usePriceStream";
```

**Fetch/state pattern** (lines 127-158, adapt for POST instead of GET):
```typescript
const refresh = useCallback(async () => {
  try {
    const response = await fetch("/api/portfolio");
    if (!response.ok) {
      setError("Could not load portfolio");
    } else {
      const data = (await response.json()) as PortfolioView;
      setPortfolio(data);
      setError(null);
    }
  } catch {
    setError("Could not load portfolio");
  } finally {
    setLoaded(true);
  }
}, []);
```
`useChat.ts`'s `sendMessage` is POST-based (not polling like `usePortfolio`) — model it closer to `TradeBar.tsx`'s `submitTrade` (see below) for the request shape, but keep `usePortfolio.ts`'s state-shape conventions (`error`, `loaded`/`sending`, typed response). Per CONTEXT.md D-10, on a timeout/error the hook must NOT clear the `draft` (user's input) — mirror `TradeBar.tsx`'s pattern of only clearing on success (`setQuantity("")` only inside the `response.ok` branch).

---

### `frontend/components/ChatDrawer.tsx` / `ChatMessageBubble.tsx` (component, request-response)

**Analog:** `frontend/components/TradeBar.tsx` (full file, 106 lines)

**Imports pattern** (lines 1-3):
```typescript
"use client";

import { useEffect, useState, type FormEvent } from "react";
```

**Submit pattern with success/error branching** (lines 34-61):
```typescript
async function submitTrade(side: Side, event: FormEvent) {
  event.preventDefault();
  if (!canSubmit) return;

  setSubmitting(true);
  try {
    const response = await fetch("/api/portfolio/trade", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker, side, quantity: parsedQuantity }),
    });

    if (response.ok) {
      setQuantity("");
      setErrorMessage(null);
      await onTraded();
    } else if (response.status === 400) {
      const body = (await response.json()) as { detail?: string };
      setErrorMessage(body.detail ?? "Could not complete that trade — try again.");
    } else {
      setErrorMessage("Could not complete that trade — try again.");
    }
  } catch {
    setErrorMessage("Could not complete that trade — try again.");
  } finally {
    setSubmitting(false);
  }
}
```
Chat's `sendMessage` follows this exact try/response.ok/catch/finally shape. The generic retry message (D-09) renders as an inline error bubble in the message list rather than `errorMessage` state near the input — but the disable-while-in-flight (`submitting`/`sending`) and preserve-on-failure (draft stays, D-10) behaviors are a direct copy of this component's `submitting`/`quantity` state handling.

**Styling tokens** (line 102, `text-down` for error text; classes throughout use `terminal-border`, `terminal-panel`, `terminal-bg`, `terminal-text`, `accent-purple`):
```typescript
{errorMessage && <span className="text-xs text-down">{errorMessage}</span>}
```
Reuse `text-down`/`text-up` (locked in Phase 1) for rejected/successful `TradeConfirmationCard` variants (D-04/D-05), and `bg-terminal-panel border-terminal-border` for the drawer's bottom-sheet container (D-01/D-02).

---

## Shared Patterns

### Router factory convention
**Source:** `backend/app/watchlist/router.py:60-70`, `backend/app/portfolio/router.py:42-52`
**Apply to:** `backend/app/llm/router.py`
Every router is a plain function `create_X_router(get_conn, market_source, price_cache, ...)` returning a fresh `APIRouter()` per call — no DI framework, no module-level router singleton. Mounted in `main.py` alongside the other three, before `app.frontend(...)`.

### Explicit transaction discipline (no await inside BEGIN/COMMIT)
**Source:** `backend/app/portfolio/trades.py:1-19` (docstring) and `:126-147` (code)
**Apply to:** `backend/app/llm/persistence.py`, indirectly `backend/app/llm/executor.py`
Zero awaits between `conn.execute("BEGIN")` and `conn.execute("COMMIT")`. The chat handler's one unavoidable `await` (the up-to-30s LLM call) sits strictly between two separate transactions, never inside either. `execute_trade()`/`apply_watchlist_change()` calls are bare (non-transaction-wrapped) function calls between the two — each already manages its own internal transaction; nesting a `BEGIN` around them raises `sqlite3.OperationalError`.

### Ticker normalize-and-validate
**Source:** `backend/app/portfolio/router.py:33-39`, `backend/app/watchlist/router.py:28-34`
**Apply to:** `backend/app/llm/schemas.py` (`TradeAction.ticker`, `WatchlistChange.ticker`)
```python
_TICKER_PATTERN = re.compile(r"^[A-Z.\-]+$")

@field_validator("ticker")
@classmethod
def _normalize_and_validate(cls, value: str) -> str:
    normalized = normalize_ticker(value)
    if not normalized or not _TICKER_PATTERN.match(normalized):
        raise ValueError("ticker must contain only letters, '.', and '-'")
    return normalized
```

### Env-var boolean/string flag reading
**Source:** `backend/app/market/factory.py:27` (`MASSIVE_API_KEY` check, referenced not re-read this pass — confirmed via RESEARCH.md Pitfall 4)
**Apply to:** `backend/app/main.py` (`LLM_MOCK` check), `backend/app/llm/mock.py`
```python
os.environ.get("LLM_MOCK", "").strip().lower() == "true"
```
Never bare-truthiness-check an env string — `"false"` is truthy in Python.

### Fetch/state/error hook shape
**Source:** `frontend/hooks/usePortfolio.ts:111-177`
**Apply to:** `frontend/hooks/useChat.ts`
`useState` for the data, `error`, and a loaded/sending flag; a `useCallback`-wrapped async function doing `try { fetch → response.ok check → setState } catch { setError } finally { setLoaded }`.

### Theme tokens (Phase 1, reused for chat UI)
**Source:** `frontend/components/TradeBar.tsx` classnames throughout (`terminal-border`, `terminal-panel`, `terminal-bg`, `terminal-text`, `accent-purple`, `text-up`, `text-down`)
**Apply to:** `ChatDrawer.tsx`, `ChatMessageBubble.tsx`, `TradeConfirmationCard.tsx`
No new color tokens — the success/failed trade card variants (D-04/D-05) use existing `text-up`/`text-down` (green/red), the purple `accent-purple` for the submit/send button.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `backend/app/llm/client.py` | service | request-response (external) | First external LLM call in the codebase; follow `.claude/skills/cerebras/SKILL.md` exactly (`litellm.completion()`, `MODEL = "openrouter/openai/gpt-oss-120b"`, `extra_body={"provider":{"order":["cerebras"]}}`, `reasoning_effort="low"`, Pydantic `response_format`) — no in-repo precedent, RESEARCH.md/AI-SPEC.md already lock the shape |
| `backend/app/llm/mock.py` | service | event-driven | No rule-based matcher exists anywhere in the codebase; CONTEXT.md D-11 locks the *approach* only — exact keyword table is new, informed by AI-SPEC §5's 12 scenarios |
| `backend/app/llm/prompt.py` | utility | transform | No prompt-construction code exists yet; PLAN.md §9 gives content requirements, no code precedent |
| `backend/tests/llm/test_client.py`, `test_mock.py` | test | request-response / event-driven | No existing test mocks `litellm.completion` or an env-driven rule matcher; net-new test shape (mock `litellm.completion` via `monkeypatch.setattr`) |
| `frontend/vitest.config.mts`, `vitest.setup.ts` | config | — | Zero frontend test tooling currently installed; follow the official Next.js 16 Vitest guide shipped at `frontend/node_modules/next/dist/docs/01-app/02-guides/testing/vitest.md` verbatim, not an in-repo analog |

## Metadata

**Analog search scope:** `backend/app/portfolio/`, `backend/app/watchlist/`, `backend/app/market/`, `backend/app/main.py`, `backend/tests/portfolio/`, `frontend/hooks/`, `frontend/components/`
**Files read this session:** `backend/app/portfolio/router.py`, `backend/app/portfolio/trades.py`, `backend/app/watchlist/router.py`, `backend/app/main.py`, `frontend/hooks/usePortfolio.ts`, `frontend/components/TradeBar.tsx` (all read in full, ≤200 lines each, no re-reads needed)
**Pattern extraction date:** 2026-08-25
