---
phase: 260825-ddv
plan: 01
subsystem: ui
tags: [nextjs, lightweight-charts, intl-numberformat, formatting]

requires: []
provides:
  - Shared `formatCurrency` helper in `frontend/lib/format.ts` (en-US, 2 decimals, thousands separators)
  - P&L chart price scale and crosshair render currency with thousands separators via Lightweight Charts `localization.priceFormatter`
  - Header Total Value and Cash readouts render currency with thousands separators
affects: [frontend-ui, portfolio-header, pnl-chart]

actuals:
  tokens: 750
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Shared formatting helpers live in frontend/lib/ (new directory), imported via the @/lib/* path alias"

key-files:
  created:
    - frontend/lib/format.ts
  modified:
    - frontend/components/PnlChart.tsx
    - frontend/app/page.tsx
    - .gitignore

key-decisions:
  - "Pinned Intl.NumberFormat locale to en-US rather than the viewer's browser locale, so rendered separators are deterministic across browsers, the static export, and CI verification"
  - "Fixed a pre-existing root .gitignore bug (unanchored `lib/` pattern from the Python boilerplate template) that was silently excluding frontend/lib/ — anchored to /lib/ so it only matches the top-level Python build artifact it was meant for"

requirements-completed: [QUICK-260825-ddv]

coverage:
  - id: D1
    description: "P&L chart price-scale tick labels and crosshair label render thousands-separated currency (e.g. 10,000.00)"
    requirement: "QUICK-260825-ddv"
    verification:
      - kind: unit
        ref: "node -e Intl.NumberFormat contract assertion (thousands/sub-thousand/millions/negative cases)"
        status: pass
      - kind: unit
        ref: "grep wiring check: PnlChart.tsx passes formatCurrency as localization.priceFormatter"
        status: pass
      - kind: manual_procedural
        ref: "Load app, confirm P&L axis/crosshair show comma-separated values once >=2 snapshots exist"
        status: unknown
    human_judgment: true
    rationale: "Plan's <verify> specifies a human-check step (visual confirmation in the running app with live chart data) that this executor did not run — automated build and contract checks pass, but the rendered chart appearance was not visually inspected."
  - id: D2
    description: "Header Total Value and Cash readouts render thousands-separated currency"
    requirement: "QUICK-260825-ddv"
    verification:
      - kind: unit
        ref: "grep wiring check: formatCurrency(portfolio.*) appears twice in app/page.tsx"
        status: pass
      - kind: integration
        ref: "npm --prefix frontend run build (Next.js static export incl. TypeScript check)"
        status: pass
      - kind: manual_procedural
        ref: "Load app, confirm header reads 'Total Value 10,000.00' / 'Cash 10,000.00' on a fresh portfolio"
        status: unknown
    human_judgment: true
    rationale: "Plan's <verify> specifies a human-check step (visual confirmation in the running app) that this executor did not run."

duration: 25min
completed: 2026-08-25
status: complete
---

# Quick Task 260825-ddv: Format P&L Chart Currency Values Summary

**Added a pinned-locale `formatCurrency` helper and wired it into the P&L chart's Lightweight Charts price scale/crosshair and the header's Total Value/Cash readouts, so four- and five-figure portfolio values now render with thousands separators (e.g. `10,000.00`).**

## Performance

- **Duration:** 25 min
- **Started:** 2026-08-25T07:20:00Z (approx.)
- **Completed:** 2026-08-25T07:45:15Z
- **Tasks:** 2
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments
- New `frontend/lib/format.ts` exports `formatCurrency(value: number): string`, backed by a module-level `en-US` `Intl.NumberFormat` (2 decimal places, no currency symbol)
- `PnlChart.tsx`'s `createChart` options now include `localization: { priceFormatter: formatCurrency }`, which Lightweight Charts applies to both the right price-scale tick labels and the crosshair label
- `app/page.tsx`'s header `Total Value` and `Cash` spans now call `formatCurrency` instead of bare `.toFixed(2)`
- Fixed a pre-existing bug in the root `.gitignore` that was silently excluding `frontend/lib/` from version control

## Task Commits

Each task was committed atomically:

1. **Task 1: Shared currency formatter wired end-to-end into the P&L chart price scale** - `07b4949` (feat)
2. **Task 2: Apply the formatter to the header Total Value and Cash readouts** - `698a386` (feat)

**Plan metadata:** committed separately by the orchestrator (docs commit not made by this executor per constraints)

## Files Created/Modified
- `frontend/lib/format.ts` - New shared currency formatter (`formatCurrency`), pinned `en-US` locale, 2 decimal places
- `frontend/components/PnlChart.tsx` - Added `formatCurrency` import and `localization.priceFormatter` chart option
- `frontend/app/page.tsx` - Routed header `Total Value` and `Cash` readouts through `formatCurrency`
- `.gitignore` - Anchored the Python-boilerplate `lib/` ignore pattern to `/lib/` (root only) so it no longer shadows `frontend/lib/`

## Decisions Made
- Pinned the `Intl.NumberFormat` locale to `en-US` (not `undefined`/browser-default) so formatting is deterministic across browsers, the static export, and the `node -e` verification command — matches the plan's `<interface_notes>`.
- No currency symbol prepended, matching the existing bare-number rendering convention in both the header and chart axis.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Root `.gitignore`'s unanchored `lib/` pattern was excluding `frontend/lib/`**
- **Found during:** Task 1 (creating `frontend/lib/format.ts`)
- **Issue:** The repo's root `.gitignore` carries the standard Python-project boilerplate, which includes an unanchored `lib/` entry (intended to ignore a Python `build/lib/`-style packaging artifact). Because it isn't anchored with a leading `/`, git's ignore matching applies it to any directory named `lib` anywhere in the tree, including the newly created `frontend/lib/`. `git status` showed no new file after creating `frontend/lib/format.ts`, and `git check-ignore -v` confirmed the match at `.gitignore:17:lib/`.
- **Fix:** Changed the `.gitignore` entry from `lib/` to `/lib/`, anchoring it to the repository root so it still ignores a top-level Python build artifact (which doesn't currently exist — the Python backend lives under `backend/`) without shadowing `frontend/lib/`.
- **Files modified:** `.gitignore`
- **Verification:** `git check-ignore -v frontend/lib/format.ts` returned exit code 1 (not ignored) after the fix; `git status --short` showed `frontend/lib/format.ts` as untracked/addable.
- **Committed in:** `07b4949` (part of Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary to satisfy the plan's must-have artifact (`frontend/lib/format.ts` committed to version control). No scope creep — the fix is a one-character anchor change scoped to the exact pattern that was blocking the task, and does not remove Python's ability to ignore a genuine top-level `lib/` build directory if one is ever created.

## Issues Encountered
- `npm --prefix frontend run build` initially failed with `next: not found` because this worktree had no `frontend/node_modules/` installed. Ran `npm --prefix frontend install` (existing `package.json`/`package-lock.json`, no new dependency added) to materialize the already-declared dependencies, then the build succeeded. Not logged as a plan deviation since it materializes existing, already-committed dependencies rather than introducing new functionality or packages.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Both automated verification layers pass: the `Intl.NumberFormat` contract test (thousands, sub-thousand, millions, and negative cases) and the full Next.js static export build (`npm --prefix frontend run build`), which also type-checks the new `@/lib/format` import in both consumers.
- `git diff --stat` confirms exactly the expected scope: `frontend/lib/format.ts` (new), `frontend/components/PnlChart.tsx`, `frontend/app/page.tsx`, plus the necessary `.gitignore` fix.
- **Outstanding:** the plan's `<human-check>` verification step (visually loading the running app to confirm the header and P&L chart render `10,000.00`-style values, and that no other UI surface changed) was not performed by this executor — no live backend/frontend stack was launched. Recommend a quick manual spot-check before considering this fully closed, though the change is narrowly scoped and both automated checks strongly support correctness.

---
*Phase: 260825-ddv*
*Completed: 2026-08-25*

## Self-Check: PASSED

- FOUND: `frontend/lib/format.ts`
- FOUND: `frontend/components/PnlChart.tsx`
- FOUND: `frontend/app/page.tsx`
- FOUND: `.planning/quick/260825-ddv-format-p-l-chart-currency-values-with-th/260825-ddv-SUMMARY.md`
- FOUND commit: `07b4949` (Task 1)
- FOUND commit: `698a386` (Task 2)
