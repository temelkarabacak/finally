---
phase: 02-portfolio-trading
reviewed: 2026-08-25T00:00:00Z
depth: standard
files_reviewed: 1
files_reviewed_list:
  - frontend/hooks/usePortfolio.ts
findings:
  critical: 0
  warning: 1
  info: 1
  total: 2
status: issues_found
---

# Phase 02: Code Review Report (02-04 gap closure — P&L cold start)

**Reviewed:** 2026-08-25T00:00:00Z
**Depth:** standard
**Files Reviewed:** 1
**Status:** issues_found

## Summary

Reviewed the interval-polling change added by gap-closure plan 02-04 in `frontend/hooks/usePortfolio.ts` (lines 32, 160-169 in particular; the surrounding `refresh` callback at 127-158 was inspected only as far as needed to assess the new polling behavior). The change itself is small and correctly implemented as a React effect: `refresh` has a stable identity (`useCallback` with `[]` deps), so the effect at lines 160-169 mounts once, fires an immediate call, sets a single `setInterval`, and tears it down with `clearInterval` on unmount — no interval leak, no re-creation churn from the `prices` argument changing on every SSE tick.

The one substantive issue is that repeated polling (as opposed to the previous mount-only call) meaningfully increases the exposure window for an existing but previously low-probability race: `refresh()` issues two independent, un-cancelled `fetch` calls per invocation with no guard against overlap or out-of-order completion. Under real network jitter this can let a stale response clobber a fresher one — ironically able to reproduce a symptom adjacent to the exact bug (G-02-4) this plan closes (chart/portfolio state visibly reverting). This is not new code introduced by the diff line-for-line, but the diff is what turns a mostly theoretical race into a live, indefinitely-repeating one, so it is in scope here.

This review covers only the interval-polling change; findings already logged in `02-REVIEW.md` for plans 02-01 through 02-03 are not repeated.

## Warnings

### WR-01: Overlapping polls can let a stale response overwrite fresher state

**File:** `frontend/hooks/usePortfolio.ts:127-169`
**Issue:** `refresh` (lines 127-158) performs two `fetch` calls and unconditionally applies whatever response comes back via `setPortfolio`/`setHistory`, with no request-ordering guard, in-flight guard, or `AbortController`. Previously `refresh` only ran once on mount (plus ad hoc calls after a trade), so an overlapping pair of calls was rare. The new `setInterval(refresh, PORTFOLIO_POLL_INTERVAL_MS)` (line 167) fires unconditionally every 10s regardless of whether the prior invocation's `fetch` calls have resolved. If a poll started at t=0 is slow (network jitter, backend GC pause, etc.) and is still in flight when the t=10s poll starts and completes first, the t=0 response can land after and overwrite the newer t=10s response — reintroducing stale `portfolio`/`history` state, including the possibility of the P&L chart losing a data point it had just gained (the exact class of symptom this gap-closure plan targets). This is more likely to manifest now that polling runs indefinitely rather than once.
**Fix:** Guard against overlap and/or ignore out-of-order responses, e.g. track the latest request with a ref and only apply a response if it is still the most recent request, or skip starting a new poll while one is still in flight:
```ts
const inFlight = useRef(false);

const refresh = useCallback(async () => {
  if (inFlight.current) return;
  inFlight.current = true;
  try {
    // ...existing fetch logic...
  } finally {
    inFlight.current = false;
  }
}, []);
```
or use an `AbortController` per call and abort the previous request when a new one starts, applying responses only from the latest controller.

## Info

### IN-01: No test coverage for the new polling behavior

**File:** `frontend/hooks/usePortfolio.ts:160-169`
**Issue:** There is no test file for this hook (`frontend/hooks/usePortfolio.ts` has no corresponding `*.test.ts(x)`), so the new `setInterval`/`clearInterval` behavior that this gap-closure plan added — including the interval-cleanup-on-unmount contract it relies on to avoid leaking timers — is unverified by automated tests.
**Fix:** Add a test (e.g. with `@testing-library/react` and fake timers) asserting: `refresh` is called immediately on mount, called again after `PORTFOLIO_POLL_INTERVAL_MS` elapses, and the interval is cleared on unmount (no further `fetch` calls after unmount + timer advance).

---

_Reviewed: 2026-08-25T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
