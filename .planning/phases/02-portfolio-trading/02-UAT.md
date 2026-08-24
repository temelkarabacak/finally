---
status: testing
phase: 02-portfolio-trading
source: [02-VERIFICATION.md]
started: 2026-08-24T21:47:41Z
updated: 2026-08-24T21:47:41Z
---

## Current Test

number: 1
name: Fresh database: buy 2 AAPL and sell them back via the trade bar's Buy/Sell buttons in a running browser
expected: |
  Order fills instantly (no confirmation dialog, no page reload); Cash and Total Value in the header update immediately; a position row appears in the Positions table and a tile in the Heatmap, then both disappear when sold back to zero
awaiting: user response

## Tests

### 1. Fresh database: buy 2 AAPL and sell them back via the trade bar's Buy/Sell buttons in a running browser
expected: Order fills instantly (no confirmation dialog, no page reload); Cash and Total Value in the header update immediately; a position row appears in the Positions table and a tile in the Heatmap, then both disappear when sold back to zero
result: [pending]

### 2. Attempt a buy that exceeds cash (e.g. 100000 shares) and a sell of a ticker not held
expected: An inline red error message appears below the trade bar, both fields retain their entered values, and Cash/Total Value do not change
result: [pending]

### 3. Watch the header connection dot through a simulated disconnect/reconnect cycle (e.g. stop/restart the backend)
expected: Dot is green while the SSE stream is open, turns yellow while reconnecting, and red when closed, with the status word beside it
result: [pending]

### 4. Wait ~70 seconds after a fresh app start without trading, watching the P&L panel
expected: Panel shows "Building portfolio history" / "usually within a minute" for the first phase, then switches to a flat 10000.00 line with at least two points, proving the recorder runs unconditionally (D-04) with no trade
result: [pending]

### 5. Buy three tickers in clearly different dollar amounts and observe the heatmap
expected: Tile areas visibly track the dollar weights (not visually equal), each tile shows ticker + signed percent, green for winners and red for losers; a very small fourth position's tile suppresses its text label rather than clipping
result: [pending]

### 6. Click a watchlist row, a positions-table row, and a heatmap tile in turn
expected: Each click highlights the clicked item with the same accent-blue left-border/outline treatment, switches the main price chart to that ticker, and prefills the trade bar's ticker field
result: [pending]

### 7. Tab to a positions-table row and a watchlist row and press Enter or Space
expected: The same selection behavior as a mouse click occurs (keyboard-reachable rows)
result: [pending]

### 8. Take a grayscale screenshot of the positions table and the heatmap with at least one winner and one loser held
expected: Winners and losers remain distinguishable via arrow glyphs and signed numbers/percent labels alone, without relying on color
result: [pending]

## Summary

total: 8
passed: 0
issues: 0
pending: 8
skipped: 0
blocked: 0

## Gaps
