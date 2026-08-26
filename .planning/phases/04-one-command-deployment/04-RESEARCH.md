# Phase 4: One-Command Deployment - Research

**Researched:** 2026-08-26
**Domain:** Docker packaging (multi-stage builds), graceful process shutdown, containerized E2E testing, cross-platform lifecycle scripting
**Confidence:** MEDIUM-HIGH (all external claims verified against official docs via Context7 or docs.docker.com directly; two claims below are load-bearing in-repo discoveries verified by reading source this session)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01 — Database volume strategy:** SQLite persistence uses a **bind mount of the project's `./db` folder** to `/app/db` in the container (`docker run -v $(pwd)/db:/app/db ...`), not a named Docker volume. This resolves an internal inconsistency in `planning/PLAN.md` — §4's directory structure describes `db/` as a host folder holding `finally.db` (gitignored, already the case today), while §11's example command uses a named volume (`finally-data:/app/db`). The bind mount wins: it matches §4 exactly, and it means a student can see, inspect, back up, or delete `db/finally.db` directly without touching the Docker CLI. Reversibility: reversible.
- The existing `FINALLY_DB_PATH` env var override (`backend/app/db/connection.py:27`) and lazy-init behavior already support this without backend code changes — the container just needs the mount pointed at the right path (see Common Pitfalls — this still requires an explicit `ENV FINALLY_DB_PATH=/app/db/finally.db`, not zero Dockerfile configuration; see below).
- `db/finally.db` is already gitignored — no repo cleanup needed before this phase.

### Claude's Discretion

Three candidate gray areas were surfaced during discussion but left to research/planning judgment:

1. **Container shutdown reliability** — `scripts/smoke.sh`'s cleanup trap (SIGTERM to uvicorn) has hung twice already because long-lived SSE connections can keep the server alive past SIGTERM. `stop_mac.sh`/`stop_windows.ps1` and the E2E harness's teardown need a shutdown strategy that doesn't hang (e.g., a bounded graceful-shutdown timeout before a forceful `docker stop`/`kill`). **Resolved by this research** — see Common Pitfalls Pitfall 1 and Code Examples.
2. **E2E test data isolation** — whether the Playwright suite runs against a throwaway/ephemeral DB volume (fresh every run, never touches `db/finally.db`) or could reuse the dev volume. Given D-01 makes the dev DB a plain host file, isolating E2E runs is the safer default. **Resolved by this research** — use a `tmpfs` mount for the test container's `/app/db`, not the host bind mount.
3. **Startup experience details** — whether `start_mac.sh` auto-opens the browser by default and what happens if `OPENROUTER_API_KEY` is missing at container start. Default to PLAN.md's literal wording: opening the browser is optional/best-effort, and startup must not block on a missing LLM key since prices/trading work without it. **Resolved by this research** — see Code Examples (env-var truthy check already established in `main.py`, no new validation needed at container-start time; chat requests will simply fail at call-time if the key is absent, which is acceptable per PLAN.md and CONCERNS.md's own recommendation being explicitly out of scope for this phase).

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope. Terraform/cloud deployment is explicitly out of scope per PLAN.md §11 and PROJECT.md's Out of Scope list.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEPLOY-01 | Multi-stage Dockerfile builds the Next.js export and Python backend into a single image serving port 8000 | Standard Stack, Code Examples (Dockerfile), Common Pitfalls (glibc mismatch, static/db path resolution) |
| DEPLOY-02 | SQLite database persists via a volume-mounted `db/` directory across container restarts | Common Pitfalls (FINALLY_DB_PATH must be set explicitly), Code Examples |
| DEPLOY-03 | Idempotent start/stop scripts for macOS/Linux and Windows | Architecture Patterns (idempotent script pattern), Code Examples (bash + PowerShell) |
| TEST-05 | Playwright E2E suite (`test/`, `LLM_MOCK=true`) covers fresh start, watchlist add/remove, buy/sell, visualizations, AI chat, and SSE reconnection | Architecture Patterns (docker-compose.test.yml), Don't Hand-Roll (Playwright Docker image), Code Examples |
</phase_requirements>

## Summary

This phase has no new application logic — it packages a complete app (verified working in Phases 1-3) into a Docker image, gives it reliable start/stop lifecycle scripts on two platforms, and stands up a containerized E2E suite. The two biggest risks are not "will Docker work" but **silent correctness failures**: (1) a shutdown that hangs because Uvicorn's graceful-shutdown timeout defaults to unbounded when SSE connections are open — already reproduced twice in this repo — and (2) a Dockerfile that silently writes SQLite to a path that is never actually the bind-mounted volume, because the existing `resolve_db_path()` fallback logic in `connection.py` computes the DB path via `Path(__file__).resolve().parents[3]`, an assumption tied to the exact `<repo-root>/backend/app/db/connection.py` nesting depth that will not hold once the backend is copied into a Docker image layout. Both failure modes are fixable with one line each (a bounded `timeout_graceful_shutdown` on Uvicorn, and an explicit `ENV FINALLY_DB_PATH=/app/db/finally.db`), but neither fails loudly if missed — the app will build, run, and appear to work, and only lose data or hang on the *next* restart/stop.

For the Docker build itself, Astral's official uv Docker guide's "copy the uv binary into a stock `python:3.12-slim` image" pattern (rather than using Astral's own `astral-sh/uv:python3.12-*` image as the builder) is the safer choice here specifically because it keeps the builder and runtime stages on the *same* Debian base (both bookworm, since plain `python:3.12-slim` still defaults to bookworm), avoiding a real glibc-version mismatch that can otherwise break `numpy`'s compiled wheel at import time. For the E2E suite, Playwright's official Docker image (`mcr.microsoft.com/playwright:v<version>-noble`) ships with browsers pre-installed and must be pinned to the exact `@playwright/test` npm version used in `test/package.json`; the app and test containers are paired via `docker-compose.test.yml` using `depends_on: condition: service_healthy` against `/api/health`, with the test container's SQLite mounted on `tmpfs` for isolation and speed.

**Primary recommendation:** Build the Dockerfile using uv's "copy binary into `python:3.12-slim`" pattern with a single flattened `/app` layout for the backend, set `ENV FINALLY_DB_PATH=/app/db/finally.db` explicitly (don't rely on the `parents[3]` auto-detection), set Uvicorn's `--timeout-graceful-shutdown 10`, and give `docker stop` a slightly longer `--time` (e.g. 15s) so Uvicorn's own bounded shutdown resolves first under normal conditions.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Static frontend serving | API / Backend (FastAPI `app.frontend()`) | CDN / Static (image layer) | Single-port constraint means FastAPI itself serves the static export; no separate static-file tier exists in this architecture |
| SQLite persistence | Database / Storage (bind mount) | — | `db/` bind mount is the only persistence tier; no server-based DB per PLAN.md |
| Process lifecycle (start/stop) | Host OS / Docker CLI (scripts) | — | Scripts orchestrate the container from outside; no in-container orchestration needed for a single-container app |
| Graceful shutdown of SSE connections | API / Backend (Uvicorn config) | Host OS (Docker stop timeout) | Uvicorn must bound its own task-cancellation window; Docker's SIGKILL timeout is the backstop, not the primary mechanism |
| E2E test execution | CI / Test tier (separate Playwright container) | API / Backend (app container under test) | Kept out of the production image per PLAN.md §12 — two containers, one compose file, scoped to `test/` |
| Test data isolation | Database / Storage (tmpfs, test-only) | — | Must never touch the dev bind mount; tmpfs on the test compose service is the standard pattern |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `python:3.12-slim` (Debian bookworm) | latest `3.12-slim` tag | Base image for both build and runtime Python stages | Official Docker Hub image; using the *same* tag in both stages avoids the glibc mismatch documented in Common Pitfalls |
| `node:20-slim` | latest `20-slim` tag | Base image for the frontend build stage | Next.js 16.x requires Node 20.9+ [CITED: nextjs.org/docs/app/guides/upgrading/version-16]; matches PLAN.md/CONTEXT.md's explicit "Node 20 slim" instruction |
| `ghcr.io/astral-sh/uv:latest` | latest | Source of the `uv`/`uvx` static binaries, copied (not run from) into the Python builder stage | Official Astral-recommended pattern for injecting uv into a plain Python base image without adopting Astral's own Debian suite [CITED: github.com/astral-sh/uv/blob/main/docs/guides/integration/docker.md] |
| `mcr.microsoft.com/playwright:v<pinned-version>-noble` | must match `@playwright/test` npm version exactly | E2E test runner container with browsers preinstalled | Official Playwright Docker image; keeps browser binaries out of the production image per PLAN.md §12 [CITED: github.com/microsoft/playwright/blob/main/docs/src/docker.md] |
| `@playwright/test` | `^1.62.1` (verify at install time) | Node.js test runner/assertion library for E2E specs | The canonical Playwright test framework; 56.9M weekly downloads, canonical `microsoft/playwright` GitHub org — see Package Legitimacy Audit for its `[SUS]` flag reason (recency, not illegitimacy) |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `uvicorn[standard]` | already pinned `>=0.32.0` in `backend/pyproject.toml` | ASGI server | Already a dependency; this phase adds one CLI/config flag (`timeout_graceful_shutdown`), no version bump needed |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Copying `uv` binary into `python:3.12-slim` | `FROM ghcr.io/astral-sh/uv:python3.12-trixie-slim AS builder` (Astral's own uv+Python image) | Astral's image is trixie (Debian 13)-based by default while the stock `python:3.12-slim` runtime is bookworm-based; mixing the two across build/runtime stages risks a `GLIBC_2.X not found` failure for compiled wheels (numpy is one) unless both stages are pinned to the same suite explicitly. Copying the binary into a single consistent base avoids this entirely. |
| Root-level `docker-compose.yml` "convenience wrapper" (PLAN.md frames as optional) | Plain `docker build`/`docker run` inside the start/stop scripts | A second compose-based lifecycle path for a genuinely single-container app adds redundant surface area without adding capability; recommend the scripts drive `docker build`/`docker run`/`docker stop` directly and skip the root compose file (Claude's discretion, non-binding on the planner) |
| `mcr.microsoft.com/playwright` browsers pre-baked into a custom test image | Installing Playwright + browsers fresh inside a generic `node:20` container on every test run | The official image is purpose-built for this (matches `PLAYWRIGHT_BROWSERS_PATH`), avoids repeated `npx playwright install --with-deps` cost, and is the documented pattern |

**Installation:**
```bash
# Root-level Dockerfile has no separate install step — `docker build .` handles both stages.
# Frontend/backend dependencies are already locked (package-lock.json, uv.lock).

# New: test/ needs its own package.json for Playwright
cd test
npm init -y
npm install --save-dev @playwright/test
```

**Version verification:** Verified this session via `npm view @playwright/test version` → `1.62.1` (registry, 2026-08-26). Confirm again immediately before running `npm install` in the actual implementation, since Playwright ships frequent releases and the Docker image tag must match exactly.

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|--------------|---------|-------------|
| `@playwright/test` | npm | Version `1.62.1` published 2026-07-30 (package itself is Microsoft's flagship test runner, years old; only the *specific version* is recent) | 56,970,888/week | `github.com/microsoft/playwright` | `[SUS]` — reason: `"too-new"` (the checked version's publish date, not the package's overall history) | **Flagged — planner must add a `checkpoint:human-verify` task before `npm install` in `test/`, per protocol.** Given the canonical `microsoft/playwright` repo and ~57M weekly downloads, this is very likely a false positive from the recency heuristic rather than a real supply-chain risk, but the gate still applies as written. |

**Packages removed due to `[SLOP]` verdict:** none.
**Packages flagged as suspicious `[SUS]`:** `@playwright/test` (see above; planner inserts `checkpoint:human-verify` before this install).

*This session's tool output for `@playwright/test` is quoted verbatim above; no other new external packages are introduced by this phase (base Docker images are not npm/PyPI packages and are not subject to this gate, but see Common Pitfalls for their own verification concerns — Debian suite matching).*

## Architecture Patterns

### System Architecture Diagram

```
Host machine
 │
 │  scripts/start_mac.sh  or  scripts/start_windows.ps1
 │  (idempotent: checks for existing image/container before building/running)
 ▼
docker build (multi-stage) ──► docker run -d --name finally-app \
                                  -v $(pwd)/db:/app/db \
                                  -p 8000:8000 --env-file .env \
                                  --stop-timeout 15 finally
                                       │
                                       ▼
                         ┌─────────────────────────────────────┐
                         │ Container (python:3.12-slim runtime) │
                         │                                       │
                         │  Uvicorn (timeout_graceful_shutdown=10)│
                         │   ├── /api/*        FastAPI routes    │
                         │   ├── /api/stream/*  SSE (long-lived) │
                         │   └── /*             app.frontend()   │
                         │        (serves /app/static, built     │
                         │         from frontend/ in build stage)│
                         │                                       │
                         │  FINALLY_DB_PATH=/app/db/finally.db ──┼──► bind mount ──► host ./db/finally.db
                         └─────────────────────────────────────┘
                                       ▲
                                       │ browser: http://localhost:8000
                                       │ (EventSource auto-reconnects on drop)

Separate, test-only path (never touches the above):
 test/docker-compose.test.yml
   ├── service "app": same image, LLM_MOCK=true, tmpfs: /app/db (ephemeral)
   │      healthcheck: GET /api/health
   └── service "playwright": mcr.microsoft.com/playwright:v<pinned>-noble
          depends_on: app: condition: service_healthy
          runs `npx playwright test` against http://app:8000 (compose DNS name)
```

### Recommended Project Structure

```
finally/
├── Dockerfile                    # multi-stage: node builder -> python builder -> python runtime
├── .dockerignore                 # NEW — excludes .env, .git, node_modules, db/, test/ artifacts
├── docker-compose.yml            # SKIP (recommendation) — see Alternatives Considered
├── scripts/
│   ├── start_mac.sh               # idempotent build+run, bind-mounts db/, optional browser open
│   ├── stop_mac.sh                # bounded docker stop, never touches the volume
│   ├── start_windows.ps1          # PowerShell equivalent
│   └── stop_windows.ps1
├── test/
│   ├── package.json               # NEW — @playwright/test devDependency
│   ├── playwright.config.ts       # NEW — baseURL from env, no webServer block (compose starts the app)
│   ├── docker-compose.test.yml    # NEW — app + playwright services
│   └── tests/
│       ├── fresh-start.spec.ts
│       ├── watchlist.spec.ts
│       ├── trading.spec.ts
│       ├── visualizations.spec.ts
│       ├── chat.spec.ts
│       └── sse-reconnect.spec.ts
└── db/
    └── .gitkeep                   # already exists; finally.db is gitignored
```

### Pattern 1: Same-base-image multi-stage Docker build (uv + Next.js static export)

**What:** Two independent builder stages (Node for the static export, Python for the backend venv) feeding a single minimal runtime stage, with the Python builder and runtime stages pinned to the identical Debian suite.
**When to use:** Any project combining a Node build tool with a `uv`-managed Python runtime in one image.
**Example:**
```dockerfile
# Source: https://github.com/astral-sh/uv/blob/main/docs/guides/integration/docker.md (uv+Docker guide, adapted)
#         https://github.com/vercel/next.js/blob/v16.1.6/docs/01-app/02-guides/static-exports.mdx (output: 'export')

# ---- Stage 1: build the Next.js static export ----
FROM node:20-slim AS frontend-builder
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build   # next.config.ts has output:'export' -> produces /fe/out

# ---- Stage 2: build the Python backend venv ----
FROM python:3.12-slim AS backend-builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_PYTHON_DOWNLOADS=0
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project
COPY backend/ .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked
# Copy the frontend build into backend/static, matching scripts/smoke.sh's existing pattern
COPY --from=frontend-builder /fe/out ./static

# ---- Stage 3: minimal runtime (SAME base tag as Stage 2 -- avoids glibc mismatch) ----
FROM python:3.12-slim
WORKDIR /app
COPY --from=backend-builder /app /app
ENV PATH="/app/.venv/bin:$PATH"
# See Common Pitfalls: this MUST be set explicitly; the code's own parents[3]
# auto-detection assumes the source-tree nesting depth, which this image does not have.
ENV FINALLY_DB_PATH=/app/db/finally.db
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/health', timeout=2).status==200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "10"]
```
Note: the `HEALTHCHECK` uses a Python one-liner instead of `curl`/`wget` deliberately — `python:3.12-slim` does not include either by default, and adding `curl` via `apt-get install` only for the healthcheck is an avoidable dependency for a container that already has a Python interpreter on `PATH`.

### Pattern 2: Bounded graceful shutdown for Uvicorn behind SSE

**What:** Set Uvicorn's `timeout_graceful_shutdown` to a small positive integer instead of leaving it at the default `None` (unbounded).
**When to use:** Any FastAPI/Uvicorn app serving long-lived `StreamingResponse`/SSE connections that must also respond cleanly to `docker stop`.
**Example:**
```python
# Source: https://github.com/kludex/uvicorn/blob/main/docs/settings.md (Settings > Timeouts)
#         https://github.com/kludex/uvicorn/blob/main/config.py (Config.__init__ signature)
# timeout_graceful_shutdown: int | None = None  <- default is UNBOUNDED, this is the root
# cause of the hang already observed twice in scripts/smoke.sh's cleanup trap.

# CLI form (used in the Dockerfile CMD above):
# uvicorn app.main:app --host 0.0.0.0 --port 8000 --timeout-graceful-shutdown 10

# Programmatic form, if ever invoked via uvicorn.run() instead of the CLI:
import uvicorn
uvicorn.run("app.main:app", host="0.0.0.0", port=8000, timeout_graceful_shutdown=10)
```
Pair this with a `docker stop --time` (or `--stop-timeout` at `docker run`) slightly *larger* than the Uvicorn value (e.g., 15s vs. Uvicorn's 10s), so Uvicorn's own bounded cancellation resolves first under normal conditions and Docker's SIGKILL is a true last resort, not the primary mechanism:
```bash
# Source: https://docs.docker.com/reference/cli/docker/container/stop/ (fetched directly this session)
# "the container's main process receives SIGTERM ... Default timeout is 10 seconds
#  for Linux containers ... configurable via --timeout"
docker run -d --name finally-app --stop-timeout 15 ...
docker stop --timeout 15 finally-app   # or just `docker stop finally-app` if --stop-timeout was set at run time
```

### Pattern 3: Compose-paired E2E with ephemeral test DB

**What:** `test/docker-compose.test.yml` runs the production image plus a Playwright container, using `depends_on: condition: service_healthy` and a `tmpfs` mount for the app's DB so E2E runs never touch the dev bind mount.
**When to use:** Whenever the SUT (system under test) is the actual containerized artifact, not a dev server.
**Example:**
```yaml
# Source: pattern synthesized from official Playwright Docker docs
# (github.com/microsoft/playwright/blob/main/docs/src/docker.md) and general
# Docker Compose healthcheck/tmpfs documentation (docs.docker.com); no single
# doc combines all three verbatim, so treat structure as [CITED] not a literal snippet.
services:
  app:
    build:
      context: ..
      dockerfile: Dockerfile
    environment:
      LLM_MOCK: "true"
    tmpfs:
      - /app/db          # ephemeral: fresh, seeded DB every run; never the host bind mount
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"]
      interval: 5s
      timeout: 3s
      retries: 10
      start_period: 5s

  playwright:
    image: mcr.microsoft.com/playwright:v1.62.1-noble   # MUST match test/package.json's @playwright/test version
    depends_on:
      app:
        condition: service_healthy
    working_dir: /work
    volumes:
      - ./:/work
    environment:
      BASE_URL: http://app:8000
    command: sh -c "npm ci && npx playwright test"
```
Run it with exit-code propagation for CI:
```bash
docker compose -f test/docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from playwright
code=$?
docker compose -f test/docker-compose.test.yml down -v
exit $code
```

### Pattern 4: Idempotent lifecycle scripts

**What:** Check container/image state before acting, so re-running `start_mac.sh` or `stop_mac.sh` is always safe.
**When to use:** Any single-container start/stop script pair meant to be run repeatedly by non-expert users.
**Example (bash):**
```bash
#!/usr/bin/env bash
set -euo pipefail
IMAGE=finally
NAME=finally-app

if ! docker image inspect "$IMAGE" >/dev/null 2>&1 || [ "${1:-}" = "--build" ]; then
    docker build -t "$IMAGE" .
fi

STATE="$(docker inspect -f '{{.State.Running}}' "$NAME" 2>/dev/null || echo "absent")"
case "$STATE" in
    true)
        echo "finally is already running at http://localhost:8000"
        ;;
    false)
        docker start "$NAME"
        ;;
    absent)
        docker run -d --name "$NAME" \
            -v "$(pwd)/db:/app/db" \
            -p 8000:8000 --env-file .env \
            --stop-timeout 15 \
            "$IMAGE"
        ;;
esac
echo "Open http://localhost:8000"
```
**Example (stop, bash):**
```bash
#!/usr/bin/env bash
set -euo pipefail
NAME=finally-app
if docker inspect -f '{{.State.Running}}' "$NAME" >/dev/null 2>&1; then
    docker stop --timeout 15 "$NAME"
else
    echo "finally is not running"
fi
# Deliberately no `docker rm`/`docker volume rm` here -- stopping never destroys data (D-01, DEPLOY-03).
```
**Example (PowerShell equivalent, start):**
```powershell
# Source: pattern synthesized from general PowerShell+Docker JSON-parsing guidance
# (jdhitsolutions.com/blog/powershell series); no single official MS doc covers
# this exact idempotent pattern, so treat as [CITED]-tier guidance, not verbatim.
$Image = "finally"
$Name = "finally-app"

if (-not (docker image inspect $Image 2>$null) -or $args -contains "--build") {
    docker build -t $Image .
}

$state = docker inspect -f '{{.State.Running}}' $Name 2>$null
if ($LASTEXITCODE -ne 0) {
    docker run -d --name $Name `
        -v "${PWD}\db:/app/db" `
        -p 8000:8000 --env-file .env `
        --stop-timeout 15 `
        $Image
} elseif ($state -eq "true") {
    Write-Host "finally is already running at http://localhost:8000"
} else {
    docker start $Name
}
Write-Host "Open http://localhost:8000"
```

### Anti-Patterns to Avoid

- **Relying on `resolve_db_path()`'s default in the container:** The `parents[3]` computation in `backend/app/db/connection.py:32` assumes the exact source-tree nesting depth (`<repo-root>/backend/app/db/connection.py`). A Docker image that copies `backend/`'s contents into `/app` breaks this silently — no error, just a DB written somewhere other than the bind mount. Always set `FINALLY_DB_PATH` explicitly in the Dockerfile.
- **Leaving `timeout_graceful_shutdown` at its default:** `None` means unbounded — this is the exact mechanism behind the already-observed `scripts/smoke.sh` hang.
- **Mixing Astral's `astral-sh/uv:python3.12-trixie-slim` builder with a plain `python:3.12-slim` (bookworm) runtime:** two different Debian suites across stages risk a glibc-version mismatch for compiled wheels (numpy).
- **`docker rm`/`docker volume rm` inside a stop script:** violates DEPLOY-03's "stopping never destroys the data volume" requirement; stop scripts must only `docker stop`.
- **Running the E2E Playwright container against the dev bind-mounted `db/`:** would pollute or reset the developer's actual portfolio data; use `tmpfs` for the test compose service instead.
- **Playwright npm package version and Docker image tag drifting apart:** the two must match exactly (`@playwright/test@1.62.1` ↔ `mcr.microsoft.com/playwright:v1.62.1-noble`), or browser/test-runner protocol mismatches can cause opaque failures.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Browser automation environment for E2E in Docker | A custom Dockerfile installing Chromium/Firefox/WebKit + all system deps | `mcr.microsoft.com/playwright:v<version>-noble` official image | Official image already handles the notoriously fiddly headless-browser system dependency list (fonts, codecs, sandboxing libs); reinventing this is a multi-hour dependency-chasing exercise with no functional benefit |
| Waiting for the app container to be ready before running tests | A custom polling/sleep loop in a shell wrapper around `docker compose up` | Compose's built-in `healthcheck` + `depends_on: condition: service_healthy` | Native Compose feature, avoids race conditions and arbitrary sleep durations |
| Detecting SIGTERM-vs-hang for a long-lived server | A custom signal handler that forcibly kills its own event loop after N seconds | Uvicorn's built-in `timeout_graceful_shutdown` setting | It's precisely what this setting exists for; a hand-rolled handler would duplicate logic Uvicorn already implements correctly |

**Key insight:** everything in this phase is orchestration/configuration, not new business logic — every "custom" solution considered above already has a first-party, better-tested equivalent (Uvicorn's own timeout setting, Docker Compose's own healthcheck primitive, Playwright's own Docker image). The risk in this phase is exclusively in *wiring these correctly together*, not in needing to build anything new.

## Common Pitfalls

### Pitfall 1: Uvicorn's graceful-shutdown timeout defaults to unbounded, hanging on open SSE connections

**What goes wrong:** `docker stop` (or a bare SIGTERM from `scripts/smoke.sh`'s trap) sends SIGTERM to Uvicorn. Uvicorn stops accepting new connections and waits for in-flight requests/tasks to finish — but the SSE generator in `backend/app/market/stream.py` only exits its `while True` loop when *the client* disconnects (`await request.is_disconnected()`), never in response to the server's own shutdown signal. With `timeout_graceful_shutdown=None` (the default), Uvicorn waits **forever** for that task to finish, and it never will while a client (or the E2E test) still has the SSE connection open.
**Why it happens:** `request.is_disconnected()` detects the *client* going away, not the *server* initiating shutdown; these are two independent signals, and only client-disconnect is wired into `_generate_events()`'s loop today (`backend/app/market/stream.py:69-85`).
**How to avoid:** Set Uvicorn's `timeout_graceful_shutdown` to a small bounded value (e.g., 10s) via the `--timeout-graceful-shutdown` CLI flag or `uvicorn.run(..., timeout_graceful_shutdown=10)`. After that timeout, Uvicorn force-cancels the remaining request tasks regardless of what they're doing [CITED: github.com/kludex/uvicorn/blob/main/docs/settings.md]. Give `docker stop`/`docker run --stop-timeout` a slightly larger window (e.g., 15s) so Uvicorn's own bound resolves first.
**Warning signs:** `docker stop` (or the smoke.sh trap) takes noticeably longer than expected, or requires a manual `docker kill`/force-kill to actually terminate — this has already happened twice per `STATE.md`'s Blockers/Concerns entry for Phase 4.

### Pitfall 2: The DB path auto-detection breaks silently once the backend is copied into a Docker image

**What goes wrong:** With no `FINALLY_DB_PATH` set, `resolve_db_path()` computes the database location as `Path(__file__).resolve().parents[3] / "db" / "finally.db"`. This literally means "three directories above `connection.py`," which in the source tree is the repo root (`backend/app/db/connection.py` → `backend/app/db` → `backend/app` → `backend` → repo root). If the Dockerfile copies `backend/`'s *contents* into `/app` (flattening one level of nesting, which is also required for `app.frontend()`'s own `parents[1]` static-path assumption in `main.py:99-104` to resolve correctly), `parents[3]` from `/app/app/db/connection.py` resolves to filesystem root (`/`), not `/app`. The app would silently create and write to `/db/finally.db` inside the container's writable layer — a path that is **never the bind-mounted volume** — and every restart would appear to work but actually reset the portfolio.
**Why it happens:** The path-resolution comment (`# backend/app/db/connection.py -> parents[3] is the repo root`, `connection.py:31`) is a valid assumption only for the exact source-tree layout; it has no way to know it's running inside a differently-shaped container filesystem. This is exactly the kind of failure that only surfaces on the *second* container run (after the first run seeded a throwaway DB) — the app "just works" on first boot regardless.
**How to avoid:** Set `ENV FINALLY_DB_PATH=/app/db/finally.db` explicitly in the Dockerfile's final stage, matching whatever path is bind-mounted at `docker run` time (`-v $(pwd)/db:/app/db` per D-01). This is exactly the override mechanism `connection.py:27-29` already exists to support — no backend code changes needed, just don't skip setting the env var.
**Warning signs:** Portfolio/watchlist/chat history resets after `stop_mac.sh` + `start_mac.sh`, even though `db/finally.db` exists and is non-empty on the host — the file the host sees was never the one the container's process last wrote to.

> **Evidence for this pitfall (read this session, quoted verbatim per in-repo value provenance rule):**
> `backend/app/db/connection.py:27-32`
> ```python
>     env_path = os.environ.get("FINALLY_DB_PATH", "").strip()
>     if env_path:
>         path = Path(env_path)
>     else:
>         # backend/app/db/connection.py -> parents[3] is the repo root
>         path = Path(__file__).resolve().parents[3] / "db" / "finally.db"
> ```
> `backend/app/main.py:99-104`
> ```python
> app.frontend(
>     "/",
>     directory=Path(__file__).resolve().parents[1] / "static",
>     fallback="index.html",
>     check_dir=False,
> )
> ```
> [VERIFIED: backend/app/db/connection.py:27-32] and [VERIFIED: backend/app/main.py:99-104]

### Pitfall 3: `python:3.12-slim` has no `curl`/`wget` for `HEALTHCHECK`

**What goes wrong:** Copy-pasting a generic `HEALTHCHECK ... CMD curl --fail http://localhost:8000/api/health` from a tutorial fails at build/run time because `curl` is not installed in the `slim` Debian base image.
**Why it happens:** `slim` variants deliberately exclude common CLI tools to minimize image size.
**How to avoid:** Either `apt-get install -y curl` (adds ~10-15MB and an update/cleanup step) or use the Python interpreter that's already on `PATH` (`python -c "import urllib.request; urllib.request.urlopen(...)"`) — the latter adds zero image size, matching CLAUDE.md's "do not overengineer" guidance.
**Warning signs:** `docker build` succeeds, but `docker ps` shows the container stuck in `(health: starting)` or `(unhealthy)` indefinitely; `docker inspect --format='{{json .State.Health}}' finally-app` shows a "command not found" error in the healthcheck log.

### Pitfall 4: Mixing Debian suites across the uv builder and the runtime stage

**What goes wrong:** Using `ghcr.io/astral-sh/uv:python3.12-trixie-slim` (Debian 13/trixie, Astral's current default tag family per their 0.9+ releases) as the builder while the final runtime stage is `python:3.12-slim` (Debian 12/bookworm, Docker Hub's current default for that tag) can produce a runtime `GLIBC_2.4X not found` failure the first time a compiled wheel (numpy, in this project) is imported, because the venv was built against trixie's newer glibc.
**Why it happens:** Astral replaced bookworm-based ghcr.io images with trixie defaults in uv 0.9+, while the official `python` Docker Hub image's unqualified `-slim` tag is still bookworm-based as of this research.
**How to avoid:** Pin both build and runtime stages to the identical base image tag. The simplest way is the pattern in Code Example 1: `FROM python:3.12-slim AS builder` + `COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/`, then `FROM python:3.12-slim` again for runtime — never let the two stages diverge in Debian suite.
**Warning signs:** `docker build` succeeds; the container starts and then crashes immediately with an `ImportError` or a raw `GLIBC_2.XX not found` message when `numpy` (or any compiled dependency) is first imported.

## Code Examples

See Architecture Patterns above (Patterns 1-4) for the full Dockerfile, Uvicorn flag, `docker-compose.test.yml`, and start/stop script examples — all code-heavy content lives there to avoid duplication.

### `.dockerignore` (new file, root-level)

```
# Source: general Docker best practice, not tied to a single official doc for this
# project's specific exclusion set — treat as [ASSUMED] guidance, verify against
# actual repo contents before finalizing.
.git
.env
.env.*
!.env.example
node_modules
frontend/node_modules
frontend/.next
frontend/out
backend/.venv
backend/__pycache__
backend/**/__pycache__
db/
test/
*.pyc
```
Critically: `.env` must be excluded so a secret (`OPENROUTER_API_KEY`) is never baked into an image layer; it is passed only via `--env-file .env` at `docker run` time.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `astral-sh/uv:python3.X-bookworm-slim` as the default uv+Python builder image | `astral-sh/uv:python3.X-trixie-slim` is Astral's current default suite (uv 0.9+) | uv 0.9 (2026) | If this project's Dockerfile follows an older tutorial that pins Astral's bookworm-tagged image as the builder, it will still work but drifts from Astral's own current default; the *pitfall* only bites if this stage's Debian suite differs from the final runtime stage's suite, regardless of which one is chosen — consistency matters more than which one |
| `docker-compose` (hyphenated binary) | `docker compose` (V2, integrated Docker CLI subcommand) | Docker Compose V2 has been current for several years | This repo's environment reports `Docker Compose version v5.1.1` (verified this session via `docker compose version`) — use `docker compose` (space, no hyphen) in all scripts and CI, not the deprecated standalone `docker-compose` binary |

**Deprecated/outdated:** the standalone `docker-compose` Python-based binary is in legacy/maintenance mode; all example commands in this document use the `docker compose` CLI plugin form.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `.dockerignore` contents (exact exclusion list) | Code Examples | Low — a missing exclusion just means slightly larger build context or (worst case) `.env` accidentally copied into an intermediate layer if a future `COPY . .` is added carelessly; mitigated by keeping `.env` explicitly listed |
| A2 | The exact PowerShell idempotency pattern shown (Pattern 4) | Architecture Patterns / Code Examples | Low-Medium — PowerShell/Docker CLI JSON-parsing quirks (e.g., `$LASTEXITCODE` semantics after `docker inspect` failure) should be smoke-tested on real Windows/Docker Desktop before trusting verbatim; no single official Microsoft doc covers this exact recipe |
| A3 | Recommending root-level `docker-compose.yml` be skipped entirely | Architecture Patterns (Alternatives Considered) | Low — this is a discretionary simplicity call, not a correctness claim; including it anyway causes no harm, it's just redundant with the scripts |
| A4 | `docker-compose.test.yml` YAML structure (Pattern 3) is a synthesized combination of officially-documented pieces, not copied verbatim from one source | Architecture Patterns | Low-Medium — the individual primitives (`healthcheck`, `depends_on: condition: service_healthy`, `tmpfs:`) are all standard, well-documented Compose keys, but the exact combination shown was assembled by this research, not lifted from a single canonical example; validate the YAML parses and behaves as expected during Wave 0 |

**If this table is empty:** N/A — see entries above; none of them concern the two load-bearing pitfalls (Uvicorn shutdown timeout, FINALLY_DB_PATH), which are grounded in official docs and direct source reads respectively.

## Open Questions

1. **Should `smoke.sh` itself be patched with `--timeout-graceful-shutdown` as part of this phase?**
   - What we know: `STATE.md`'s Blockers/Concerns explicitly says the smoke.sh hang is "worth fixing before Docker/E2E lifecycle management is built on top of it," and the fix is a one-line addition to the same `uvicorn` invocation already in that script.
   - What's unclear: `smoke.sh` is not itself one of DEPLOY-01/02/03/TEST-05's deliverables, so it's not strictly required by any phase requirement.
   - Recommendation: Include it as a small, low-risk first task in the plan — it directly de-risks manual verification of every other task in this phase, and the fix is trivial once Pitfall 1 is understood.

2. **Non-root user inside the runtime container?**
   - What we know: Running as root inside a container is a common (if imperfect) ASVS V14 finding; running as a fixed non-root UID is generally preferred.
   - What's unclear: The bind-mounted `./db` directory's ownership will vary by host user across students' machines; a hardcoded non-root UID in the image can cause permission-denied errors writing to a bind mount owned by a different host UID, especially on Linux hosts (Docker Desktop on Mac/Windows handles UID mapping more transparently).
   - Recommendation: For this single-user, local-only, no-multi-tenant educational deployment, accept running as the image's default user (root) as a documented, low-severity trade-off rather than adding UID-matching complexity; the security review phase can re-evaluate if this needs to change before any non-local deployment.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker Engine | All of DEPLOY-01/02/03, TEST-05 | ✓ (this research environment) | 29.3.1 | none — Docker is the core deployment mechanism per PLAN.md, not optional |
| Docker Compose (V2 CLI plugin) | TEST-05 (`docker-compose.test.yml`) | ✓ | v5.1.1 | none for the E2E harness; the production container itself does not require compose |
| Node.js 20+ | Frontend build stage (inside Docker, not the host) | N/A — build happens inside the `node:20-slim` build stage, not on the host | — | — |
| `uv` | Backend build stage (inside Docker) | N/A — installed via `COPY --from=ghcr.io/astral-sh/uv:latest` inside the build, not required on the host | — | — |

**Missing dependencies with no fallback:** none identified in this research environment; the actual student/grader machine's Docker availability is the real constraint this phase can't verify in advance — the start scripts should fail with a clear message if `docker info` fails, rather than a cryptic Docker CLI error.

**Missing dependencies with fallback:** none.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Playwright (`@playwright/test`, pin to `1.62.1` or whatever `npm view @playwright/test version` returns at implementation time) |
| Config file | `test/playwright.config.ts` — none yet, Wave 0 |
| Quick run command | `cd test && npx playwright test --project=chromium` (against an already-running dev instance, for fast local iteration) |
| Full suite command | `docker compose -f test/docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from playwright` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|--------------|
| DEPLOY-01 | `docker build` succeeds; single container serves frontend+API+SSE+chat on :8000, no CORS needed | manual/smoke (infra, not unit-testable business logic) | `docker build -t finally . && docker run --rm -d -p 8000:8000 --env-file .env finally && curl -f http://localhost:8000/api/health && curl -f http://localhost:8000/` | ❌ Wave 0 |
| DEPLOY-02 | Stopping/restarting the container preserves cash, positions, trades, chat history | manual/integration (infra) | Trade via API, `docker stop`/`docker start`, re-`GET /api/portfolio`, assert unchanged | ❌ Wave 0 |
| DEPLOY-03 | Start/stop scripts are idempotent on macOS/Linux and Windows; stop never destroys the volume | manual (cross-platform, can't run Windows CI from this environment) | Run each script twice in a row, assert exit code 0 both times and container state matches expectation | ❌ Wave 0 |
| TEST-05 | Fresh start, watchlist add/remove, buy/sell, heatmap/P&L rendering, AI chat with inline trade, SSE reconnection | e2e (Playwright, `LLM_MOCK=true`) | `npx playwright test` (inside `docker-compose.test.yml`'s playwright service) | ❌ Wave 0 — no spec files exist in `test/` yet |

### Sampling Rate

- **Per task commit:** `cd test && npx playwright test --project=chromium` against a locally-running dev instance (fast iteration, no Docker rebuild)
- **Per wave merge:** full `docker compose -f test/docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from playwright`
- **Phase gate:** full suite green, plus the DEPLOY-01/02/03 manual smoke commands above, before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `test/package.json` — Playwright devDependency, `checkpoint:human-verify` before `npm install` per the Package Legitimacy Audit
- [ ] `test/playwright.config.ts` — `baseURL` from `process.env.BASE_URL`, no `webServer` block (compose starts the app, not Playwright)
- [ ] `test/tests/*.spec.ts` — one spec file per TEST-05 scenario
- [ ] `test/docker-compose.test.yml` — app + playwright services per Pattern 3
- [ ] `.dockerignore` — root-level, per Code Examples
- [ ] `Dockerfile` — root-level, per Pattern 1
- [ ] `scripts/start_mac.sh`, `scripts/stop_mac.sh`, `scripts/start_windows.ps1`, `scripts/stop_windows.ps1` — none exist yet

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|----------------|---------|-------------------|
| V2 Authentication | No | Single hardcoded `user_id="default"`, no login — explicitly out of scope for the whole project |
| V3 Session Management | No | No sessions |
| V4 Access Control | No | No roles/permissions |
| V5 Input Validation | Not primarily this phase's concern (covered in Phases 1-3's own security reviews) | — |
| V14 Configuration | Yes — the central category for this phase | `.dockerignore` excludes secrets; secrets passed only via `--env-file` at `docker run`, never `COPY`'d into an image layer; `HEALTHCHECK` and `/api/health` do not leak the API key, a file path, or a version (already true per `main.py`'s existing docstring/comment) |
| V1 Architecture | Marginal | Document the single-container security boundary (no internal network segmentation needed since there's one process) |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|-----------------------|
| Secret baked into a Docker image layer (e.g., a careless `COPY .env .`) | Information Disclosure | `.dockerignore` excludes `.env`; secrets only ever enter via `--env-file` at `docker run` time, never at build time |
| Container running as root | Elevation of Privilege | Accepted risk for this phase (see Open Questions #2) given the bind-mount UID-matching complexity vs. the single-user local threat model; revisit if this project is ever deployed beyond localhost |
| Unbounded shutdown hang used as a local denial-of-service against the developer's own workflow | Denial of Service (self-inflicted, not attacker-driven) | Bounded `timeout_graceful_shutdown` + `docker stop --time` (Pitfall 1) |
| E2E test run corrupting the developer's real portfolio data | Tampering | `tmpfs` mount for the test compose service's `/app/db`, never the host bind mount (Pattern 3) |
| Healthcheck endpoint leaking internal paths/versions to anything that can reach the container | Information Disclosure | Already mitigated — `main.py`'s `/api/health` handler explicitly documents that it never reports the API key, a file path, or a version |

## Sources

### Primary (MEDIUM confidence — Context7-sourced official docs)
- `/astral-sh/uv` and `/astral-sh/uv-docker-example` (Context7) — multi-stage Dockerfile patterns, `COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/` pattern
- `/kludex/uvicorn` (Context7) — `timeout_graceful_shutdown` setting, `Config.__init__` signature, server-behavior docs
- `/vercel/next.js` v16.1.6 (Context7) — `output: 'export'` static export configuration, output-mode type definitions
- `/microsoft/playwright` (Context7) — official Docker image usage, `webServer`/`reuseExistingServer` config API
- `/websites/fastapi_tiangolo` (Context7) — `app.frontend()` API reference and SPA-fallback tutorial (confirms the code already in `backend/app/main.py` uses the current, documented API)
- `docs.docker.com/reference/cli/docker/container/stop/` (fetched directly via WebFetch this session) — default 10s SIGTERM→SIGKILL grace period, `--timeout` flag

### Secondary (LOW→MEDIUM confidence — WebSearch, cross-checked across multiple independent results)
- Uvicorn/sse-starlette GitHub issues/discussions on SSE-vs-graceful-shutdown hangs (corroborates the mechanism, not just the fix)
- FastAPI GitHub discussions on `StreamingResponse`/`request.is_disconnected()` disconnect detection
- Docker Compose `depends_on: condition: service_healthy` + `tmpfs` E2E isolation pattern (multiple independent blog/community sources agreeing on the same mechanism)
- Bash/PowerShell idempotent Docker lifecycle script patterns (community sources; no single official doc)
- Next.js 16 minimum Node version (20.9+) — cross-checked against `nextjs.org/docs/app/guides/upgrading/version-16`

### Tertiary (this session's in-repo verification — highest confidence for the two load-bearing pitfalls)
- `backend/app/db/connection.py:21-36` (Read this session) — `FINALLY_DB_PATH` override and `parents[3]` auto-detection
- `backend/app/main.py:74-104` (Read this session) — `app.frontend()` usage, `parents[1]` static-path assumption
- `backend/app/market/stream.py:51-88` (Read this session) — SSE generator's disconnect-detection loop, confirms it only reacts to client disconnect, not server shutdown
- `scripts/smoke.sh:14-21` (Read this session) — existing (unbounded) SIGTERM cleanup trap, the exact reproduction of Pitfall 1
- `.planning/config.json` (Read this session) — confirms `nyquist_validation: true` and `security_enforcement: true`, both sections included above accordingly

## Metadata

**Confidence breakdown:**
- Standard stack (Docker base images, uv pattern, Playwright image): MEDIUM — all Context7/official-docs sourced, no single source combines every piece verbatim
- Architecture (Dockerfile structure, compose pairing, script idempotency): MEDIUM — synthesized from multiple official primitives; the overall combination has not been build-tested in this research session (no `docker build` was run)
- Pitfalls (Uvicorn shutdown timeout, FINALLY_DB_PATH path resolution): HIGH — the shutdown-timeout fix is directly from official Uvicorn docs, and the DB-path pitfall is verified by reading this repo's actual source code this session, not inferred

**Research date:** 2026-08-26
**Valid until:** ~30 days (Docker/uv/Playwright/Next.js all ship frequently; re-verify exact version numbers — `@playwright/test`, base image tags — immediately before implementation rather than trusting this document's pinned numbers if more than a few weeks have passed)
