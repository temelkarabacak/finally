---
phase: 02-portfolio-trading
fixed_at: 2026-08-24T21:39:15Z
review_path: .planning/phases/02-portfolio-trading/02-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 02: Code Review Fix Report

**Fixed at:** 2026-08-24T21:39:15Z
**Source review:** .planning/phases/02-portfolio-trading/02-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (critical_warning scope — CR-01, CR-02, WR-01, WR-02, WR-03; IN-01 and IN-02 excluded by scope)
- Fixed: 5
- Skipped: 0

**Verification environment:** All fixes were made and verified in an isolated git worktree (`.claude/worktrees/rf-02-769361-1787607391`, branch `gsd-reviewfix/02-769361`), fast-forwarded into `finally-gsd` on completion. Backend syntax/lint/test checks ran inside the worktree's own `uv` virtualenv (built fresh there, isolated from the main checkout). Frontend TypeScript syntax checking (Tier 2 `tsc --noEmit`) was **not run** because the worktree has no `node_modules` (by design — worktrees are dependency-free); those three fixes (CR-02, WR-01, WR-02) rely on Tier 1 (careful re-read of the diff) plus a close visual diff comparison against the existing, working sibling pattern (`PriceChart.tsx`). Re-running `tsc --noEmit` from the main checkout after this branch merges is recommended before the phase proceeds to the verifier stage.

## Fixed Issues

### CR-01: `execute_trade` does not validate `side` or `quantity`, enabling a cash-fabrication exploit and corrupt trade records

**Files modified:** `backend/app/portfolio/trades.py`
**Commit:** 6bcf38e
**Applied fix:** Added an `import math` and two guard clauses at the top of `execute_trade`, before any DB read or write: reject any `side` not in `("buy", "sell")` with `TradeError("invalid_side")`, and reject any non-finite or non-positive `quantity` with `TradeError("invalid_quantity")`. This closes the cash-fabrication path (negative-quantity buy) and the corrupt-ledger path (non-"buy"/"sell" `side` string silently treated as a sell) described in the finding, matching the function's own docstring contract that "every rejection happens before any write." Verified: `ruff check` clean, all 18 existing tests in `tests/portfolio/test_trades.py` still pass (no regressions), full `tests/portfolio/` suite (44 tests) passes.

### CR-02: `PnlChart.tsx` never creates the chart — the container it needs is unmounted at the exact moment the mount effect runs

**Files modified:** `frontend/components/PnlChart.tsx`
**Commit:** 0719b79
**Applied fix:** Changed the render so the `<div ref={containerRef}>` chart container is now always mounted (inside a `relative` wrapper, `absolute inset-0`), and the "Building portfolio history" empty-state message is rendered as an absolutely-positioned overlay on top of it rather than as a replacement for it. This matches the pattern already used successfully by the sibling `PriceChart.tsx` (whose container is unconditionally rendered), so the mount `useEffect` (which runs once, with an empty dependency array, and previously bailed out silently when `containerRef.current` was `null`) now always finds a real container element and creates the chart/series on first render.

### WR-01: `TradeBar.tsx` form has no submit guard — pressing Enter reloads the page and loses all app state

**Files modified:** `frontend/components/TradeBar.tsx`
**Commit:** 2e009f4
**Applied fix:** Added `onSubmit={(event) => event.preventDefault()}` to the `<form>` element, per the REVIEW.md fix suggestion. This stops the browser's native implicit-submission full-page navigation when Enter is pressed in either input, independent of the existing per-button `onClick` handlers (which already call `event.preventDefault()` on their own click events but do not intercept the form's native `submit` event).

### WR-02: `usePortfolio.ts` `refresh()` skips the history fetch inconsistently depending on failure mode

**Files modified:** `frontend/hooks/usePortfolio.ts`
**Commit:** 635ab40
**Applied fix:** Removed the early `return` from the non-2xx branch of the first (`/api/portfolio`) `try` block and replaced it with an `if/else`, so a failed portfolio fetch no longer exits `refresh()` early. Control now always falls through to the second (`/api/portfolio/history`) fetch block regardless of whether the first fetch succeeded, failed with a non-2xx response, or threw a network error — matching the code's own stated intent that the two fetches are independent.

### WR-03: A failure in `market_source.add_ticker` turns an already-successful trade into a client-visible 500

**Files modified:** `backend/app/portfolio/router.py`
**Commit:** 54f2524
**Applied fix:** Wrapped the post-commit `await market_source.add_ticker(request.ticker)` call (only reached on a successful buy) in a `try/except Exception` that logs via `logger.exception(...)` and swallows the error, so a downstream market-data failure after the trade has already durably committed no longer propagates as an unhandled 500 to the client. The already-computed `result` is still returned. Verified: `ruff check` clean, all 9 tests in `tests/portfolio/test_router.py` pass, full `tests/portfolio/` suite (44 tests) passes.

## Skipped Issues

None — all in-scope findings (CR-01, CR-02, WR-01, WR-02, WR-03) were fixed. IN-01 and IN-02 were out of scope for this run (`fix_scope: critical_warning`) and were not attempted.

---

_Fixed: 2026-08-24T21:39:15Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
