---
status: testing
phase: 02-portfolio-trading
source: [02-VERIFICATION.md, 02-04-SUMMARY.md]
started: 2026-08-24T21:47:41Z
updated: 2026-08-25T09:10:00Z
---

## Current Test

number: 4
name: Fresh database, no trade: watch the P&L panel for ~90 seconds (re-run after gap G-02-4 fix)
expected: |
  Panel shows "Building portfolio history" / "usually within a minute" at first, then switches
  on its own to a flat 10000.00 line with at least two points — no trade, no page reload, no
  manual refresh.
awaiting: user response

## Tests

### 1. Fresh database: buy 2 AAPL and sell them back via the trade bar's Buy/Sell buttons in a running browser
expected: Order fills instantly (no confirmation dialog, no page reload); Cash and Total Value in the header update immediately; a position row appears in the Positions table and a tile in the Heatmap, then both disappear when sold back to zero
result: pass

### 2. Attempt a buy that exceeds cash (e.g. 100000 shares) and a sell of a ticker not held
expected: An inline red error message appears below the trade bar, both fields retain their entered values, and Cash/Total Value do not change
result: pass

### 3. Watch the header connection dot through a simulated disconnect/reconnect cycle (e.g. stop/restart the backend)
expected: Dot is green while the SSE stream is open, turns yellow while reconnecting, and red when closed, with the status word beside it
result: pass

### 4. Wait ~70 seconds after a fresh app start without trading, watching the P&L panel (re-run after gap G-02-4 fix)
expected: Panel shows "Building portfolio history" / "usually within a minute" for the first phase, then switches to a flat 10000.00 line with at least two points, proving the recorder runs unconditionally (D-04) with no trade
result: [pending]
note: "Gap-closure plan 02-04 added a 10s client poll in usePortfolio.ts. Verifier independently confirmed 2 history points recorded within 70s of a cold start via a direct API probe, but the live-browser empty-state-to-chart DOM transition has not been re-observed since the fix — this is that re-observation."

### 5. Buy three tickers in clearly different dollar amounts and observe the heatmap
expected: Tile areas visibly track the dollar weights (not visually equal), each tile shows ticker + signed percent, green for winners and red for losers; a very small fourth position's tile suppresses its text label rather than clipping
result: pass

### 6. Click a watchlist row, a positions-table row, and a heatmap tile in turn
expected: Each click highlights the clicked item with the same accent-blue left-border/outline treatment, switches the main price chart to that ticker, and prefills the trade bar's ticker field
result: pass

### 7. Tab to a positions-table row and a watchlist row and press Enter or Space
expected: The same selection behavior as a mouse click occurs (keyboard-reachable rows)
result: pass

### 8. Take a grayscale screenshot of the positions table and the heatmap with at least one winner and one loser held
expected: Winners and losers remain distinguishable via arrow glyphs and signed numbers/percent labels alone, without relying on color
result: pass

## Summary

total: 8
passed: 7
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps

- gap_id: G-02-4
  truth: "Panel shows \"Building portfolio history\" then switches to a flat 10000.00 line with at least two points within ~70s of a fresh app start, with no trade required (D-04)"
  status: failed
  reason: "User reported: I've been waiting for about 2 minutes without making any trades, but the P&L history chart is still not showing even as a flat line. Follow-up: P&L history appeared after buying something — suggests the panel/chart only renders once a trade has happened, contrary to D-04's unconditional-recording intent."
  severity: major
  test: 4
  root_cause: "Backend recorder and GET /api/portfolio/history are both correct (verified live: returns [] at t=0, then a real snapshot at t=35s, unconditionally). The bug is frontend-only: usePortfolio.ts's mount useEffect (frontend/hooks/usePortfolio.ts:154-156) calls refresh() exactly once on page load, with no polling interval. The only other refresh() call site is TradeBar's onTraded callback (frontend/app/page.tsx:68) after a trade. So the initial history fetch races the backend's first 30s snapshot tick, returns [], and nothing ever re-fetches history again until a trade happens — the empty state (PnlChart.tsx:90, showEmptyState = !ready || points.length < 2) stays stuck indefinitely instead of resolving on its own."
  artifacts:
    - path: "frontend/hooks/usePortfolio.ts"
      issue: "Mount-only useEffect (lines 154-156) fetches portfolio history once and never re-polls; history state never advances without a trade-triggered refresh()"
  missing:
    - "A periodic re-fetch of /api/portfolio/history (interval <= the 30s snapshot cadence), cleaned up on unmount, so the P&L panel's cold-start data appears without requiring a trade"
  debug_session: ""
