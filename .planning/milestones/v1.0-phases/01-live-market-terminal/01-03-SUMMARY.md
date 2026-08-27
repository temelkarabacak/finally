---
phase: 01-live-market-terminal
plan: 03
subsystem: frontend-ui
tags: [nextjs, typescript, tailwindcss, lightweight-charts, sse, terminal-theme]

# Dependency graph
requires:
  - phase: 01-01
    provides: "frontend/ Next.js scaffold, usePriceStream hook, app/globals.css minimal theme token"
  - phase: 01-02
    provides: "frontend/components/WatchlistPanel.tsx with add/remove watchlist UI and selectedTicker state in app/page.tsx"
provides:
  - "frontend/app/globals.css: full Tailwind v4 @theme dark-terminal token set (terminal-bg, terminal-panel, terminal-border, terminal-text, terminal-muted, accent-yellow, accent-blue, accent-purple, up, down) and flash-up/flash-down keyframes honoring prefers-reduced-motion"
  - "frontend/components/Sparkline.tsx: inline SVG per-row sparkline, no charting library"
  - "frontend/components/PriceChart.tsx: Lightweight Charts v5 wrapper for the selected ticker"
  - "frontend/hooks/usePriceStream.ts: timeline buffer (deduped/floored-second, capped 120) alongside history"
  - "frontend/components/WatchlistPanel.tsx: flashing rows, arrow+percent direction cues, sparkline column, keyboard-selectable rows"
affects: [portfolio-phase, ai-copilot-phase, docker-phase]

# Actuals (#2632)
actuals:
  tokens: 66000
  tasks: 3
  commits: 2

# Tech tracking
tech-stack:
  added: ["lightweight-charts ^5.2.1 (resolved 5.2.1)"]
  patterns:
    - "Theme tokens defined once in a single @theme block in globals.css and consumed everywhere via CSS custom properties -- the contract Phases 2 and 3 reuse for the heatmap, P&L chart, and chat panel"
    - "Per-ticker animation-retrigger via a counter keyed into the flash class name, since re-triggering a CSS animation on an element that is still animating requires a class-identity change, not a timer"
    - "PriceChart creates the chart once on mount (useEffect keyed on nothing) and calls setData (not update) in a second effect keyed on [ticker, points], so switching tickers replaces the series wholesale instead of appending"
    - "timeline buffer dedupe: floor SSE timestamps to whole seconds, replace-if-equal, drop-if-less-than, append-otherwise -- required because Lightweight Charts rejects non-ascending/duplicate time values and SSE frames arrive faster than 1/sec"

key-files:
  created:
    - frontend/components/Sparkline.tsx
    - frontend/components/PriceChart.tsx
  modified:
    - frontend/app/globals.css
    - frontend/app/layout.tsx
    - frontend/components/WatchlistPanel.tsx
    - frontend/package.json
    - frontend/package-lock.json
    - frontend/hooks/usePriceStream.ts
    - frontend/app/page.tsx

key-decisions:
  - "--color-up #3fb950 / --color-down #f85149 chosen for contrast against #0d1117, transcribed verbatim from the executor that implemented Task 1 and re-confirmed by reading frontend/app/globals.css directly during this summary pass -- matches exactly"
  - "Flash keyframes wrapped in @media (prefers-reduced-motion: no-preference); a separate (prefers-reduced-motion: reduce) block applies the tint statically with no animation, so direction is still color-communicated without the fade"
  - "lightweight-charts installed at ^5.2.1 (resolved 5.2.1), matching the version already cleared by the Plan 01-01 legitimacy checkpoint -- confirmed in frontend/package.json"

patterns-established:
  - "Inline SVG sparkline (no charting library) for decorative per-row minicharts -- ten-plus canvas/chart instances in a grid would be real per-row overhead for a decorative line; Lightweight Charts is reserved for the one large, interactive main chart"

requirements-completed: [UI-01, UI-02, UI-03, UI-10]

coverage:
  - id: D1
    description: "Every watchlist row shows ticker, current price, signed change percent, an arrow glyph, and a sparkline accumulated from the SSE stream since page load; a sparkline with zero points renders nothing, one point renders a centered mark, and an all-identical series renders a flat line instead of dividing by zero"
    requirement: "UI-01"
    verification:
      - kind: unit
        ref: "grep assertions in 01-03-PLAN.md Task 1 acceptance_criteria (return null / max === min / aria-hidden / <Sparkline / toFixed(2)) -- all matched during Task 1 execution"
        status: pass
      - kind: integration
        ref: "npm --prefix frontend run build && bash scripts/smoke.sh"
        status: pass
      - kind: manual
        ref: "Task 3 checkpoint item 5 (color independence) and item 6 (sparklines) -- human-verified live"
        status: pass
    human_judgment: true
    rationale: "The grid-shape and null/flat-line guards are grep- and build-verifiable, but whether a sparkline reads as honest progressive history (short line for a fresh ticker, not implying a full session) and whether direction is legible from the arrow+percent alone without color are perceptual judgments -- Task 3 items 5 and 6, approved by the human against the running app."
  - id: D2
    description: "A price change briefly tints its row green (uptick) or red (downtick), fading to transparent over roughly 500ms, never repeating or looping across ten simultaneously-updating rows, and honoring prefers-reduced-motion by keeping the color change while suppressing the animated fade"
    requirement: "UI-02"
    verification:
      - kind: unit
        ref: "grep assertions in 01-03-PLAN.md Task 1 (flash-up/flash-down present, 'infinite' absent, prefers-reduced-motion present) -- all matched during Task 1 execution"
        status: pass
      - kind: manual
        ref: "Task 3 checkpoint item 3 (flash reads as calm shimmer, not a strobe, over 30s of live streaming) and item 4 (reduced-motion honored)"
        status: pass
    human_judgment: true
    rationale: "Whether a 500ms fade across ten rows updating twice a second reads as calm or as a strobe is a perceptual judgment no grep or build check can settle -- flagged unresolved by the plan's own edge-case engine and explicitly routed to Task 3 item 3, which the human approved as PASS."
  - id: D3
    description: "Clicking a watchlist row draws a larger Lightweight Charts price series for that ticker in the main chart area; clicking a different row replaces the series (setData, not update); the chart never throws on sparse or duplicate-timestamp data"
    requirement: "UI-03"
    verification:
      - kind: unit
        ref: "grep assertions in 01-03-PLAN.md Task 2 (addSeries(LineSeries, chart.remove() in cleanup, setData( present / series.update( absent, Math.floor in timeline accumulation) -- all matched during Task 2 execution"
        status: pass
      - kind: integration
        ref: "npm --prefix frontend run build && npx --prefix frontend tsc --noEmit && bash scripts/smoke.sh"
        status: pass
      - kind: manual
        ref: "Task 3 checkpoint item 7 (clicking several rows draws each ticker's series, switching is clean, no console errors about series ordering)"
        status: pass
    human_judgment: true
    rationale: "Static analysis proves the v5 API is used correctly and setData replaces rather than appends, but whether switching feels clean in a real browser and whether the console stays free of series-ordering errors under live SSE traffic is only observable by running the app -- Task 3 item 7, approved PASS."
  - id: D4
    description: "The whole interface renders in the dark trading-terminal theme: backgrounds #0d1117 (darkest surface, no pure black anywhere) and #1a1a2e, accent yellow #ecad0a, blue #209dd7, purple #753991 on submit controls, muted gray borders"
    requirement: "UI-10"
    verification:
      - kind: unit
        ref: "grep -c -E '#0d1117|#1a1a2e|#ecad0a|#209dd7|#753991' frontend/app/globals.css >= 5; grep -ricE pure-black patterns == 0 -- both matched during Task 1 execution"
        status: pass
      - kind: manual
        ref: "Task 3 checkpoint item 1 (theme colors correct and applied where intended, confirmed live)"
        status: pass
    human_judgment: true
    rationale: "Grep proves the exact hex values are transcribed into globals.css and that no pure-black value exists in the file, but whether those tokens are actually applied to the right elements on screen (panel surfaces, submit button, accent placement) is a rendered-page judgment -- Task 3 item 1, approved PASS."

duration: 47min
completed: 2026-08-23
status: complete
---

# Phase 1 Plan 3: Dark Terminal Theme, Flash, Sparklines & Main Chart Summary

**Dark Bloomberg-style terminal with price-flash animations, per-row sparklines, and a Lightweight Charts main chart — human-verified against all 9 checkpoint items, closing out Phase 1.**

## Performance

- **Duration:** ~47 min across Tasks 1-2 implementation (this plan's automated work); Task 3 was a human-verify checkpoint that paused execution pending live review
- **Tasks:** 3 of 3 (Task 1 and Task 2 `type="auto"`, committed; Task 3 `type="checkpoint:human-verify"`, resolved by human approval)
- **Files modified:** 8 across the two implementation commits (2 new components, 6 modified)

## Accomplishments

- `frontend/app/globals.css`: complete Tailwind v4 `@theme` token set transcribing the exact hex values from `planning/PLAN.md` §2 — `#0d1117` (terminal background, the darkest surface, no pure black anywhere in the file), `#1a1a2e` (panel), `#ecad0a` (yellow), `#209dd7` (blue), `#753991` (purple, submit-only) — plus chosen `--color-up: #3fb950` / `--color-down: #f85149` for contrast, and `flash-up`/`flash-down` keyframes (single 500ms ease-out fade, never looping) wrapped in `@media (prefers-reduced-motion: no-preference)`, with a parallel `(prefers-reduced-motion: reduce)` block that keeps the color tint but drops the animation
- `frontend/components/Sparkline.tsx`: inline SVG, no charting library — zero points renders nothing, one point renders a centered mark, an all-identical series draws a flat line instead of dividing by a zero range, and the rendered width scales to the fill fraction of the capped 120-slot buffer so a fresh ticker's short history reads as short, not as a complete picture
- `frontend/components/WatchlistPanel.tsx`: dressed with price/percent columns (`toFixed(2)`, explicit signed percent), a per-ticker animation counter so a still-animating row can be re-triggered, arrow-glyph + signed-percent direction cues (never color alone), keyboard-selectable rows (`tabIndex`, `onKeyDown` Enter/Space, `aria-selected`), and purple/yellow accent placement per the plan's submit-button convention
- `frontend/hooks/usePriceStream.ts`: added a `timeline` buffer alongside `history` — SSE timestamps floored to whole seconds, with replace-if-equal / drop-if-less-than / append-otherwise dedupe logic, because Lightweight Charts rejects non-ascending or duplicate-second time values and SSE frames arrive faster than one per second
- `frontend/components/PriceChart.tsx`: Lightweight Charts v5 wrapper — `createChart` + `chart.addSeries(LineSeries, {...})` (the v5 API; `addLineSeries()` does not exist in 5.x), chart created once on mount, `series.setData()` (not `update()`) on ticker/points change so switching tickers replaces the series wholesale, `ResizeObserver`-driven resizing, and `chart.remove()` in cleanup so repeated ticker switching cannot leak canvases
- `frontend/app/page.tsx`: composed the terminal layout — watchlist panel left, main chart area filling the remaining width, `selectedTicker` lifted and passed to both `WatchlistPanel` and `PriceChart` via `timeline[selectedTicker] ?? []`
- `lightweight-charts` installed at `^5.2.1` (resolved `5.2.1`), matching the version already cleared by the Plan 01-01 npm-legitimacy checkpoint
- Both automated gates passed before the checkpoint: `npm --prefix frontend run build` (exit 0), `npx --prefix frontend tsc --noEmit` (exit 0), `bash scripts/smoke.sh` (all assertions pass), full backend suite (124 passed, untouched by this plan)
- Task 3's human-verify checkpoint walked all 9 items against the live running terminal at `http://localhost:8000` and returned **all 9 PASS** (see Checkpoint Resolution below)

## Task Commits

Each task was committed atomically:

1. **Task 1: Dark terminal theme, price flash, and per-row sparklines** — `cbcff9d` (feat)
2. **Task 2: Main price chart for the selected ticker** — `68eecdb` (feat)
3. **Task 3: Visual verification of the trading terminal** — checkpoint, no code commit; resolved by human approval (see below)

**Plan metadata:** committed alongside this SUMMARY (see final metadata commit)

## Files Created/Modified

- `frontend/app/globals.css` — full `@theme` token set, `flash-up`/`flash-down` keyframes, reduced-motion handling
- `frontend/app/layout.tsx` — `<html className="dark">`, terminal-background `<body>`, `theme-color` meta matching `#0d1117`
- `frontend/components/Sparkline.tsx` — new, inline SVG per-row sparkline
- `frontend/components/PriceChart.tsx` — new, Lightweight Charts v5 wrapper
- `frontend/components/WatchlistPanel.tsx` — flash animation, sparkline column, keyboard-selectable rows, direction cues
- `frontend/hooks/usePriceStream.ts` — added `timeline` buffer
- `frontend/app/page.tsx` — terminal layout composition, `PriceChart` wiring
- `frontend/package.json`, `frontend/package-lock.json` — `lightweight-charts ^5.2.1` dependency

## Checkpoint Resolution

Task 3 (`type="checkpoint:human-verify"`, `gate="blocking"`) required visual/functional verification of the running terminal that no automated grep or build check could settle — perceptual judgments about flash timing, color independence, and rendered chart behavior under live SSE traffic. The human reviewed the running app at `http://localhost:8000` (via `bash scripts/dev.sh`) and returned **"approved"** with all 9 items passing:

| # | Item | Requirement | Result |
|---|------|-------------|--------|
| 1 | Theme | UI-10 | PASS — `#0d1117` background, `#1a1a2e` panels, muted gray borders, purple/yellow/blue accents correct |
| 2 | Streaming | WATCH-04 | PASS — all 10 tickers updating ~2x/sec |
| 3 | Flash | UI-02 | PASS — green/red tint fading ~500ms, reads as calm shimmer, not a strobe |
| 4 | Reduced motion | UI-02 | PASS — color change shows without fade animation when OS reduced-motion is enabled |
| 5 | Color independence | UI-01 | PASS — direction readable from arrow + signed % alone |
| 6 | Sparklines | UI-01 | PASS — progressive fill, new ticker starts short |
| 7 | Chart | UI-03 | PASS — clicking rows draws that ticker's series, clean switching, no console errors |
| 8 | Watchlist edit | WATCH-02, WATCH-03 | PASS — add/remove/re-add duplicate message all work inline |
| 9 | Console | — | PASS — clean, no uncaught errors or React key warnings |

This is normal execution flow for a `checkpoint:human-verify` task, not a deviation: the plan's own `<flagged_assumptions>` section explicitly identified the flash-timing perceptual question ("calm shimmer vs. strobe") as un-resolvable by automated tooling and routed it to this checkpoint.

## Decisions Made

- `--color-up: #3fb950` / `--color-down: #f85149` chosen for contrast against `#0d1117` — recorded and re-confirmed by reading `frontend/app/globals.css` directly during this summary pass; values match exactly
- Flash animation wrapped in `@media (prefers-reduced-motion: no-preference)` with a parallel static-tint block for `reduce`, so direction is never lost to motion-sensitive users
- `lightweight-charts` pinned at `^5.2.1`, matching the version already legitimacy-checked in Plan 01-01 — Task 2 re-confirmed the resolved version rather than re-running the checkpoint

## Deviations from Plan

None — plan executed exactly as written across Tasks 1 and 2, and Task 3's checkpoint resolved with a clean "approved" (all 9 items pass) requiring no gap-closure work.

## Issues Encountered

None. No auth gates, no auto-fixes required in this plan's scope.

## User Setup Required

None — no external service configuration required for this plan.

## Next Phase Readiness

All 3 plans of Phase 1 (Live Market Terminal) are now complete:
- 01-01: walking skeleton (DB, FastAPI entry point, Next.js scaffold, SSE watchlist streaming)
- 01-02: editable watchlist + permanent Massive failover
- 01-03: dark terminal theme, price flash, sparklines, main chart — this plan

The theme tokens (`--color-terminal-*`, `--color-accent-*`, `--color-up`/`--color-down`) and the `PriceChart` Lightweight Charts wrapper conventions established here are the contract Phase 2 (portfolio heatmap, P&L chart, positions table, trade bar) and Phase 3 (AI chat panel) build on directly — no rework anticipated. Phase 1 is ready for orchestrator-level phase verification.

## Self-Check: PASSED

All key files confirmed present in the worktree and tracked in git:
- `frontend/components/Sparkline.tsx` — FOUND
- `frontend/components/PriceChart.tsx` — FOUND
- `frontend/app/globals.css` — FOUND, token values confirmed matching this SUMMARY by direct read
- `frontend/package.json` — FOUND, `"lightweight-charts": "^5.2.1"` confirmed present

Both task commits confirmed present in `git log --oneline`: `cbcff9d` (Task 1), `68eecdb` (Task 2).

---
*Phase: 01-live-market-terminal*
*Completed: 2026-08-23*
