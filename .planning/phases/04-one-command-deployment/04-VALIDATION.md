---
phase: 4
slug: one-command-deployment
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-26
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

**Infra smoke (DEPLOY-01/02/03)**

| Property | Value |
|----------|-------|
| **Framework** | Shell smoke commands against `docker build`/`docker run` — no unit-testable business logic in this phase, infra behavior only |
| **Config file** | none — ad hoc commands per task, see Per-Task Verification Map |
| **Quick run command** | `docker build -t finally . && docker run --rm -d -p 8000:8000 --env-file .env finally && curl -f http://localhost:8000/api/health` |
| **Full suite command** | Same build/run, plus a trade via API, `docker stop`/`docker start`, re-`GET /api/portfolio`, assert unchanged (DEPLOY-02); each start/stop script run twice in a row asserting exit code 0 both times (DEPLOY-03) |
| **Estimated runtime** | ~60-90s (Docker build is the dominant cost; cached layers after the first build) |

**E2E (TEST-05)**

| Property | Value |
|----------|-------|
| **Framework** | Playwright (`@playwright/test`, pin to `1.62.1` or whatever `npm view @playwright/test version` returns at implementation time) |
| **Config file** | `test/playwright.config.ts` — none yet, Wave 0 |
| **Quick run command** | `cd test && npx playwright test --project=chromium` (against an already-running dev instance, for fast local iteration) |
| **Full suite command** | `docker compose -f test/docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from playwright` |
| **Estimated runtime** | ~2-4 minutes for the full compose build+run (Docker build + browser boot + 6 spec files) |

---

## Sampling Rate

- **After every task commit:** Run the quick-run command for the layer just touched — Docker smoke curl for Dockerfile/script tasks, `npx playwright test --project=chromium` against a locally-running dev instance for spec-file tasks
- **After every plan wave:** Run the full suite — Docker build/run/stop/restart smoke sequence, plus the full `docker compose -f test/docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from playwright`
- **Before `/gsd-verify-work`:** Full E2E suite must be green inside `docker-compose.test.yml`, plus the DEPLOY-01/02/03 manual smoke commands below must all pass
- **Max feedback latency:** ~4 minutes (dominated by the full Docker Compose E2E run; acceptable given this phase has no per-function unit-test layer to fall back on)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-T1 | 04-01 | 1 | DEPLOY-01 | T-04-01, T-04-06 | Multi-stage Dockerfile builds Next.js export + Python backend into one image serving :8000, no CORS | smoke (tracer) | `docker build -t finally . && docker run -d --name finally-tracer -v "$VD":/app/db -p 8010:8000 --stop-timeout 15 finally` then assert `/api/health`, `/`, `/api/watchlist`, `/api/stream/prices`, and no `/app/.env` in the image | ❌ W0 | ⬜ pending |
| 04-01-T2 | 04-01 | 1 | DEPLOY-02 | T-04-02, T-04-03 | `FINALLY_DB_PATH` set explicitly (not relying on `parents[3]` auto-detection); stop/start preserves cash, positions, trades, chat; bounded uvicorn shutdown | integration | `bash scripts/verify_container.sh && bash scripts/verify_container.sh` | ❌ W0 | ⬜ pending |
| 04-02-T1 | 04-02 | 2 | DEPLOY-03 | T-04-07, T-04-03 | Start/stop scripts idempotent on macOS/Linux; stop never destroys the data directory | smoke | `bash scripts/start_mac.sh && bash scripts/start_mac.sh && bash scripts/stop_mac.sh && bash scripts/stop_mac.sh && test -f db/finally.db` | ❌ W0 | ⬜ pending |
| 04-02-T2 | 04-02 | 2 | DEPLOY-03 | T-04-07 | PowerShell start/stop pair mirrors the bash contract branch for branch | static + manual | Filtered greps for `--stop-timeout 15`, `--timeout 15`, `LASTEXITCODE`, `Invoke-WebRequest`, and zero container/volume-remove subcommands; real-Windows idempotency run recorded as an end-of-phase human check | ❌ W0 | ⬜ pending |
| 04-03-T2 | 04-03 | 2 | TEST-05 | T-04-SC, T-04-05, T-04-08 | Compose harness: production image + pinned Playwright image, healthcheck-gated, mocked LLM, ephemeral DB | config | `docker compose -f test/docker-compose.test.yml config` | ❌ W0 | ⬜ pending |
| 04-03-T3 | 04-03 | 2 | TEST-05 | T-04-09 | Fresh start: seeded watchlist of 10, $10,000.00 cash, streaming prices | e2e | `docker compose -f test/docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from playwright` | ❌ W0 — no spec files exist in `test/` yet | ⬜ pending |
| 04-04-T1 | 04-04 | 3 | TEST-05 | T-04-05, T-04-09 | Watchlist add/remove; buy and sell with delta-based cash and position assertions | e2e | `docker compose -f test/docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from playwright` | ❌ W0 | ⬜ pending |
| 04-04-T2 | 04-04 | 3 | TEST-05 | T-04-08, T-04-09 | Heatmap and P&L chart rendering, AI chat with inline trade, SSE reconnection | e2e | `docker compose -f test/docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from playwright` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky. Task IDs/plan/wave columns are filled in by the planner once tasks are assigned — this table's requirement/command mapping is the fixed contract; the planner slots real task IDs into it.*

---

## Wave 0 Requirements

- [ ] `.dockerignore` — root-level, excludes `.env`, `.git`, `node_modules`, `db/`, `test/` artifacts (secrets must never enter a build-time `COPY`)
- [ ] `Dockerfile` — root-level, multi-stage (Node builder → Python builder → Python runtime, same Debian suite across Python stages)
- [ ] `scripts/start_mac.sh`, `scripts/stop_mac.sh`, `scripts/start_windows.ps1`, `scripts/stop_windows.ps1` — none exist yet
- [ ] `test/package.json` — Playwright devDependency; `@playwright/test` is flagged `[SUS]` (too-new version) by the package-legitimacy gate — requires a `checkpoint:human-verify` task before `npm install`
- [ ] `test/playwright.config.ts` — `baseURL` from `process.env.BASE_URL`, no `webServer` block (compose starts the app, not Playwright)
- [ ] `test/docker-compose.test.yml` — app + playwright services, `tmpfs: /app/db` for the app service (never the host bind mount)
- [ ] `test/tests/*.spec.ts` — one spec file per TEST-05 scenario (fresh-start, watchlist, trading, visualizations, chat, sse-reconnect)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cross-platform idempotency of the PowerShell start/stop scripts on real Windows + Docker Desktop | DEPLOY-03 | This research/planning/execution environment has no Windows host to run `.ps1` scripts against; the JSON-parsing/`$LASTEXITCODE` idempotency pattern is `[CITED]`-tier, not verified end-to-end on Windows | Run `start_windows.ps1` twice in a row on a Windows machine with Docker Desktop, confirm both runs exit 0 and the second is a no-op (container already running); repeat for `stop_windows.ps1` twice, confirm the data volume survives |
| Graceful-shutdown timing under a genuinely open SSE connection | DEPLOY-03 | Confirms the actual wall-clock behavior of `timeout_graceful_shutdown` + `docker stop --time`, not just that the flags are present in code | With the container running and a browser tab open on `http://localhost:8000` (SSE stream active), run `stop_mac.sh` and time it — it must resolve within the bounded window (~10-15s) without hanging or requiring a manual `docker kill` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 4 minutes
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
