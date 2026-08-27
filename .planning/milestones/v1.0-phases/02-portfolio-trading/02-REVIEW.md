---
phase: 02-portfolio-trading
reviewed: 2026-08-24T00:00:00Z
depth: standard
files_reviewed: 18
files_reviewed_list:
  - backend/app/main.py
  - backend/app/portfolio/__init__.py
  - backend/app/portfolio/router.py
  - backend/app/portfolio/snapshots.py
  - backend/app/portfolio/trades.py
  - backend/app/portfolio/valuation.py
  - backend/tests/portfolio/__init__.py
  - backend/tests/portfolio/test_router.py
  - backend/tests/portfolio/test_snapshots.py
  - backend/tests/portfolio/test_trades.py
  - backend/tests/portfolio/test_valuation.py
  - frontend/app/page.tsx
  - frontend/components/PnlChart.tsx
  - frontend/components/PortfolioHeatmap.tsx
  - frontend/components/PositionsTable.tsx
  - frontend/components/TradeBar.tsx
  - frontend/hooks/usePortfolio.ts
  - frontend/package.json
findings:
  critical: 2
  warning: 3
  info: 2
  total: 7
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-08-24T00:00:00Z
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found

## Summary

Backend portfolio module (`trades.py`, `snapshots.py`, `valuation.py`, `router.py`) is well tested (44/44 tests pass, ruff clean) and the transaction/rollback discipline in `execute_trade` is sound. However, `execute_trade` — the exported function the plan explicitly designates as the single validation gate for both manual and future LLM-driven trades (PLAN.md §9: "Each trade goes through the same validation as manual trades") — trusts its `side` and `quantity` arguments completely instead of validating them itself, relying entirely on the HTTP router's Pydantic schema. Called directly (as the future chat/LLM auto-execution path is designed to do), this allows fabricating cash out of thin air and writing corrupt `side` values into the trade ledger.

On the frontend, `PnlChart.tsx` diverges from the exact pattern its sibling `PriceChart.tsx` uses to avoid a ref-timing pitfall — the divergence means the P&L chart's Lightweight Charts instance is never created, so the chart permanently fails to render even once enough snapshots exist. `TradeBar.tsx` has no `onSubmit` guard on its `<form>`, so pressing Enter in either input reloads the page. `usePortfolio.ts`'s `refresh()` has an inconsistent early-return that skips the (independent) portfolio-history fetch on a non-2xx `/api/portfolio` response but not on a network-level failure.

## Critical Issues

### CR-01: `execute_trade` does not validate `side` or `quantity`, enabling a cash-fabrication exploit and corrupt trade records

**File:** `backend/app/portfolio/trades.py:62-116`
**Issue:**

`execute_trade` is exported (`app/portfolio/__init__.py`) as the shared trade-validation entry point, and PLAN.md §9 states the not-yet-built LLM chat module will call this exact function directly for auto-executed trades ("Each trade goes through the same validation as manual trades"). Today the only caller is `router.py`, whose `TradeRequest` Pydantic model enforces `quantity: float = Field(gt=0)` and `side: Literal["buy", "sell"]` — but `execute_trade` itself performs no equivalent check, so any direct caller (a future chat action executor, a script, a test) that skips the Pydantic layer can violate the fund invariant.

Reproduction, `side="buy"` with a negative quantity (old_qty=0, cash=10000, price=100):
```python
execute_trade(conn, cache, "AAPL", "buy", -100)
```
- `cost = quantity * price = -10000`
- `cost > cash + POSITION_EPSILON` → `-10000 > 10000` → `False` → **not rejected**
- `new_qty, new_avg_cost = new_position_after_buy(0, 0, -100, 100)` → `new_qty = -100`
- `new_cash = cash - cost = 10000 - (-10000) = 20000` — **cash doubles for free**
- `new_qty <= POSITION_EPSILON` is true, so `new_qty` is silently zeroed — the position never shows the negative number, but the cash credit is permanent and committed.

Reproduction, `side` is neither `"buy"` nor `"sell"` (e.g. `"short"`, or any typo/garbage string a malformed LLM response could contain): the `if side == "buy": ... else: # sell` structure treats every non-`"buy"` value as a sell. It passes the sell-side share check (`quantity > old_qty + POSITION_EPSILON`), executes sell math, and — critically — writes the literal invalid string into `trades.side` (line 132), corrupting the append-only ledger the schema documents as `side TEXT ("buy" or "sell")`.

Neither branch validates the fundamental preconditions before any write, contradicting the function's own docstring ("Every rejection happens before any write... the requested quantity is never reduced"). No existing test calls `execute_trade` with a non-positive quantity or an invalid `side`, so this gap is untested.

**Fix:**
```python
def execute_trade(
    conn: sqlite3.Connection,
    cache: PriceCache,
    ticker: str,
    side: str,
    quantity: float,
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    ticker = normalize_ticker(ticker)

    if side not in ("buy", "sell"):
        raise TradeError(f"Invalid trade side {side!r}.", "invalid_side")
    if not (quantity > 0) or not math.isfinite(quantity):
        raise TradeError("Quantity must be a positive, finite number.", "invalid_quantity")

    price = cache.get_price(ticker)
    ...
```
(import `math` at the top of the module.)

### CR-02: `PnlChart.tsx` never creates the chart — the container it needs is unmounted at the exact moment the mount effect runs

**File:** `frontend/components/PnlChart.tsx:31-75, 100-109`
**Issue:**

The chart-creation `useEffect` runs exactly once, on mount, with an empty dependency array (line 31: `}, []);`), and bails out silently if `containerRef.current` is `null` (line 32: `if (!containerRef.current) return;`). But the `<div ref={containerRef}>` that this effect depends on is only rendered when `!showEmptyState` (lines 100-109):

```tsx
{showEmptyState ? (
  <div>Building portfolio history…</div>
) : (
  <div ref={containerRef} className="min-h-0 flex-1" />
)}
```

`showEmptyState` is `!ready || points.length < 2` (line 90). On first render — before `usePortfolio`'s history fetch resolves, and for the first ~minute of the app's life even after it resolves (fewer than 2 snapshots exist) — `showEmptyState` is `true`, so the ref div does not exist in the DOM. The mount effect fires at this point, finds `containerRef.current === null`, and returns early without ever calling `createChart`/`chart.addSeries`, so `chartRef.current` and `seriesRef.current` stay `null` forever.

Later, once enough points arrive and `showEmptyState` flips to `false`, React mounts the container div — but the creation effect does not re-run (empty deps array), so no chart is ever created. The second effect (`seriesRef.current?.setData(...)`, lines 79-83) then silently no-ops on every points update because `seriesRef.current` is `null`. The result: the P&L chart panel renders an empty `<div>` forever, with no error, no data, and no chart — the feature this component exists to deliver never activates on a normal cold start.

This is a genuine regression relative to the sibling component `frontend/components/PriceChart.tsx`, which explicitly avoids this exact pitfall — its container div is *always* rendered unconditionally, with a comment stating why: "Zero or one point is a valid setData call -- it renders bare axes with no line, never a reason to unmount the chart." (`PriceChart.tsx:78-81`). `PnlChart.tsx`'s docstring even claims to mirror `PriceChart.tsx` "almost verbatim" (line 22) but diverges on exactly the one detail that matters.

**Fix:** Always render the chart container; move the empty-state messaging to an overlay instead of a replacement, e.g.:
```tsx
<div className="relative min-h-0 flex-1">
  <div ref={containerRef} className="absolute inset-0" />
  {showEmptyState && (
    <div className="absolute inset-0 flex flex-col items-center justify-center text-center text-terminal-muted">
      <span className="text-sm font-semibold">Building portfolio history</span>
      <span className="text-xs">
        Chart appears once enough data points are recorded — usually within a minute.
      </span>
    </div>
  )}
</div>
```

## Warnings

### WR-01: `TradeBar.tsx` form has no submit guard — pressing Enter reloads the page and loses all app state

**File:** `frontend/components/TradeBar.tsx:65-100`
**Issue:** The `<form>` (line 65) wraps two `type="submit"` buttons whose `onClick` handlers call `submitTrade(...)`, which calls `event.preventDefault()` — but that `preventDefault()` is on the *click* event, not the form's `submit` event. When a user presses Enter while focused in the ticker or quantity `<input>` (a very natural gesture right after typing a quantity), browsers perform implicit form submission by firing the form's native `submit` event directly; this does not run through either button's `onClick` handler in modern browsers. Since the `<form>` has no `onSubmit` handler and no `action`, the browser performs a full-page navigation (GET to the current URL), which reloads the SPA, drops the SSE connection, resets `selectedTicker`, and loses all client state.
**Fix:**
```tsx
<form
  className="flex items-center gap-2"
  onSubmit={(event) => event.preventDefault()}
>
```
or eliminate the ambiguity entirely by giving each button an explicit `onClick` and no `type="submit"` semantics reliance (keep `type="button"` and call `submitTrade` directly without depending on form submission at all).

### WR-02: `usePortfolio.ts` `refresh()` skips the history fetch inconsistently depending on failure mode

**File:** `frontend/hooks/usePortfolio.ts:121-152`
**Issue:** In the first `try` block (portfolio fetch), a non-2xx response does `setError(...); return;` (lines 124-127) — this `return` exits the entire `refresh()` function, skipping the second `try` block that fetches `/api/portfolio/history` entirely. But a thrown exception (network failure) is caught by the `catch` block (lines 131-132), which does *not* return, so the history fetch still runs. The two fetches are logically independent (per the code's own comments), so a transient `/api/portfolio` 5xx should not prevent `/api/portfolio/history` from being fetched — yet it does, while a network drop does not have the same effect. This also means that if a trade's immediate `refresh()` call happens to hit a portfolio 5xx, `historyLoaded`/`history` are never updated even though the trade itself succeeded and a new snapshot was recorded server-side.
**Fix:** Don't `return` out of the whole function; let control fall through to the history fetch regardless of the portfolio fetch's outcome:
```ts
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
// history fetch unconditionally follows
```

### WR-03: A failure in `market_source.add_ticker` turns an already-successful trade into a client-visible 500

**File:** `backend/app/portfolio/router.py:70-85`
**Issue:** `execute_trade` (line 76-78) fully commits the trade (cash, position, trade row, snapshot) before the handler reaches line 83's `await market_source.add_ticker(request.ticker)`. That call is unguarded — `FailoverMarketDataSource.add_ticker` (`app/market/failover.py:54-55`) simply delegates to the active source with no try/except. If the underlying source raises (e.g. a Massive API call failing during a buy), the exception propagates out of the route handler and FastAPI returns an unhandled 500 to the client, even though the trade already succeeded and is durably committed. The client has no way to distinguish this from "the trade failed," and `TradeBar.tsx`'s generic error handling would let the user retry, risking an unintended duplicate buy.
**Fix:**
```python
if request.side == "buy":
    try:
        await market_source.add_ticker(request.ticker)
    except Exception:
        logger.exception("add_ticker failed after a committed buy of %s", request.ticker)

return result
```

## Info

### IN-01: Ticker validation has no maximum length

**File:** `backend/app/portfolio/router.py:23`
**Issue:** `_TICKER_PATTERN = re.compile(r"^[A-Z.\-]+$")` accepts a string of unbounded length as long as it's letters, `.`, and `-`. Combined with `Field(min_length=1)` (no `max_length`), a client can send an arbitrarily long ticker string that passes validation, gets normalized, and is only rejected downstream by the price-cache lookup (`no_price`). Low impact (single-user, no auth), but a cheap `max_length=10` on the `ticker` field would close it off.
**Fix:** `ticker: str = Field(min_length=1, max_length=10)`

### IN-02: `formatQuantity` can render fractional quantities in scientific notation

**File:** `frontend/components/PositionsTable.tsx:35-37`
**Issue:** `Number(quantity).toString()` uses JavaScript's default `Number.prototype.toString()`, which switches to exponential notation for very small magnitudes (e.g. `0.0000001` → `"1e-7"`). Since positions can legitimately hold near-epsilon fractional quantities transiently (`POSITION_EPSILON = 1e-9`), a user could see a "Qty" column value like `1.5e-8` instead of a decimal.
**Fix:** Format with a fixed/adaptive decimal count instead, e.g. `quantity.toFixed(8).replace(/\.?0+$/, "")`.

---

_Reviewed: 2026-08-24T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
