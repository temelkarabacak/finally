# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — MVP

**Shipped:** 2026-08-27
**Phases:** 4 | **Plans:** 15 | **Sessions:** several (spanning 2026-08-23 to 2026-08-27)

### What Was Built
- A live-streaming trading terminal: FastAPI backend, six-table SQLite schema (lazy-init), Next.js dark-terminal frontend, watchlist CRUD, SSE price streaming with permanent Massive→simulator failover (Phase 1).
- Full portfolio trading: market-order buy/sell with fractional shares, positions table, P&L-colored heatmap, and a 30s snapshot recorder feeding a P&L history chart (Phase 2).
- An AI copilot (LiteLLM/OpenRouter/Cerebras) that reads live portfolio context and auto-executes trades/watchlist changes through the same validated code paths as manual actions, with mock-mode for offline tests (Phase 3).
- Single-container Docker deployment with idempotent start/stop scripts (macOS/Linux + Windows) and a 6-scenario Playwright E2E suite proven against the real production image (Phase 4).

### What Worked
- **Vertical MVP phase slicing** avoided half-finished layers on a schema where DB/portfolio/chat all touch the same tables — each phase shipped a complete, demoable user capability rather than an isolated technical layer.
- **Reuse-by-construction for the AI copilot**: Phase 3's chat executor called the exact same `execute_trade()` and watchlist helpers the manual UI used, rather than reimplementing trade/watchlist logic — this made auto-executed AI actions trustworthy by construction and the integration-checker found zero orphaned wiring across all 4 phases at milestone close.
- **Blocking-human package-legitimacy gates** caught real signal, not just noise: `recharts`, the 9 packages in Phase 3 (litellm, pydantic, vitest, etc.), and `@playwright/test` were all flagged `[SUS]` by automated recency heuristics but confirmed legitimate by a human checking download counts and canonical GitHub orgs before install — no wasted installs, no missed problems.
- **Live re-verification over trusting SUMMARY claims**: every phase's VERIFICATION.md independently re-ran the test suites, re-executed live smoke/E2E scripts, and re-read diffs for code-review fixes rather than trusting prior narrative — this caught things a document-only audit would have missed (e.g., confirming the CR-01 chat-history-duplication fix by capturing the actual `messages` kwarg in a monkeypatched call).
- **UAT closed every human-verification gap**: all 12 human-verification items raised across the 4 phases (1 in Phase 2, 2 in Phase 3, 2 in Phase 4 — some overlapping/re-tested) were subsequently resolved with 0 issues via recorded UAT sessions, so no phase closed with an open human-confirmation gap.

### What Was Inefficient
- **Lint wasn't part of the acceptance gate early on.** Phase 1 and Phase 2's initial plans verified with `npm run build` + `tsc --noEmit` only; `npm run lint` wasn't run until Phase 2's Task 3, by which point 2 additional `react-hooks/set-state-in-effect` errors (`TradeBar.tsx`, `usePortfolio.ts`) had already landed on top of Phase 1's 2. All 4 are still open as accepted tech debt at v1.0 close. Running lint as a standard gate from Phase 1 onward would have caught these at the point of introduction instead of accumulating them.
- **STATE.md's blocker count silently drifted from reality.** It recorded "2 lint errors" through Phase 4 close even after Phase 2 introduced 2 more — the milestone's own pre-close audit (`audit-open`) is what caught the discrepancy, not an earlier phase gate. A per-phase reconciliation step (or just trusting `npm run lint`'s live count over a cached STATE.md tally) would have avoided a stale number persisting across two phases.
- **One phase (Phase 2) needed a gap-closure wave.** UAT caught G-02-4 (P&L chart never resolved its cold-start empty state without a trade) after the phase's initial plans were "done" — root cause was a mount-only `useEffect` with no polling interval. Wave 4 fixed it, but this is exactly the class of bug a live ~90-second browser observation (not just an integration-test-level data-timing check) would catch earlier if built into the plan's own acceptance criteria rather than discovered in UAT.

### Patterns Established
- **Reuse validated backend functions from the LLM executor rather than reimplementing them** — the pattern this milestone leaned on hardest for trustworthy auto-execution, worth carrying into any future AI-driven-action phase.
- **`refreshAll` combining hook**: when more than one piece of frontend state (portfolio + watchlist) must refresh together after a shared trigger (a trade or a chat action), expose one combined refresh callback from the page rather than wiring each trigger to each hook independently — avoids the class of bug CR-02 was (chat-executed watchlist changes not appearing without a reload).
- **Package-legitimacy checkpoint as a blocking-human gate before any `npm install`/`uv add`** for automated-heuristic-flagged packages — ran 3 times this milestone (Phase 2, 3, 4), zero false negatives caught downstream.

### Key Lessons
1. Add `npm run lint` (or the project's equivalent style gate) to every frontend plan's acceptance criteria from Phase 1 onward, not just when a later phase's Task 3 happens to run it — debt otherwise silently compounds across phases.
2. When a UAT item is a real-wall-clock state transition (e.g., "resolves within ~70s with no user action"), write that exact scenario into the plan's own acceptance criteria up front rather than relying on UAT to discover it after the phase is marked done.
3. Treat STATE.md's Blockers/Concerns tallies as a snapshot, not a ledger — re-verify counts (e.g., via a live `npm run lint` run) at milestone close rather than trusting a number carried forward from an earlier phase.

### Cost Observations
- Sessions: several across 2026-08-23 to 2026-08-27 (4 days wall-clock for the whole remaining platform, 152 commits from `feat(01-01)` to `feat(04-04)` plus fixes/docs/security follow-ups).
- Notable: every phase's code review caught at least one real, fixed bug before verification (CR-01/CR-02 in Phase 3, CR-01 in Phase 4), and every phase's security review closed 100% of its registered ASVS L1 threats (16/22, 18/23, 8/10 mitigated; remainder explicitly accepted) — the review-then-verify pipeline consistently found and closed real issues rather than rubber-stamping.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | several | 4 | First milestone — vertical MVP slicing, blocking-human package gates, and live re-verification (not SUMMARY-trusting) established as the baseline process |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 | 243+ backend (pytest), 31 frontend (Vitest), 6 E2E scenarios (Playwright) | Backend ~99% on core modules (per-phase VERIFICATION.md) | 0 — every new dependency (recharts, litellm, pydantic, vitest, @playwright/test, etc.) passed a human legitimacy check before install |

### Top Lessons (Verified Across Milestones)

1. Lint/style gates belong in every plan's acceptance criteria from the first phase, not introduced partway through — v1.0 saw debt accumulate for exactly this reason.
2. Live re-verification (re-running tests, re-reading diffs, live smoke/E2E runs) at each phase's VERIFICATION.md catches real gaps that trusting SUMMARY.md narrative would miss.
