---
phase: 04-one-command-deployment
reviewed: 2026-08-26T22:03:35Z
depth: standard
files_reviewed: 19
files_reviewed_list:
  - .dockerignore
  - Dockerfile
  - db/.gitkeep
  - scripts/smoke.sh
  - scripts/start_mac.sh
  - scripts/start_windows.ps1
  - scripts/stop_mac.sh
  - scripts/stop_windows.ps1
  - scripts/verify_container.sh
  - test/.gitignore
  - test/docker-compose.test.yml
  - test/package-lock.json
  - test/package.json
  - test/playwright.config.ts
  - test/tests/01-fresh-start.spec.ts
  - test/tests/02-watchlist.spec.ts
  - test/tests/03-trading.spec.ts
  - test/tests/04-visualizations.spec.ts
  - test/tests/05-chat.spec.ts
  - test/tests/06-sse-reconnect.spec.ts
findings:
  critical: 1
  warning: 5
  info: 2
  total: 8
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-08-26T22:03:35Z
**Depth:** standard
**Files Reviewed:** 19
**Status:** issues_found

## Summary

Reviewed the Docker packaging, start/stop lifecycle scripts, and the Playwright E2E harness for the one-command-deployment phase. The Dockerfile, `.dockerignore`, and `verify_container.sh` are solid — graceful-shutdown timing, bind-mount persistence, and healthcheck wiring are all correctly reasoned through and the accompanying comments show the authors traced real failure modes (GLIBC mismatch, HSTS-preloaded service name, SSE shutdown hang) rather than guessing.

The one critical finding is serious: `scripts/start_mac.sh` crashes with an "unbound variable" error under macOS's stock `/bin/bash` (3.2.57) whenever no `.env` file is present — which is a scenario the script itself documents as supported ("AI chat will be unavailable... prices and trading still work"). This was reproduced empirically against `bash:3.2` in this review. I also verified empirically that a theorized `.dockerignore` bug (bare `db` pattern possibly matching the nested `backend/app/db` Python package) does **not** occur — Docker's ignore-pattern matching for unslashed patterns is root-anchored, not recursive like `.gitignore`, confirmed with a throwaway `docker build`.

Additional warnings cover container hardening (no non-root `USER`), a host-permission hazard in the Playwright compose service, an inconsistent error-check in the PowerShell start script, and environment leakage into `smoke.sh`'s local (non-Docker) server process.

## Critical Issues

### CR-01: `start_mac.sh` crashes on stock macOS bash when no `.env` file exists

**File:** `scripts/start_mac.sh:27-32,56`
**Issue:** The script declares `ENV_ARGS=()` and only appends to it when `.env` exists (lines 27-32), then unconditionally expands `"${ENV_ARGS[@]}"` inside the `docker run` invocation (line 56), under `set -euo pipefail` (line 5). On macOS's default `/bin/bash` (3.2.57 — Apple has shipped this version since Mavericks/Yosemite for GPLv3 licensing reasons, and it remains `/usr/bin/bash`/what `env bash` resolves to unless the user has explicitly put a newer Homebrew bash earlier on `PATH`), expanding `"${array[@]}"` on a declared-but-empty array under `set -u` raises `unbound variable` and aborts the script — this bug was fixed in bash 4.4 (2016) but macOS's stock bash predates that fix.

Reproduced empirically in this review:
```
$ docker run --rm bash:3.2 bash -c '
set -euo pipefail
ENV_ARGS=()
if [ -f /nonexistent ]; then ENV_ARGS+=(--env-file /nonexistent); else echo "no env file"; fi
echo hi "${ENV_ARGS[@]}" world
'
no env file
bash: line 5: ENV_ARGS[@]: unbound variable
```
This exactly matches `start_mac.sh`'s structure and reproduces the failure for precisely the "no `.env` file" path the script's own echo message on line 31 claims is supported. Since the script is named `start_mac.sh` and targets macOS specifically, this breaks the core "one-command start" promise for any user who hasn't set up the API key yet — the single most common first-run scenario for this project (per PLAN.md, `OPENROUTER_API_KEY` is presented as something the user adds later; prices/trading are meant to work without it).

**Fix:** Use the bash-3.2-safe empty-array idiom, or branch explicitly instead of relying on unconditional array expansion:
```bash
        docker run -d --name "${NAME}" \
            -v "${REPO_ROOT}/db:/app/db" \
            -p "${HOST_PORT}:8000" \
            --stop-timeout 15 \
            ${ENV_ARGS[@]+"${ENV_ARGS[@]}"} \
            "${IMAGE}" >/dev/null
```
(The `${ENV_ARGS[@]+"${ENV_ARGS[@]}"}` parameter-expansion form only expands the array when it has at least one element, which is safe under `set -u` on both old and new bash.) Alternatively, restructure into an explicit `if [ ${#ENV_ARGS[@]} -gt 0 ]; then ... else ... fi` branch around the `docker run` call.

## Warnings

### WR-01: Container runs as root — no `USER` directive in the final image stage

**File:** `Dockerfile:29-50`
**Issue:** The final runtime stage (`FROM python:3.12-slim`) never drops privileges with a `USER` instruction, so `uvicorn` and the FastAPI app run as root inside the container. This is an unnecessary privilege-escalation surface for a process that accepts untrusted HTTP input (`/api/chat`, `/api/portfolio/trade`, `/api/watchlist`) and writes to a bind-mounted host directory (`/app/db`) — any RCE-class bug in the app or a dependency has root inside the container instead of being confined to an unprivileged user.
**Fix:**
```dockerfile
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
```
Note the `db/` bind-mount ownership will need `chown`/`chmod` handling (or a matching host UID) since the mounted directory is created by `mkdir -p` on the host as the invoking user; verify `verify_container.sh` and `smoke.sh` still pass with a non-root `USER` before merging.

### WR-02: Playwright E2E service pollutes the host `test/` directory with root-owned files

**File:** `test/docker-compose.test.yml:26-36`
**Issue:** The `playwright` service bind-mounts the entire `test/` directory (`volumes: - ./:/work`) and runs `npm ci && npx playwright test` inside a container that runs as root by default (verified empirically: `docker run --rm mcr.microsoft.com/playwright:v1.62.1-noble whoami` → `root`). `npm ci` will therefore create `test/node_modules` on the host owned by `root:root`. On native Linux Docker hosts (and some Docker Desktop configurations), a developer's subsequent local `npm ci`/`rm -rf node_modules` outside the container will then fail with `EACCES`/`EPERM` until they `sudo rm -rf test/node_modules`.
**Fix:** Either run the service as the invoking host user, or keep `node_modules` inside the container instead of the bind mount:
```yaml
  playwright:
    image: mcr.microsoft.com/playwright:v1.62.1-noble
    user: "${UID:-1000}:${GID:-1000}"
    ...
```
or mount a named volume for `node_modules` (`- pw_node_modules:/work/node_modules`) so `npm ci`'s output never lands on the host filesystem.

### WR-03: `start_windows.ps1` skips the `$LASTEXITCODE` check for `docker start`, unlike every other docker invocation in the same script

**File:** `scripts/start_windows.ps1:53-56`
**Issue:** Every other docker command in this script (`docker build`, the `docker run` for a fresh container) is followed by an explicit `if ($LASTEXITCODE -ne 0) { exit 1 }` check, because `$ErrorActionPreference = "Stop"` does **not** cause the script to abort on a non-zero exit code from an external executable like `docker.exe` — only cmdlet/terminating errors trigger it. The "existing, stopped container" branch is missing this check:
```powershell
"false" {
    Write-Host "==> Starting existing container $Name"
    docker start $Name | Out-Null
}
```
If `docker start` fails (daemon race, container removed out-of-band, disk pressure, etc.), the script silently falls through to "Waiting for /api/health", which will then time out after ~20s with a generic, less actionable failure message instead of surfacing the real `docker start` error immediately. The bash counterpart (`start_mac.sh:47-49`) does not have this gap because `set -e` makes any failing command abort the whole script automatically — the two scripts are meant to be "branch-for-branch" equivalents per the file's own header comment, and this is a divergence.
**Fix:**
```powershell
"false" {
    Write-Host "==> Starting existing container $Name"
    docker start $Name | Out-Null
    if ($LASTEXITCODE -ne 0) { exit 1 }
}
```

### WR-04: `smoke.sh` inherits the caller's shell environment into the server process, risking a flaky hardcoded assertion

**File:** `scripts/smoke.sh:38-40,58-63`
**Issue:** `smoke.sh` starts the backend directly via `uv run --directory ... uvicorn ...` (not inside Docker), which inherits the invoking shell's full environment. If the developer's shell already has `MASSIVE_API_KEY` exported (e.g., sourced from the project's `.env` for other work, or exported in `~/.bashrc`/`~/.zshrc`), the backend will attempt to use the Massive data source instead of the simulator, and the hardcoded assertion at line 60 (`HEALTH_BODY != '{"status":"ok","market_source":"simulator"}'`) will fail non-deterministically depending on the caller's ambient environment — even though the code under test is correct. `verify_container.sh` and `docker-compose.test.yml` avoid this by running the app inside a container with a controlled environment (no `--env-file` passed, or `MASSIVE_API_KEY: ""` explicitly set); `smoke.sh` has no equivalent isolation.
**Fix:** Explicitly neutralize the market-data env vars before starting the server:
```bash
export MASSIVE_API_KEY=""
export LLM_MOCK="${LLM_MOCK:-true}"
```
placed alongside the `export FINALLY_DB_PATH="${TMP_DB}"` line, so the script's outcome depends only on the code, not on what happens to be exported in the caller's shell.

### WR-05: Fragile ancestor-xpath locator for the P&L panel reduces test reliability

**File:** `test/tests/04-visualizations.spec.ts:32-37`
**Issue:**
```ts
const pnlHeading = page.getByText("P&L", { exact: true });
const pnlPanel = pnlHeading.locator("xpath=../.."); // heading -> header row -> panel root
```
Unlike every other locator in this test suite (which uses `getByTestId`), this one depends on the P&L panel's DOM nesting being exactly two levels above the heading text node. Any markup change that adds or removes a single wrapping element (e.g., wrapping the heading in an icon+text flex row) will silently make `pnlPanel` resolve to the wrong element — most likely still containing *some* `canvas` (since Lightweight Charts renders several canvases per pane, per the test's own comment), so the test could keep passing while checking the wrong panel's canvas instead of failing loudly. This directly affects test reliability, which is in-scope even for test files.
**Fix:** Add a `data-testid="pnl-panel"` (or similar) to the panel root in the frontend component and use `page.getByTestId("pnl-panel")` here instead of xpath ancestor traversal, consistent with the rest of the suite.

## Info

### IN-01: `start_mac.sh` browser auto-open has no Linux fallback despite claiming macOS/Linux support

**File:** `scripts/start_mac.sh:78-80`
**Issue:** The script's header comment and `stop_mac.sh`'s say "(macOS/Linux)", but the browser-open step only tries `open` (macOS-only):
```bash
if command -v open >/dev/null 2>&1; then
    open "http://localhost:${HOST_PORT}" 2>/dev/null || true
fi
```
On Linux this silently does nothing (no `xdg-open` fallback), so Linux users never get the browser auto-opened, only the printed URL. Not a functional break (the URL is printed either way), but worth a one-line fallback for parity with the stated platform support.
**Fix:**
```bash
if command -v open >/dev/null 2>&1; then
    open "http://localhost:${HOST_PORT}" 2>/dev/null || true
elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "http://localhost:${HOST_PORT}" 2>/dev/null || true
fi
```

### IN-02: Interpolating raw curl response bodies into Python triple-quoted string literals is fragile

**File:** `scripts/smoke.sh:99-108`, `scripts/verify_container.sh:86-93,123-130,163-170`
**Issue:** Multiple places embed a shell variable holding a JSON HTTP response body directly into a Python one-liner via triple-quote interpolation, e.g.:
```bash
python3 -c "
data = json.loads('''${WATCHLIST_BODY}''')
...
"
```
This works today because the API only returns tickers/numbers with no embedded quotes, but it's brittle: any future response value containing a single quote, backslash, or (extremely unlikely but possible) a literal `'''` sequence would break the Python parse or, in a worst case with unsanitized input reflected in a response, allow the interpolated text to break out of the string literal into arbitrary Python source. Since this is a local dev/CI script hitting a trusted local server, this isn't currently exploitable, but it's a pattern worth avoiding.
**Fix:** Pipe the body through stdin instead of interpolating it into source text:
```bash
echo "${WATCHLIST_BODY}" | python3 -c "
import json, sys
data = json.load(sys.stdin)
..."
```

---

_Reviewed: 2026-08-26T22:03:35Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
