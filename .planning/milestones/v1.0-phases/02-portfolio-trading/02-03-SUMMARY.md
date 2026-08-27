---
phase: 02-portfolio-trading
plan: 03
subsystem: ui
tags: [recharts, treemap, react, tailwind, portfolio]
requires:
  - phase: 02-portfolio-trading
    provides: "usePortfolio hook, PortfolioView/PositionView types, revalue() live re-marking (Plan 02-01/02-02)"
provides:
  - "PositionsTable.tsx: live-revaluing positions grid with D-01 empty state and shared selectedTicker"
  - "PortfolioHeatmap.tsx: Recharts Treemap sized by market_value, colored by unrealized_pnl sign, D-02 empty state"
  - "recharts 3.10.1 as a vetted npm dependency, gated behind a human legitimacy checkpoint"
  - "Final page.tsx composition: header -> disclosure -> TradeBar -> (Watchlist|PriceChart) -> (PositionsTable|PortfolioHeatmap) -> PnlChart"
affects: [phase-03-llm-copilot, phase-04-docker]
actuals:
  tokens: 3291
  tasks: 3
  commits: 2
tech-stack:
  added: ["recharts@3.10.1"]
  patterns:
    - "Recharts Treemap content prop receives a cloned React element with node data (ticker, weight, pnl, pnlPercent) and layout geometry (x, y, width, height) merged onto whatever custom props (selected, onSelect) were already set on it"
    - "Small-cell label suppression: width < 24 || height < 24 hides text rather than clipping it"
    - "Blue accent-blue selection outline/border reused verbatim across watchlist rows, positions rows, and heatmap tile strokes -- one shared visual language for selectedTicker"
key-files:
  created:
    - frontend/components/PositionsTable.tsx
    - frontend/components/PortfolioHeatmap.tsx
  modified:
    - frontend/app/page.tsx
    - frontend/package.json
    - frontend/package-lock.json
key-decisions:
  - "Task 2's blocking-human package-legitimacy checkpoint for recharts was approved by the user (npm downloads 58.5M/week, canonical recharts/recharts GitHub org, 100+ version history since 0.1.0 -- the [SUS] flag was a false positive on a latest-version-recency heuristic) before npm install ran"
  - "HeatmapCell declares selected/onSelect as required (non-optional) props so Recharts' cloneElement-based prop injection cannot accidentally shadow them, and the tile onClick calls onSelect(ticker) directly (not optional-chained) to keep the click handler a plain, always-wired call"
  - "'use client' uses single quotes in PortfolioHeatmap.tsx, matching PriceChart.tsx's existing precedent for the client-only chart-library directive, rather than the double quotes used elsewhere in that file and in PositionsTable.tsx -- both styles already coexist in the repo with no eslint quote-style rule enforcing consistency"
requirements-completed: [UI-04, UI-06]
coverage:
  - id: D1
    description: "Positions table shows ticker, quantity, avg cost, current price, unrealized P&L, and percent change per open position, all revaluing live against the SSE price stream (UI-06)"
    requirement: "UI-06"
    verification:
      - kind: unit
        ref: "npm run build (exit 0); npx tsc --noEmit (exit 0)"
        status: pass
    human_judgment: true
    rationale: "Live revaluation against the price stream and the flash/color/arrow reading are visual-timing behaviors that need a human or automated UI check per the plan's own <human-check> list; this agent verified the underlying data contract via a running dev server and a real trade (GET /api/portfolio showed correct market_value/unrealized_pnl after a buy) but did not click through the rendered DOM in a browser."
  - id: D2
    description: "Before any trade, the positions table and the heatmap panel both show the identical centered 'No positions yet' / 'Buy shares to get started.' empty state instead of bare headers or a hidden panel (D-01, D-02)"
    requirement: "UI-06"
    verification:
      - kind: unit
        ref: "grep -n 'No positions yet' frontend/components/PositionsTable.tsx; grep -n 'No positions yet' frontend/components/PortfolioHeatmap.tsx"
        status: pass
      - kind: integration
        ref: "curl http://localhost:8000/api/portfolio on a fresh db -- positions: [] confirmed, driving both components' showEmpty branch"
        status: pass
    human_judgment: false
  - id: D3
    description: "recharts enters the project only after a human approves the Task 2 package-legitimacy checkpoint; npm install recharts never runs unattended"
    requirement: "UI-04"
    verification:
      - kind: manual_procedural
        ref: "Task 2 checkpoint:human-verify, gate=blocking-human -- approved by the user before this agent ran npm install recharts"
        status: pass
    human_judgment: false
  - id: D4
    description: "Each heatmap tile is sized by that position's share of total holdings value (Treemap dataKey=weight over market_value) and filled green/red by the unrealized_pnl sign, with a signed percent label; the selected tile takes the shared accent-blue outline (UI-04, D-06, D-08)"
    requirement: "UI-04"
    verification:
      - kind: unit
        ref: "npm run build (exit 0); npx tsc --noEmit (exit 0); grep -c '#3fb950'/'#f85149'/'#209dd7' frontend/components/PortfolioHeatmap.tsx all >=1"
        status: pass
    human_judgment: true
    rationale: "Tile-area-tracks-dollar-weight, small-cell label suppression under real pixel dimensions, and click-driven cross-panel highlighting are visual/interaction behaviors that need a human or automated UI check per Task 3's own <human-check> list; this agent confirmed the data contract (one AAPL position, market_value and unrealized_pnl correct after a real trade) but did not render the treemap in a browser."
  - id: D5
    description: "Clicking a positions-table row or a heatmap tile selects that ticker, driving the main price chart and prefilling the trade bar, with the same accent-blue highlight on every surface (D-05, D-06, D-07, D-08)"
    requirement: "UI-06"
    verification:
      - kind: unit
        ref: "grep -n '<PositionsTable' / '<PortfolioHeatmap' frontend/app/page.tsx -- both wired with onSelect={setSelectedTicker} on the same element as selected={selectedTicker}"
        status: pass
    human_judgment: true
    rationale: "The end-to-end click -> chart switch -> trade-bar prefill chain is an interaction behavior needing a human or automated UI check; the shared-state wiring itself is statically verified via source inspection."
duration: ~35min
completed: 2026-08-24
status: complete
---

# Phase 2 Plan 3: Positions Table and Portfolio Heatmap Summary

**A live-revaluing positions table and a Recharts `Treemap` heatmap, both driving the same `selectedTicker` state the watchlist already owns, complete Phase 2's visual portfolio surfaces -- `recharts` entered the project only after a human approved its Task 2 legitimacy checkpoint.**

## Performance
- **Duration:** ~35min (this agent's portion: bringing in Task 1's fast-forwarded commit, then Task 3)
- **Completed:** 2026-08-24T20:14:26Z
- **Tasks:** 3/3 complete (Task 1 completed by a prior executor and fast-forward merged into this worktree; Task 2's checkpoint pre-approved by the user; Task 3 executed here)
- **Files modified:** 4 (2 created, 2 modified) across the plan; this agent's own work touched `PortfolioHeatmap.tsx` (new), `frontend/app/page.tsx`, `frontend/package.json`, `frontend/package-lock.json`

## Accomplishments
- `PositionsTable.tsx` (Task 1, inherited): a presentational grid mirroring `WatchlistPanel`'s chrome, row selection, keyboard handling, and colour-plus-glyph P&L reading; `page.tsx` owns the fetch via `usePortfolio`
- `recharts@3.10.1` installed after the Task 2 `gate="blocking-human"` legitimacy checkpoint was approved -- satisfies the `react@19.2.8` peer range already pinned in `package.json` with no peer warnings
- `PortfolioHeatmap.tsx`: `'use client'` Recharts `Treemap` inside a `ResponsiveContainer`, `dataKey="weight"` sizing each tile by `market_value`, a custom `HeatmapCell` filling `#3fb950`/`#f85149`/`#8b949e` by the `unrealized_pnl` sign, a `#209dd7` selected-tile outline matching the watchlist/positions blue, and `width < 24 || height < 24` label suppression so a tiny tile never clips or overlaps its ticker/percent text
- `page.tsx`'s positions/heatmap row now mounts both panels side by side (`PositionsTable` left, `PortfolioHeatmap` right) under a shared `h-72` bounded height, replacing Task 1's placeholder div; both share `selected={selectedTicker} onSelect={setSelectedTicker}` with the watchlist, so a click anywhere drives the main chart and prefills the trade bar
- All six panels (`WatchlistPanel`, `PriceChart`, `TradeBar`, `PositionsTable`, `PortfolioHeatmap`, `PnlChart`) are now mounted in `page.tsx`, completing Phase 2's UI surface

## Task Commits
1. **Task 1: Positions table with live P&L and shared selection** - `26d4ddf` (feat) -- executed by a prior executor in a sibling worktree, fast-forward merged into this branch before Task 3 began
2. **Task 2: Verify the recharts package before installing it** - checkpoint approved by the user; no commit (checkpoint tasks make no code changes)
3. **Task 3: Portfolio heatmap sized by weight, colored by P&L** - `d5276ed` (feat)

**Plan metadata:** (this commit, docs)

## Files Created/Modified
- `frontend/components/PositionsTable.tsx` - live-revaluing positions grid, D-01 empty state, keyboard-selectable rows (Task 1)
- `frontend/components/PortfolioHeatmap.tsx` - Recharts `Treemap` sized by weight, colored by P&L, D-02 empty state, small-cell label suppression (Task 3)
- `frontend/app/page.tsx` - mounts `PositionsTable` and `PortfolioHeatmap` in the positions/heatmap row, both wired to `selectedTicker` (Tasks 1 and 3)
- `frontend/package.json` / `frontend/package-lock.json` - adds `recharts@3.10.1` (Task 3)

## Decisions Made
- `HeatmapCell`'s `selected`/`onSelect` props are typed required, not optional, and the tile's `onClick` calls `onSelect(ticker)` directly rather than `onSelect?.(ticker)` -- both a correctness choice (Recharts' `React.cloneElement(content, nodeProps)` merges node data onto the element without touching props the element already carries, so these two props are always present) and what the plan's own acceptance-criteria grep for a literal `onSelect(` call expects
- Colour and stroke logic reads the literal hex values (`#3fb950`, `#f85149`, `#209dd7`, `#0d1117`, `#e6edf3`) rather than CSS custom properties, because SVG `fill`/`stroke` attributes need concrete strings -- these stay in sync with `frontend/app/globals.css`'s `--color-up`/`--color-down`/`--color-accent-blue`/`--color-terminal-bg`/`--color-terminal-text` tokens by design, per the plan's explicit instruction

## Deviations from Plan

None - Task 3 implementation matched the plan directly. The first draft used `MIN_LABEL_SIZE` as a named constant and optional-chained `onSelect?.()`, both functionally equivalent to the final version but not matching the plan's literal acceptance-criteria grep patterns (`width < 24|height < 24`, `onSelect(`); corrected before committing, not a deviation from intent.

## Issues Encountered
None.

## Verification Performed
- `npm --prefix frontend run build` — exit 0, `frontend/out/index.html` present
- `npx --prefix frontend tsc --noEmit -p frontend/tsconfig.json` — exit 0
- `npm --prefix frontend run lint` — 4 `react-hooks/set-state-in-effect` errors, all four pre-existing and already documented in `.planning/phases/02-portfolio-trading/deferred-items.md` (`WatchlistPanel.tsx:60,77`, `TradeBar.tsx:28`, `usePortfolio.ts:155`); no new errors from this plan's files
- `uv run --directory backend --extra dev pytest -q` — 168 passed, backend untouched by this plan
- All Task 3 `<acceptance_criteria>` greps re-verified individually against the final file contents (recharts in package.json, `'use client'`, `Treemap`, `dataKey="weight"`, `ResponsiveContainer`, both P&L colors, selected-tile stroke, empty-state copy, label-suppression condition, `onSelect(` call, `aria-label`, mount site in `page.tsx`, and the 6-panel count)
- Live smoke test: started `bash scripts/dev.sh`, confirmed `GET /` returns 200 with "Heatmap" in the served HTML, `GET /api/health` returns `{"status":"ok"}`, a fresh `GET /api/portfolio` returns `positions: []` (driving both empty states), then executed `POST /api/portfolio/trade` (buy 2 AAPL) and confirmed `GET /api/portfolio` returned the correct `market_value`/`unrealized_pnl`/`unrealized_pnl_percent` that both `PositionsTable` and `PortfolioHeatmap` consume -- server stopped cleanly afterward

## Human-Check Items (harvested for phase UAT batch, not executed in a browser by this agent)

From Task 1's `<verify>` block:
1. Fresh database: Positions panel shows "No positions yet" / "Buy shares to get started." with the yellow "Positions" heading still visible
2. Buying 2 AAPL and 1 NVDA renders two rows with correct ticker/quantity/avg cost/price/P&L/Chg %, monospace, two decimals except quantity
3. Over 30s, Price/P&L/Chg % move with the stream; green/red cells carry an arrow glyph and a signed number
4. Clicking the AAPL row takes the blue left border/tint, switches the main chart, and fills the trade bar's ticker field
5. Tab-to-row + Enter performs the same selection
6. The blue selected-row treatment matches the watchlist's exactly
7. Selling all AAPL removes its row entirely, no dust row
8. A grayscale screenshot still distinguishes winners from losers via arrows/signs

From Task 3's `<verify>` block:
1. Fresh database: Heatmap panel shows the identical "No positions yet" / "Buy shares to get started." wording
2. Three tickers bought in clearly different dollar amounts produce three tiles whose areas visibly track the dollar weights
3. Each tile shows its ticker and a signed percent, green fill for a winner, red for a loser
4. Clicking a tile takes a blue outline, switches the main chart, highlights the matching positions row, and fills the trade bar
5. A fourth, tiny position's tile is small and drops its text label rather than clipping/overlapping
6. Selling one position removes its tile and the remaining tiles resize
7. A grayscale screenshot still distinguishes winners from losers via the signed percent labels
8. No browser console errors, no zero-width/height container warning

All sixteen items' underlying data contracts and static wiring are covered by `tsc`, `next build`, targeted greps, and a live curl-based smoke test against a running server; the visual rendering and interaction confirmation itself needs a human or automated UI check, per the plan's own framing.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
Phase 2's full UI surface (watchlist, price chart, trade bar, positions table, heatmap, P&L chart) is now mounted in `page.tsx` with `selectedTicker` shared across every ticker-driving panel. `recharts` is a vetted, human-approved dependency available for any future chart work. No blockers identified for Phase 3 (LLM copilot) or Phase 4 (Docker), beyond the pre-existing 4-instance `react-hooks/set-state-in-effect` lint drift already logged in `deferred-items.md`, still recommended as a dedicated cleanup pass before Phase 2 closes.

## Self-Check: PASSED

`frontend/components/PositionsTable.tsx` and `frontend/components/PortfolioHeatmap.tsx` both verified present on disk. Commits `26d4ddf` (Task 1, fast-forward merged) and `d5276ed` (Task 3) both verified present in `git log --oneline`.

---
*Phase: 02-portfolio-trading*
*Completed: 2026-08-24*
