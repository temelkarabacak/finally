# Phase 4: One-Command Deployment - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-26
**Phase:** 4-One-Command Deployment
**Areas discussed:** Database volume strategy

---

## Which areas to discuss (initial selection)

| Option | Description | Selected |
|--------|-------------|----------|
| Database volume strategy | PLAN.md is internally inconsistent between a bind-mounted host folder (§4) and a named Docker volume (§11 example) — need to pick one | ✓ |
| Container shutdown reliability | Known SSE-vs-SIGTERM hang risk already logged in STATE.md for scripts/smoke.sh | |
| E2E test data isolation | Should Playwright run against a throwaway DB volume vs. reusing the dev volume | |
| Startup experience | Auto-open browser by default? Missing OPENROUTER_API_KEY at startup — fail fast or start anyway? | |

**User's choice:** Database volume strategy only.

---

## Database volume strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Bind mount ./db (Recommended) | Matches PLAN.md §4 exactly: db/finally.db sits in the project folder, gitignored, inspectable without Docker CLI | ✓ |
| Named volume (finally-data) | Matches PLAN.md §11's literal example command; Docker-managed and idiomatic but opaque to the student | |

**User's choice:** Bind mount ./db (Recommended)
**Notes:** Confirmed `db/finally.db` is already gitignored and `git status` on `db/` is clean, so no repo cleanup is needed. The existing `FINALLY_DB_PATH` env override in `backend/app/db/connection.py` already supports this without backend changes.

**Follow-up check:** "More questions about Database volume strategy, or move to context write-up?" → **I'm ready for context**. No other areas were selected for discussion.

---

## Claude's Discretion

The three unselected gray areas above were not discussed in depth, but were surfaced with enough context to guide implementation without re-asking the user:
- **Container shutdown reliability** — design `stop_mac.sh`/`stop_windows.ps1` and E2E teardown against the known SSE-vs-SIGTERM hang risk (bounded graceful-shutdown timeout before a forceful stop).
- **E2E test data isolation** — default to an ephemeral/isolated DB volume for the Playwright suite rather than reusing the dev volume, unless research finds a reason not to.
- **Startup experience** — match PLAN.md's literal wording: browser auto-open is best-effort/optional, and a missing `OPENROUTER_API_KEY` should not block startup (chat simply errors when used; prices and trading work without it).

## Deferred Ideas

None — discussion stayed within phase scope. Terraform/cloud deployment remains explicitly out of scope per PLAN.md §11 and PROJECT.md.
