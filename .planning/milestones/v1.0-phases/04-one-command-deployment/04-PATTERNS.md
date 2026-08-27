# Phase 4: One-Command Deployment - Pattern Map

**Mapped:** 2026-08-26
**Files analyzed:** 12
**Analogs found:** 3 shared analogs cover all 12 (this phase is packaging/orchestration, not new business logic)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `Dockerfile` | config | batch (build pipeline) | `scripts/smoke.sh` (build-then-copy-to-static pattern) | role-match |
| `.dockerignore` | config | — | none (new concern) | no analog |
| `scripts/start_mac.sh` | utility | request-response (CLI lifecycle) | `scripts/smoke.sh` | role-match |
| `scripts/stop_mac.sh` | utility | request-response (CLI lifecycle) | `scripts/smoke.sh` (cleanup/trap section) | role-match |
| `scripts/start_windows.ps1` | utility | request-response (CLI lifecycle) | `scripts/smoke.sh` (logic port to PowerShell) | partial (cross-language) |
| `scripts/stop_windows.ps1` | utility | request-response (CLI lifecycle) | `scripts/smoke.sh` (cleanup section) | partial (cross-language) |
| `test/docker-compose.test.yml` | config | event-driven (health-gated startup) | `scripts/smoke.sh` (health-poll loop, conceptually) | partial |
| `test/playwright.config.ts` | config | — | none (first Playwright config in repo) | no analog |
| `test/tests/*.spec.ts` | test | request-response / event-driven | `scripts/smoke.sh` (assertion sequence: health, static HTML, watchlist, SSE) | role-match (cross-language) |
| Dockerfile `ENV FINALLY_DB_PATH=...` line | config | file-I/O | `backend/app/db/connection.py:21-36` (`resolve_db_path`) | exact (env var contract) |
| Dockerfile `CMD uvicorn ...` line | config | request-response | `backend/app/main.py` (uvicorn entry point, `app.frontend()` static serving) | exact |
| `scripts/smoke.sh` (recommended patch, not a new file) | utility | request-response | itself — add `--timeout-graceful-shutdown` per RESEARCH Pitfall 1 | n/a |

## Pattern Assignments

### `Dockerfile` (config, batch build pipeline)

**Analog:** `scripts/smoke.sh` (build stage) + `backend/app/db/connection.py` + `backend/app/main.py` (runtime contract)

**Build-then-copy-to-static pattern** — `scripts/smoke.sh` lines 23-35:
```bash
if [ ! -f "${BACKEND_DIR}/static/index.html" ]; then
    echo "==> Building frontend static export (backend/static/index.html not found)"
    npm --prefix "${REPO_ROOT}/frontend" run build
    mkdir -p "${BACKEND_DIR}/static"
    if command -v rsync >/dev/null 2>&1; then
        rsync -a --delete --exclude=".gitkeep" "${REPO_ROOT}/frontend/out/" "${BACKEND_DIR}/static/"
    else
        find "${BACKEND_DIR}/static" -mindepth 1 ! -name ".gitkeep" -exec rm -rf {} +
        cp -R "${REPO_ROOT}/frontend/out/." "${BACKEND_DIR}/static/"
    fi
fi
```
This is the exact shape the Dockerfile's multi-stage `COPY --from=frontend-builder /fe/out ./static` should mirror: frontend build output lands in a directory literally named `static` next to the backend app, because `app.frontend()` in `main.py:99-104` resolves it at `Path(__file__).resolve().parents[1] / "static"`. **Do not rename this directory in the image layout** — `parents[1]` from `/app/app/main.py` must land on `/app/static`, matching the flattened `backend/`→`/app` copy RESEARCH.md specifies.

**Server start command pattern** — `scripts/smoke.sh` lines 37-40:
```bash
echo "==> Starting uvicorn (FINALLY_DB_PATH=${TMP_DB})"
uv run --directory "${BACKEND_DIR}" --extra dev uvicorn app.main:app --host 127.0.0.1 --port 8000 \
    >/tmp/finally-smoke-server.log 2>&1 &
SERVER_PID=$!
```
Dockerfile's `CMD` should follow the same `uvicorn app.main:app --host 0.0.0.0 --port 8000` invocation, but add `--timeout-graceful-shutdown 10` (see Shared Patterns below) since the container has no `--extra dev`/uv-run wrapper needed at runtime — deps are already synced into the image's venv.

**FINALLY_DB_PATH contract** — `backend/app/db/connection.py:21-36`:
```python
def resolve_db_path() -> Path:
    env_path = os.environ.get("FINALLY_DB_PATH", "").strip()
    if env_path:
        path = Path(env_path)
    else:
        # backend/app/db/connection.py -> parents[3] is the repo root
        path = Path(__file__).resolve().parents[3] / "db" / "finally.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
```
The Dockerfile's final stage MUST set `ENV FINALLY_DB_PATH=/app/db/finally.db` explicitly. The `parents[3]` fallback assumes the exact `backend/app/db/connection.py` source-tree depth and will resolve to `/` (not `/app`) once `backend/`'s contents are flattened into `/app`, silently writing the DB outside the bind mount (RESEARCH.md Pitfall 2). No backend code changes needed — this is purely a Dockerfile `ENV` line copying the same idiom the code already supports.

**Static serving contract** — `backend/app/main.py:99-104`:
```python
app.frontend(
    "/",
    directory=Path(__file__).resolve().parents[1] / "static",
    fallback="index.html",
    check_dir=False,
)
```
Confirms the image layout requirement above: whatever directory `main.py` ends up in inside the container, `static/` must be its sibling one level up.

---

### `scripts/start_mac.sh` / `scripts/stop_mac.sh` (utility, CLI lifecycle)

**Analog:** `scripts/smoke.sh` (shebang, strict mode, path resolution, trap/cleanup idiom)

**Shebang + strict mode + repo-root resolution** — `scripts/smoke.sh` lines 1-7:
```bash
#!/usr/bin/env bash
# End-to-end smoke gate: fresh DB, boot, health, static page, watchlist, SSE frame.
# Exits non-zero on the first failed assertion.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${REPO_ROOT}/backend"
```
New start/stop scripts should reuse this exact `set -euo pipefail` + `REPO_ROOT` resolution idiom for path-independence (works whether invoked from repo root or elsewhere).

**Cleanup/trap idiom** — `scripts/smoke.sh` lines 12-21:
```bash
SERVER_PID=""

cleanup() {
    if [ -n "${SERVER_PID}" ] && kill -0 "${SERVER_PID}" 2>/dev/null; then
        kill "${SERVER_PID}" 2>/dev/null || true
        wait "${SERVER_PID}" 2>/dev/null || true
    fi
    rm -f "${TMP_DB}" "${TMP_DB}-wal" "${TMP_DB}-shm"
}
trap cleanup EXIT
```
This is the exact failure mode RESEARCH.md documents (unbounded wait on SIGTERM when SSE connections are open — `kill` here has no timeout, mirroring the hang). `stop_mac.sh` must NOT reuse this pattern verbatim; it must instead bound the wait, per Shared Patterns below (`docker stop --timeout 15` relies on the container's own `--timeout-graceful-shutdown 10`, not a bare `kill`/`wait`).

**Health-poll loop** — `scripts/smoke.sh` lines 42-55:
```bash
echo "==> Waiting for /api/health"
READY=0
for _ in $(seq 1 40); do
    if curl -sf http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
        READY=1
        break
    fi
    sleep 0.5
done
if [ "${READY}" -ne 1 ]; then
    echo "FAIL: server did not answer /api/health within 20s"
    exit 1
fi
```
Useful reference for `start_mac.sh` if it wants to confirm the container actually came up before printing "Open http://localhost:8000" (optional nicety — RESEARCH.md's Pattern 4 script example doesn't include this, but it's low-cost to add via the same idiom).

---

### `scripts/start_windows.ps1` / `scripts/stop_windows.ps1` (utility, cross-language port)

**Analog:** `scripts/smoke.sh` logic, ported (no existing PowerShell in repo — first PS file)

No direct PowerShell analog exists in the codebase. Port the same responsibilities as the bash scripts (idempotency check, build-if-missing, bind-mount `db/`, `--env-file .env`, bounded stop) using RESEARCH.md's Pattern 4 PowerShell example as the structural template, since it's the only concrete PowerShell reference available (flagged `[ASSUMED]`-tier in RESEARCH.md — smoke-test on real Windows/Docker Desktop before trusting verbatim per RESEARCH.md Assumption A2).

---

### `test/docker-compose.test.yml` / `test/playwright.config.ts` / `test/tests/*.spec.ts` (config + test, event-driven / request-response)

**Analog:** `scripts/smoke.sh`'s assertion sequence (conceptual analog — same scenarios, different tooling)

`scripts/smoke.sh` lines 57-125 enumerate exactly the assertions the new Playwright specs replace/extend at the E2E layer:
```bash
echo "==> Assert: GET /api/health returns ok status and simulator market_source"
...
echo "==> Assert: fresh database has six tables, one seeded user, ten watchlist rows"
...
echo "==> Assert: GET / returns HTML containing terminal-root"
...
echo "==> Assert: GET /api/watchlist returns ten entries"
...
echo "==> Assert: SSE stream emits a data: frame with every seeded symbol"
```
Map these 1:1 onto `test/tests/fresh-start.spec.ts` (health + terminal-root + watchlist count) and `test/tests/sse-reconnect.spec.ts` (SSE data frame with `direction` field). This confirms the exact user-visible assertions already proven meaningful in this repo — reuse the same expected values (`{"status":"ok","market_source":"simulator"}`, `terminal-root` marker in HTML, 10 watchlist entries, SSE `direction` field) as Playwright assertions rather than inventing new ones.

No config-file analog exists for `playwright.config.ts` or `docker-compose.test.yml` — these are genuinely new to the repo; follow RESEARCH.md Pattern 3 verbatim (it is the only source, synthesized from official docs, not copied from an existing file).

---

## Shared Patterns

### Bounded graceful shutdown (applies to: Dockerfile CMD, scripts/stop_mac.sh, scripts/stop_windows.ps1, test/docker-compose.test.yml teardown)

**Source:** RESEARCH.md Pattern 2, grounded in `backend/app/market/stream.py`'s disconnect-only loop (read this session by researcher) and the observed hang in `scripts/smoke.sh`'s bare `kill`/`wait` (lines 15-17 above — no timeout).

```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "10"]
```
```bash
docker run -d --name finally-app --stop-timeout 15 ...
docker stop --timeout 15 finally-app   # stop_mac.sh
```
**Apply to:** `Dockerfile` (CMD line), `scripts/stop_mac.sh`, `scripts/stop_windows.ps1`, `test/docker-compose.test.yml`'s app service. Never reuse `scripts/smoke.sh`'s unbounded `kill`+`wait` for anything Docker-based — that pattern is the reproduction of the bug, not the fix.

### FINALLY_DB_PATH env override (applies to: Dockerfile, docker-compose.test.yml)

**Source:** `backend/app/db/connection.py:27-29` (verbatim quoted above).

```dockerfile
ENV FINALLY_DB_PATH=/app/db/finally.db
```
**Apply to:** `Dockerfile` final stage (bind-mount case, per D-01) and `test/docker-compose.test.yml`'s app service — but there paired with `tmpfs: - /app/db` instead of a host bind mount, so the same env var points at an ephemeral filesystem for test isolation.

### Env-var truthy-check idiom (applies to: any new deployment flags, docker-compose.test.yml's `LLM_MOCK`)

**Source:** `backend/app/main.py:30-32`:
```python
llm_mock_enabled = os.environ.get("LLM_MOCK", "").strip().lower() == "true"
```
**Apply to:** No new backend code is needed this phase, but `test/docker-compose.test.yml` must set `LLM_MOCK: "true"` (string, matching this exact truthy check) on the app service — not a YAML boolean `true`, which some compose parsers pass through as the literal string `"true"` but is worth being explicit about given this idiom's exact string comparison.

### `.env` never baked into an image layer (applies to: Dockerfile, .dockerignore)

**Source:** RESEARCH.md Code Examples (`.dockerignore`), cross-referenced with `backend/app/main.py`'s comment about `litellm`'s side-effecting `.env` load via `python-dotenv` (lines 34-40) — confirms `.env` loading is expected to happen via runtime env vars / `--env-file`, not a baked-in file.
```
.env
.env.*
!.env.example
```
**Apply to:** `.dockerignore` (exclude), `Dockerfile` (never `COPY .env`), all lifecycle scripts (pass `--env-file .env` at `docker run`, never `docker build --secret` or similar unless revisited).

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `.dockerignore` | config | — | First Docker-related file in repo; no prior exclusion-list convention to follow. Use RESEARCH.md's Code Examples list as-is (marked `[ASSUMED]` there — verify against actual repo contents before finalizing). |
| `test/playwright.config.ts` | config | — | First Playwright config in repo; `test/` has no prior `package.json` or specs (confirmed in CONTEXT.md). Follow RESEARCH.md Architecture Patterns recommended structure (`baseURL` from `process.env.BASE_URL`, no `webServer` block). |
| `test/docker-compose.test.yml` | config | event-driven | First compose file in repo (root `docker-compose.yml` is explicitly skipped per RESEARCH.md Alternatives Considered). Follow RESEARCH.md Pattern 3 verbatim — it is synthesized from official docs, not an in-repo pattern. |
| `docker-compose.yml` (root, optional) | config | — | RESEARCH.md recommends skipping entirely (Alternatives Considered) — not required for DEPLOY-01..03; planner's discretion whether to include it at all. |

## Metadata

**Analog search scope:** `scripts/`, `backend/app/db/`, `backend/app/main.py`, `backend/app/market/stream.py` (referenced via RESEARCH.md quotes), `test/` (confirmed empty of specs/config)
**Files scanned:** `scripts/smoke.sh`, `backend/app/db/connection.py`, `backend/app/main.py`, plus CONTEXT.md/RESEARCH.md cross-references to `backend/app/market/stream.py` and `backend/app/market/factory.py`
**Pattern extraction date:** 2026-08-26
