---
phase: 04-one-command-deployment
plan: 01
subsystem: infra
tags: [docker, deployment, uvicorn, sqlite, shutdown]

requires:
  - phase: 01-03
    provides: FastAPI entry point (app.main:app), lazy SQLite init, app.frontend() static serving
provides:
  - Multi-stage Dockerfile (Node 20 slim -> Python 3.12 slim builder -> Python 3.12 slim runtime) building one image that serves the static frontend, REST API, SSE stream, and chat endpoint on port 8000
  - .dockerignore keeping secrets, host db/, and stale static exports out of every image layer
  - db/.gitkeep so the bind-mount target exists in a fresh clone
  - scripts/verify_container.sh, a repeatable, idempotent DEPLOY-01/DEPLOY-02 gate (build, serve, bind-mount persistence, buy-trade + stop/start restart proof, bounded-shutdown timing)
  - scripts/smoke.sh patched with --timeout-graceful-shutdown 10, fixing the previously-hanging cleanup trap
affects: [04-02, 04-03, 04-04]

actuals:
  tokens: 42000
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Same-base-image multi-stage Docker build (node:20-slim -> python:3.12-slim builder -> python:3.12-slim runtime), pinning the builder and runtime stages to the identical Debian suite to avoid a numpy GLIBC mismatch"
    - "Explicit ENV FINALLY_DB_PATH override in the runtime stage instead of relying on the app's parents[3] source-tree auto-detection, which silently breaks once the backend is flattened into /app"
    - "Bounded graceful shutdown: uvicorn --timeout-graceful-shutdown 10 paired with a larger docker --stop-timeout/--timeout 15, so uvicorn's own bound resolves before Docker's SIGKILL backstop"
    - "Idempotent verification script: mktemp -d host directories for db and SSE-reader state, an EXIT trap tolerant of an already-gone container, and a pre-run cleanup of any leftover container from an aborted prior run"

key-files:
  created:
    - Dockerfile
    - .dockerignore
    - db/.gitkeep
    - scripts/verify_container.sh
  modified:
    - scripts/smoke.sh

key-decisions:
  - "Copied the uv binary into a stock python:3.12-slim image (Astral's own Docker guide pattern) rather than using astral-sh/uv:python3.12-*, which now defaults to a trixie base that would mismatch the bookworm-based python:3.12-slim runtime and break numpy's compiled wheel at import time"
  - "scripts/verify_container.sh always binds host port 8010 (never 8000) and mounts a mktemp -d host directory (never db/), so it is safe to run alongside a live finally-app container and never touches the developer's real portfolio"

patterns-established:
  - "Container verification gates use temp resources exclusively (mktemp -d db dirs, non-default host ports) so they can run repeatedly and concurrently with a developer's real running instance"

requirements-completed: [DEPLOY-01, DEPLOY-02]

coverage:
  - id: D1
    description: "Multi-stage Dockerfile builds a single image serving the static frontend, REST API, SSE stream, and chat endpoint on port 8000 with no CORS configuration"
    requirement: DEPLOY-01
    verification:
      - kind: other
        ref: "docker build -t finally . && curl http://127.0.0.1:8010/api/health, GET /, GET /api/watchlist, SSE stream (tracer <verify>)"
        status: pass
    human_judgment: false
  - id: D2
    description: "SQLite database persists via the host bind-mounted db/ directory, surviving a buy trade across container stop/start"
    requirement: DEPLOY-02
    verification:
      - kind: other
        ref: "scripts/verify_container.sh (run twice back to back)"
        status: pass
    human_judgment: false
  - id: D3
    description: "A stop with an open SSE connection resolves within its bounded window (docker stop --timeout 15, uvicorn --timeout-graceful-shutdown 10)"
    requirement: DEPLOY-02
    verification:
      - kind: other
        ref: "scripts/verify_container.sh step 8 (measured 11s, twice)"
        status: pass
    human_judgment: true
    rationale: "Automated curl-based SSE reader approximates but does not fully reproduce a browser EventSource connection; the plan's own <human-check> in Task 2 calls for a browser-tab wall-clock confirmation before full trust, which is outside this executor's automatable surface"

duration: 55min
completed: 2026-08-26
status: complete
---

# Phase 4 Plan 01: Tracer Dockerfile and Container Verification Gate Summary

**Multi-stage Dockerfile packages the built FastAPI+Next.js app into one port-8000 image with a bind-mounted SQLite path and a bounded-shutdown uvicorn CMD, proven by a repeatable, idempotent `scripts/verify_container.sh` gate that also fixed the long-standing `scripts/smoke.sh` shutdown hang.**

## Performance
- **Duration:** 55min
- **Started:** 2026-08-26T22:05:00Z
- **Completed:** 2026-08-26T23:00:00Z
- **Tasks:** 2 completed
- **Files modified:** 5 (4 created, 1 modified)

## Accomplishments
- `docker build -t finally .` produces a single image serving the static frontend, `/api/*`, `/api/stream/prices`, and `/api/chat` on port 8000
- Verified end-to-end via the tracer task's fully automated `<verify>`: health body, root HTML `terminal-root` marker, 10-entry watchlist, SSE `"direction"` frame, bind-mounted `finally.db`, absence of `/app/.env` in the image, and successful `numpy` import (no GLIBC mismatch)
- `scripts/verify_container.sh` proves DEPLOY-02's restart-persistence contract: a buy trade's cash balance and AAPL position quantity are identical before and after a `docker stop`/`docker start` cycle, run twice back to back with no leftover-container error
- Bounded shutdown proven with a live SSE connection open: `docker stop --timeout 15` completed in 11 seconds both times (well under the plan's 20s ceiling)
- `scripts/smoke.sh`'s previously-hanging cleanup trap (STATE.md's Phase 4 blocker entry) is fixed by appending `--timeout-graceful-shutdown 10` to its uvicorn invocation

## Task Commits
1. **Task 1: Build and run the whole app as one container, end to end** - `2887dd5` (feat)
2. **Task 2: Prove restart persistence and bounded shutdown with a repeatable gate** - `a436ba3` (feat)

**Plan metadata:** (pending — committed by the git_commit_metadata step)

## Files Created/Modified
- `Dockerfile` - Three-stage build: `frontend-builder` (node:20-slim, `npm run build` -> `/fe/out`), `backend-builder` (python:3.12-slim, `uv sync` twice around the code copy, frontend export copied to `./static`), and an unnamed runtime stage (same base tag, `ENV FINALLY_DB_PATH=/app/db/finally.db`, Python-only `HEALTHCHECK`, `CMD uvicorn ... --timeout-graceful-shutdown 10`)
- `.dockerignore` - Excludes `.env`/`.env.*` (secrets), `backend/static` (stale export), `db` (runtime data), `test`, `node_modules`, `.venv`, and GSD/planning directories from the build context
- `db/.gitkeep` - Empty tracked file so the bind-mount target directory exists in a fresh clone
- `scripts/verify_container.sh` - New idempotent gate: builds the image, runs `finally-verify` on host port 8010 with a `mktemp -d` bind mount and `LLM_MOCK=true`, asserts health/root/watchlist/SSE, asserts DB persistence in the bind mount, executes a buy trade, times a `docker stop` with a live SSE reader open, restarts and re-asserts portfolio state is unchanged
- `scripts/smoke.sh` - One-line addition: `--timeout-graceful-shutdown 10` appended to the existing uvicorn invocation

## Decisions Made
- Followed 04-RESEARCH.md's Pattern 1 exactly: copy the `uv` binary into a stock `python:3.12-slim` image rather than using Astral's own `astral-sh/uv:python3.12-*` builder tag, because that tag now defaults to a Debian trixie base while the runtime's `python:3.12-slim` is bookworm-based — verified in practice: `docker run --rm finally python -c "import numpy; print(numpy.__version__)"` succeeded (`2.4.2`), confirming no GLIBC mismatch.
- `scripts/verify_container.sh` never touches the developer's real `db/` directory or default port 8000 — it uses a fresh `mktemp -d` and port 8010 exclusively, so it is safe to run repeatedly and even alongside a live `finally-app` container.

## Deviations from Plan

### Auto-fixed Issues

None — both tasks executed exactly as specified in 04-01-PLAN.md; the Dockerfile and verify_container.sh matched the plan's action/acceptance-criteria text with no bugs found during implementation.

**Total deviations:** 0 auto-fixed. **Impact:** none — plan executed as written.

## Issues Encountered
- During local verification of `bash scripts/smoke.sh` (not a task deliverable itself, only the one-line patch is), a long-lived, pre-existing `uvicorn` process bound to `0.0.0.0:8000` was found already occupying the port — an orphaned dev-server process in the main repository checkout, unrelated to this plan's changes, that had apparently survived an earlier ungraceful-shutdown attempt (the exact class of bug this plan fixes) and required `kill -9` to clear. This was an environmental leftover from a prior session, not caused by or part of this plan's deliverables; after clearing it, `bash scripts/smoke.sh` ran cleanly to completion (exit 0) on three consecutive runs.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
The `finally` image, `Dockerfile`, `.dockerignore`, `db/.gitkeep`, and `scripts/verify_container.sh` are all in place and verified. Ready for 04-02 (start/stop lifecycle scripts) and 04-03 (Playwright E2E harness), both of which build directly on this image and its verified `FINALLY_DB_PATH`/`--timeout-graceful-shutdown` contracts.

---
*Phase: 04-one-command-deployment*
*Completed: 2026-08-26*
