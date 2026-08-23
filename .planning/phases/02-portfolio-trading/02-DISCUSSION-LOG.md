# Phase 2: Portfolio & Trading - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-23
**Phase:** 2-Portfolio & Trading
**Areas discussed:** Empty portfolio state, Ticker selection consistency

---

## Empty portfolio state

| Option | Description | Selected |
|--------|-------------|----------|
| Empty-state message (recommended) | Centered "No positions yet — buy shares to get started" message in place of the positions table body | ✓ |
| Hide the whole panel | Panel doesn't render until first trade; layout reflows | |
| Show table headers only | Column headers render with zero rows | |

**User's choice:** Empty-state message (recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Same empty-state message (recommended) | Consistent centered message where the heatmap treemap would render | ✓ |
| Hide the heatmap panel entirely | Panel doesn't render pre-trade | |
| Render an empty treemap frame | Bordered container, no tiles | |

**User's choice:** Same empty-state message (recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Same empty-state message (recommended) | "No portfolio history yet" until 2+ snapshots exist | ✓ |
| Plot a single flat starting point | Show one point at $10,000 even with 1 snapshot | |
| Hide the P&L chart panel entirely | Panel doesn't render until 2+ snapshots | |

**User's choice:** Same empty-state message (recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, starts at app startup (recommended) | Snapshot task runs from lifespan startup regardless of trades — records $10,000 flat-line history from minute one | ✓ |
| No, starts only after the first trade | Snapshot task only begins once a position is opened | |

**User's choice:** Yes, starts at app startup (recommended)
**Notes:** This also shortens how often the empty-state P&L message actually shows — history fills in within ~60s of app start even without a trade.

---

## Ticker selection consistency

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, same selection behavior (recommended) | Positions table rows call the same onSelect(ticker) used by WatchlistPanel | ✓ |
| No, positions table is display-only | Row clicks do nothing | |

**User's choice:** Yes, same selection behavior (recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, same selection behavior (recommended) | Heatmap tiles call the shared onSelect(ticker) too | ✓ |
| No, heatmap is view-only | Heatmap is purely visual, no click interaction | |

**User's choice:** Yes, same selection behavior (recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, prefill the trade bar (recommended) | selectedTicker also drives the trade bar's ticker input | ✓ |
| No, trade bar ticker is independent | Trade bar keeps its own separate ticker field | |

**User's choice:** Yes, prefill the trade bar (recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, consistent highlight (recommended) | One shared 'selected' visual treatment applied wherever the ticker appears | ✓ |
| No highlight needed | Selection only shows up via the main chart changing | |

**User's choice:** Yes, consistent highlight (recommended)

---

## Claude's Discretion

- Trade bar placement & exact layout (grid position, field/button arrangement) — purple submit button color and no-confirmation-dialog behavior are locked by PLAN.md, layout is open.
- Header live stats layout (arrangement of portfolio value, cash balance, connection dot relative to existing title/connection text) and whether header values flash on change.
- Trade execution / snapshot write serialization approach (SQLite WAL mode already in place; transaction wrapping strategy for trade execution is a backend implementation detail).
- Heatmap treemap library choice — mirrors the Phase 1 precedent of picking a charting library (Lightweight Charts) without asking.

## Deferred Ideas

None — discussion stayed within phase scope. Trade bar layout and header stats layout were offered as discussable areas but not selected; they remain in-scope for this phase under Claude's Discretion, not deferred to a future phase.
