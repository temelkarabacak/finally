---
phase: 01-live-market-terminal
reviewed: 2026-08-23T18:18:38Z
depth: standard
files_reviewed: 42
files_reviewed_list:
  - .gitignore
  - backend/app/db/__init__.py
  - backend/app/db/connection.py
  - backend/app/db/schema.sql
  - backend/app/db/seed.py
  - backend/app/main.py
  - backend/app/market/__init__.py
  - backend/app/market/factory.py
  - backend/app/market/failover.py
  - backend/app/market/massive_client.py
  - backend/app/watchlist/__init__.py
  - backend/app/watchlist/router.py
  - backend/pyproject.toml
  - backend/static/.gitkeep
  - backend/tests/api/__init__.py
  - backend/tests/api/test_app_startup.py
  - backend/tests/api/test_health.py
  - backend/tests/api/test_static_frontend.py
  - backend/tests/conftest.py
  - backend/tests/db/__init__.py
  - backend/tests/db/test_init.py
  - backend/tests/db/test_seed.py
  - backend/tests/market/test_factory.py
  - backend/tests/market/test_failover.py
  - backend/tests/watchlist/__init__.py
  - backend/tests/watchlist/test_router.py
  - backend/uv.lock
  - frontend/.gitignore
  - frontend/AGENTS.md
  - frontend/CLAUDE.md
  - frontend/README.md
  - frontend/app/favicon.ico
  - frontend/app/globals.css
  - frontend/app/layout.tsx
  - frontend/app/page.tsx
  - frontend/components/PriceChart.tsx
  - frontend/components/Sparkline.tsx
  - frontend/components/WatchlistPanel.tsx
  - frontend/eslint.config.mjs
  - frontend/hooks/usePriceStream.ts
  - frontend/next.config.ts
  - frontend/package-lock.json
  - frontend/package.json
  - frontend/postcss.config.mjs
  - frontend/public/file.svg
  - frontend/public/globe.svg
  - frontend/public/next.svg
  - frontend/public/vercel.svg
  - frontend/public/window.svg
  - frontend/tsconfig.json
  - scripts/dev.sh
  - scripts/smoke.sh
findings:
  critical: 0
  warning: 5
  info: 4
  total: 9
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-08-23T18:18:38Z
**Depth:** standard
**Files Reviewed:** 42 (source files; lock/asset files scanned but not deeply analyzed)
**Status:** issues_found

## Summary

Reviewed the walking-skeleton backend (FastAPI app wiring, lazy SQLite init/seed, market-data factory + new permanent-failover wrapper, watchlist CRUD router) and frontend (Next.js 16 static export: SSE price hook, watchlist panel, sparkline, price chart) for Phase 01. I ran the full pytest suite (124 passed), `ruff check` (clean), `next build` (succeeds), `tsc --noEmit` (clean), and `eslint` (2 real errors) to verify claims empirically rather than by inspection alone. I also wrote small repro scripts to test the new `FailoverMarketDataSource` self-cancellation path under real asyncio semantics rather than trusting that it "looks correct."

No critical/security defects found: all SQL is parameterized, no secrets are hardcoded, no dangerous eval/exec/innerHTML usage, ticker input is validated and normalized consistently. The main findings are a real lint-breaking bug in `WatchlistPanel.tsx`, a fragile asyncio self-cancellation pattern in the new failover code, a related missing-synchronization race in `FailoverMarketDataSource`, an unhandled-exception gap in the watchlist router, and a handful of dead-code/quality nits.

## Warnings

### WR-01: `WatchlistPanel.tsx` fails the project's own lint gate (`npm run lint` exits 1)

**File:** `frontend/components/WatchlistPanel.tsx:59-61` and `frontend/components/WatchlistPanel.tsx:68-82`
**Issue:** Running `npx eslint .` (the project's configured `lint` script, `eslint-config-next` 16.3.2) fails with two `react-hooks/set-state-in-effect` errors, exit code 1:
- Line 60: `refetch()` is called directly in an effect body, and `refetch` itself calls `setTickers(...)`, which the React Compiler ESLint rule flags as a synchronous setState-in-effect.
- Line 77: `setFlashClasses((prev) => ({ ...prev, [ticker]: "" }));` is called synchronously in the effect body (the paired `requestAnimationFrame` call on line 79 is fine, but the un-deferred reset call is not).

This means CI/lint would fail on this file as committed; it is not a hypothetical, I reproduced it directly:
```
$ npx eslint .
✖ 2 problems (2 errors, 0 warnings)
```
**Fix:** For the mount-fetch effect, move the request into an effect that owns its own async logic and doesn't call an external state-setting function reference directly from the effect body, e.g.:
```tsx
useEffect(() => {
  let cancelled = false;
  (async () => {
    const response = await fetch("/api/watchlist");
    if (!response.ok || cancelled) return;
    const data = (await response.json()) as WatchlistEntry[];
    if (!cancelled) setTickers(data.map((entry) => entry.ticker));
  })();
  return () => { cancelled = true; };
}, []);
```
For the flash-reset effect, defer both the clear and the re-apply into the animation frame callback so no setState call is synchronous in the effect body:
```tsx
requestAnimationFrame(() => {
  setFlashClasses((prev) => ({ ...prev, [ticker]: "" }));
  requestAnimationFrame(() => {
    setFlashClasses((prev) => ({ ...prev, [ticker]: cls }));
  });
});
```

### WR-02: `MassiveDataSource.stop()` cancels and awaits its own currently-running task

**File:** `backend/app/market/massive_client.py:64-73`, triggered via `backend/app/market/failover.py:71-81`
**Issue:** When a periodic poll (running inside `_poll_loop()`, stored as `self._task`) fails, `_poll_once()` invokes `self._on_permanent_failure()` (set by `FailoverMarketDataSource` to `self._on_permanent_failure`), which calls `await self._active.stop()`. Since this whole call chain (`_poll_loop → _poll_once → _on_permanent_failure → stop`) executes synchronously within the massive-poller task itself, `stop()`'s `self._task.cancel()` followed by `await self._task` is the task cancelling and then awaiting *itself*.

I verified empirically (via a standalone repro and an end-to-end `FailoverMarketDataSource` + `MassiveDataSource` integration test) that this currently resolves cleanly on this environment's Python/asyncio version — the pending `_must_cancel` flag causes `CancelledError` to be raised at the `await self._task` point, which `stop()`'s `except asyncio.CancelledError: pass` swallows, and execution continues normally. So this is not a proven functional bug today, but it depends on undocumented CPython asyncio scheduling internals (the ordering between the "task cannot await on itself" `RuntimeError` path and the `_must_cancel`-triggered `CancelledError` path) rather than on any documented, guaranteed behavior. This is fragile: a future Python version, or any code change that makes the failure path asynchronous relative to the task's own execution (e.g., adding an `await` before `stop()` is called), could change this from "works by luck" to "hangs or raises `RuntimeError: Task cannot await on itself`."
**Fix:** Don't have the running task cancel/await itself. Simplest robust fix: make `stop()` a no-op when called from within the task's own execution context (compare `self._task is asyncio.current_task()`), or restructure so `_on_permanent_failure` schedules the stop via `asyncio.get_running_loop().call_soon(...)` / simply clears `self._task = None` and lets `_poll_loop`'s own `if self._permanently_failed: break` handle loop termination without an explicit self-cancel:
```python
async def stop(self) -> None:
    if self._task and not self._task.done() and self._task is not asyncio.current_task():
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
    self._task = None
    self._client = None
```

### WR-03: `FailoverMarketDataSource` swaps `_active` without synchronizing readers

**File:** `backend/app/market/failover.py:48-61` (unsynchronized) vs. `failover.py:71-81` (`async with self._lock`)
**Issue:** `start`, `stop`, `add_ticker`, `remove_ticker`, and the `active`/`get_tickers` accessors all read `self._active` directly with no locking, while `_on_permanent_failure` reassigns `self._active` under `self._lock`. If `add_ticker`/`remove_ticker` is called concurrently with a failover swap (e.g., a user adds a ticker to the watchlist at the same moment a Massive poll fails), the call can read the stale (about-to-be-stopped) `massive` reference, so the mutation is silently applied to a source that's being torn down and never reaches the new simulator — losing the ticker add/remove until the next reconciliation.
**Fix:** Guard the read of `self._active` in each delegating method with the same lock used for the swap (or snapshot the reference once and use a `asyncio.Lock` read-side too), e.g.:
```python
async def add_ticker(self, ticker: str) -> None:
    async with self._lock:
        active = self._active
    await active.add_ticker(ticker)
```

### WR-04: Watchlist router doesn't handle `market_source` exceptions after the DB write succeeds

**File:** `backend/app/watchlist/router.py:90-95` (add) and `backend/app/watchlist/router.py:109-114` (remove)
**Issue:** `add_to_watchlist` and `remove_from_watchlist` both perform the DB mutation first, then call `await market_source.add_ticker(...)` / `await market_source.remove_ticker(...)` unguarded. If that call raises (e.g., a future `MassiveDataSource.add_ticker` implementation makes a network call, or any unexpected error), FastAPI will surface an unhandled 500 to the client even though the watchlist row was already committed — the client has no way to know the mutation partially succeeded, and the response body/status won't match the documented "next startup reconciles" comment (that comment only covers eventual consistency, not the immediate response to this request).
**Fix:** Wrap the source call and return a response that reflects partial success, or explicitly document/degrade gracefully:
```python
try:
    await market_source.add_ticker(ticker)
except Exception:
    logger.exception("Failed to add %s to market source; watchlist row already committed", ticker)
```

### WR-05: `test_static_frontend.py`'s backup fixture is not crash-safe

**File:** `backend/tests/api/test_static_frontend.py:13-42`
**Issue:** Both fixtures move the real `backend/static/` directory to `backend/static.bak` and restore it in a `finally` block. If a prior test run is killed (Ctrl-C, OOM, CI timeout) between the move and the restore, `static.bak` is left on disk. On the next run, `shutil.move(str(_STATIC_DIR), str(backup))` will move the (freshly created, empty) `_STATIC_DIR` *into* the existing `static.bak` directory (POSIX `mv` semantics — moving into an existing directory target) rather than overwriting it, corrupting the on-disk layout so the final restore no longer reconstructs the original `backend/static/` contents.
**Fix:** Guard against a pre-existing backup, e.g. fail fast or clean it up before starting:
```python
if backup.exists():
    raise RuntimeError(f"Stale {backup} from a previous failed run; remove it before testing")
```

## Info

### IN-01: Unused ref in `usePriceStream.ts`

**File:** `frontend/hooks/usePriceStream.ts:36,42`
**Issue:** `hasOpenedRef` is created and set to `true` in the `open` handler but is never read anywhere in the hook or its return value. Dead state.
**Fix:** Remove `hasOpenedRef` entirely, or if it was meant to distinguish "reconnecting" from "connecting" on the very first connection, actually use it in the `status` derivation.

### IN-02: `app.state.db` is set but never read

**File:** `backend/app/main.py:40`
**Issue:** `app.state.db = conn` is assigned during lifespan startup, but no route, test, or other module reads `app.state.db` anywhere in the codebase (confirmed via grep). All DB access goes through `app.db.get_db()`'s module-level singleton instead.
**Fix:** Remove the unused assignment, or if it's intended for future use/introspection, add a comment explaining why it's kept.

### IN-03: Redundant re-normalization in `add_to_watchlist`

**File:** `backend/app/watchlist/router.py:88`
**Issue:** `ticker = normalize_ticker(request.ticker)` re-normalizes a value that the Pydantic `field_validator` (`_normalize_and_validate`) already normalized via the same `normalize_ticker` function before the model was constructed. Harmless (idempotent) but redundant.
**Fix:** Use `request.ticker` directly; it is guaranteed already normalized.

### IN-04: Misleading comment about static-frontend route precedence

**File:** `backend/app/main.py:72-73`
**Issue:** The comment states "/api/* routes above always win because FastAPI resolves routes in registration order" — but per FastAPI's own `frontend()` docstring, "FastAPI path operations are checked first, and the frontend files are checked only if no normal route matched," independent of where `app.frontend(...)` is registered relative to other routes. The behavior described is correct, but the stated *reason* (registration order) is not what actually guarantees it.
**Fix:** Update the comment to reflect that `app.frontend()` is inherently low-priority by design, not because of call-order.

---

_Reviewed: 2026-08-23T18:18:38Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
