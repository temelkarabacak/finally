# Deferred Items — Phase 02

Out-of-scope discoveries logged during execution, per the executor's scope-boundary rule
(only auto-fix issues directly caused by the current task's changes).

## Plan 02-02, Task 3

- **Status:** acknowledged
- **Acknowledged at:** 2026-08-27 (v1.0 milestone close) — non-blocking lint debt, tracked in
  `.planning/STATE.md` Deferred Items and `.planning/v1.0-MILESTONE-AUDIT.md` tech debt list.
- **`npm run lint` reports 4 `react-hooks/set-state-in-effect` errors, not the 2 recorded in
  `.planning/STATE.md`.** The 2 documented errors are `WatchlistPanel.tsx:60,77` (Phase 1,
  already accepted as non-blocking). Two additional errors of the same category —
  `TradeBar.tsx:28` and `usePortfolio.ts:155` (the pre-existing `useEffect(() => { refresh(); },
  [refresh])` mount-fetch pattern) — were introduced by Plan 02-01, which verified with
  `npm run build` + `tsc --noEmit` only and did not run `npm run lint`, so these went
  undetected until Plan 02-02's Task 3 verification ran `npm run lint` for the first time this
  phase. Confirmed via `git show HEAD:frontend/hooks/usePortfolio.ts` and `git log` that both
  lines predate any Plan 02-02 edit — Plan 02-02 added no new instances of this pattern.
  Out of scope to fix here: `TradeBar.tsx` is not in this plan's `files_modified` list, and
  restructuring the mount-fetch pattern in `usePortfolio.ts` to satisfy a stricter lint rule is
  an architectural change (Rule 4) better handled as a dedicated pass across all four instances
  at once, not a one-off fix buried in this task. Recommend a follow-up task/phase note to
  address all 4 `react-hooks/set-state-in-effect` errors together.
