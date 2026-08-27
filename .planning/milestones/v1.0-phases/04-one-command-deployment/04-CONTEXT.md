# Phase 4: One-Command Deployment - Context

**Gathered:** 2026-08-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Package the completed app (FastAPI backend, Next.js static export, SQLite) into a single Docker container that serves everything on port 8000 with no CORS configuration. A user builds and runs the whole verified app with one script (`start_mac.sh` / `start_windows.ps1`), stopping it never destroys their portfolio data, and restarting it restores cash, positions, trades, and chat history from the volume-mounted SQLite file. A Playwright E2E suite (`test/`, `LLM_MOCK=true`) runs against the built container and covers fresh start, watchlist add/remove, buy/sell, visualizations, AI chat with an inline trade, and SSE reconnection. This is the last phase — the milestone is not complete without it.

</domain>

<decisions>
## Implementation Decisions

### Database volume strategy
- **D-01:** SQLite persistence uses a **bind mount of the project's `./db` folder** to `/app/db` in the container (`docker run -v $(pwd)/db:/app/db ...`), not a named Docker volume. This resolves an internal inconsistency in `planning/PLAN.md` — §4's directory structure describes `db/` as a host folder holding `finally.db` (gitignored, already the case today), while §11's example command uses a named volume (`finally-data:/app/db`). The bind mount wins: it matches §4 exactly, and it means a student can see, inspect, back up, or delete `db/finally.db` directly without touching the Docker CLI. — **Reversibility:** reversible — switching to a named volume later is a one-line change to the `docker run`/compose invocation; no data format changes.
- The existing `FINALLY_DB_PATH` env var override (`backend/app/db/connection.py:27`) and lazy-init behavior (create + seed if missing/empty) already support this without backend changes — the container just needs the mount, not new backend logic.
- `db/finally.db` is already gitignored (`.gitignore:214-215`) and `git status` on `db/` is clean — no repo cleanup needed before this phase.

### Claude's Discretion
Three other candidate gray areas were surfaced during discussion but not selected by the user — Claude's judgment applies, informed by PLAN.md, ROADMAP.md's phase notes, and the codebase evidence below:
- **Container shutdown reliability** — `scripts/smoke.sh`'s cleanup trap (SIGTERM to uvicorn) has hung twice already (STATE.md Blockers/Concerns, Phase 4 entry) because long-lived SSE connections can keep the server alive past SIGTERM. `stop_mac.sh`/`stop_windows.ps1` and the E2E harness's teardown need a shutdown strategy that doesn't hang — e.g. a bounded graceful-shutdown timeout before a forceful `docker stop`/`kill`. Left to research/planning to design against this known failure mode.
- **E2E test data isolation** — whether the Playwright suite runs against a throwaway/ephemeral DB volume (fresh every run, never touches `db/finally.db`) or could reuse the dev volume. Given D-01 makes the dev DB a plain host file the user can see, isolating E2E runs (e.g., a separate volume/path in `test/docker-compose.test.yml`) is the safer default and should be assumed unless research surfaces a reason not to.
- **Startup experience details** — whether `start_mac.sh` auto-opens the browser by default (PLAN.md §11 says "optionally") and what happens if `OPENROUTER_API_KEY` is missing from `.env` at container start (fail fast vs. start with chat erroring on use). Neither was raised as something the user has a strong opinion on; default to matching PLAN.md's literal wording (open browser is optional/best-effort, don't block startup on a missing LLM key since the rest of the app — prices, trading — works fine without it).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Master specification
- `planning/PLAN.md` §4 (Directory Structure — `db/` bind-mount description, now the authoritative one per D-01), §11 (Docker & Deployment — multi-stage Dockerfile, start/stop scripts, note the volume example there is superseded by D-01), §12 (Testing Strategy — E2E infrastructure: `test/docker-compose.test.yml` pairs app container with a Playwright container to keep browser deps out of the production image) — authoritative spec for this phase

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — DEPLOY-01, DEPLOY-02, DEPLOY-03, TEST-05
- `.planning/ROADMAP.md` Phase 4 section — success criteria and phase notes (multi-stage build layout, E2E infra rationale for why TEST-05 lives here not Phase 3)

### Codebase maps
- `.planning/codebase/CONCERNS.md` — "No Docker Support" and "No Start/Stop Scripts" entries describe exactly what this phase must close
- `.planning/STATE.md` Blockers/Concerns — `[Phase 4]` entry documents the smoke.sh shutdown-hang risk (SSE connections vs. SIGTERM) that container/script shutdown design must account for

### Existing scripts to build on
- `scripts/smoke.sh` — an existing end-to-end boot/health/SSE smoke script (not Docker-based) that already demonstrates: building the frontend static export into `backend/static/`, starting uvicorn with `FINALLY_DB_PATH` pointed at a temp DB, waiting on `/api/health`, and a cleanup trap — useful as a reference pattern for the Dockerfile's build stages and for the exact shutdown-hang failure mode to design around
- `backend/app/db/connection.py:24-27` — `FINALLY_DB_PATH` env override, defaults to `<repo-root>/db/finally.db`
- `backend/app/main.py:31-37` — env-var truthy-check idiom (`LLM_MOCK`), mirrors `MASSIVE_API_KEY` handling in `app/market/factory.py`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/smoke.sh` — frontend-build-then-copy-to-`backend/static/` pattern, `/api/health` polling loop, and a `trap cleanup EXIT` pattern; the Dockerfile's build stages and any new lifecycle scripts should follow the same shape rather than inventing a new one.
- `backend/app/db/connection.py`'s `FINALLY_DB_PATH` override — the container doesn't need new backend code for the bind mount to work; it already defaults to `db/finally.db` relative to repo root.
- `backend/app/main.py`'s `LLM_MOCK` / `MASSIVE_API_KEY` env-var patterns — `.env` is already the single source of config; Docker just needs `--env-file .env`.

### Established Patterns
- Env var truthy idiom: `os.environ.get("X", "").strip().lower() == "true"` — reuse for any new deployment-related flags rather than inventing a different truthiness check.
- `test/` already exists as a directory (currently only stray Playwright/npm cache artifacts, no actual spec files or `package.json` yet) — this phase is the first to populate it with real E2E tests and `docker-compose.test.yml`.

### Integration Points
- New root-level `Dockerfile` — multi-stage: Node 20 slim (build Next.js static export) → Python 3.12 slim (uv sync, copy static export, run uvicorn on 8000).
- New root-level `docker-compose.yml` — PLAN.md §11 frames this as an "optional convenience wrapper"; not required for `DEPLOY-01..03` to be satisfied, whether to include it is planner's call.
- New `scripts/start_mac.sh`, `stop_mac.sh`, `start_windows.ps1`, `stop_windows.ps1` — none exist yet (confirmed via `CONCERNS.md`).
- New `test/docker-compose.test.yml` plus actual Playwright spec files — `test/` currently has no `package.json` or specs, only unrelated cache/report directories from a prior tool run.

</code_context>

<specifics>
## Specific Ideas

No specific visual or behavioral references came up — this phase is infrastructure/deployment, not UI. The one concrete implementation detail pinned down is D-01 (bind mount, not named volume), which directly resolves a contradiction between two sections of PLAN.md.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. Terraform/cloud deployment is already explicitly out of scope per PLAN.md §11 ("stretch goal, not part of the core build") and PROJECT.md's Out of Scope list.

</deferred>

---

*Phase: 4-One-Command Deployment*
*Context gathered: 2026-08-26*
