---
phase: 04
slug: one-command-deployment
status: verified
threats_open: 0
asvs_level: 1
created: 2026-08-27
---

# Phase 04 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| host `.env` → container process env | Secrets cross here at `docker run` time only; they must never cross at `docker build` time | `OPENROUTER_API_KEY`, `MASSIVE_API_KEY` |
| container writable layer → host `db/` bind mount | The only durable data path; a misrouted DB path silently discards user state | Portfolio, trade history, chat history |
| host Docker daemon → container lifecycle signals | SIGTERM/SIGKILL crossing into a process holding long-lived SSE connections | N/A (process signals) |
| npm registry → `test/node_modules` | A new third-party package enters the developer's machine and the CI path | Package artifacts (`@playwright/test`) |
| test app container `/app/db` → host filesystem | Must be a one-way dead end; any host mount here exposes real user data to test mutation | N/A (must be zero — verified as tmpfs) |
| host environment → compose app service env | Host-set `MASSIVE_API_KEY` / `OPENROUTER_API_KEY` must not leak into the test container and make the suite non-deterministic or network-dependent | Environment variables |
| Playwright suite result → phase verification verdict | A vacuous green run would falsely certify the milestone as complete | N/A (test integrity) |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-04-01 | Information Disclosure | `Dockerfile` / build context, start scripts' `--env-file` handling | high | mitigate | `.dockerignore` excludes `.env` and `.env.*`; no build instruction copies an environment file; secrets pass only via `--env-file` at `docker run` time, never as `-e KEY=value` (visible in `docker inspect`/process table). Verified: `.dockerignore` contains `.env`/`.env.*`; `docker run --rm -d finally` + inspecting the built image confirmed no `/app/.env`. | closed |
| T-04-02 | Tampering | SQLite path resolution (`backend/app/db/connection.py`) | high | mitigate | `ENV FINALLY_DB_PATH=/app/db/finally.db` set explicitly in the Dockerfile's runtime stage, overriding the source-tree-relative `parents[3]` auto-detection that would otherwise resolve to the wrong path once `backend/` is flattened into `/app`. Verified: `Dockerfile` contains `ENV FINALLY_DB_PATH=/app/db/finally.db`; live restart-persistence proof via `scripts/verify_container.sh` (cash/position identical pre/post restart, twice). | closed |
| T-04-03 | Denial of Service (self-inflicted) | uvicorn shutdown with open SSE connections | medium | mitigate | `--timeout-graceful-shutdown 10` in the Dockerfile `CMD`, paired with `--stop-timeout 15` at `docker run` time (and `--timeout 15` on `docker stop`), so Uvicorn's own bounded cancellation resolves before Docker's SIGKILL backstop. Verified: `Dockerfile` CMD and `scripts/start_mac.sh` both contain the flags; live-measured `docker stop --timeout 15` at 11-13s across multiple runs with a live SSE connection open, well under the 15-20s ceiling. | closed |
| T-04-04 | Elevation of Privilege | container default user (root), in both the production image and the test containers | low | accept | Single-user, localhost-only educational deployment; a hardcoded non-root UID breaks writes to a bind mount owned by an arbitrary host user across students' machines (04-RESEARCH.md Open Question 2). Test containers are additionally ephemeral with no durable state. Revisit before any non-local deployment. | closed (accepted) |
| T-04-05 | Tampering | E2E run versus the developer's real `db/finally.db` | high | mitigate | `tmpfs: /app/db` on the compose app service (`webapp`); the service mounts no host path for `/app/db` at all, so the E2E suite (including live buy/sell trades) can never reach the developer's real portfolio. Verified: `test/docker-compose.test.yml` contains `tmpfs: [/app/db]` with no competing `volumes:` entry; host `db/finally.db` MD5 checksum identical before and after two independent full-suite runs. | closed |
| T-04-06 | Information Disclosure | `/api/health` and the image `HEALTHCHECK` | low | accept | `backend/app/main.py:79-89`'s docstring and implementation confirm the handler returns only `{"status": "ok", "market_source": ...}` — never the API key, a file path, or a version; the Dockerfile `HEALTHCHECK` reads only that endpoint. Verified: read `main.py:77-89` directly this session. | closed (accepted — already-true prior-phase control, re-confirmed) |
| T-04-07 | Denial of Service (data loss) | `scripts/stop_mac.sh`, `scripts/stop_windows.ps1` | high | mitigate | Stop scripts issue a bounded container-stop only, never a container or volume removal. Verified: `grep -cE "docker rm|volume rm" scripts/stop_mac.sh` and the PowerShell equivalent both return `0`; `db/finally.db` confirmed present and unchanged after two consecutive stop runs. | closed |
| T-04-08 | Information Disclosure | compose app service environment (outbound LLM/market-data calls during E2E) | medium | mitigate | `LLM_MOCK: "true"` and `MASSIVE_API_KEY: ""` set explicitly on the `webapp` compose service so no host secret is inherited and no outbound OpenRouter/Massive call is made during the suite — the chat spec exercises `backend/app/llm/mock.py` only. Verified: `test/docker-compose.test.yml` contains both env entries. | closed |
| T-04-09 | Spoofing (false verification signal) | Playwright suite integrity | medium | mitigate | `forbidOnly: true` in `playwright.config.ts` plus filtered negative greps for focused (`.only`) and skipped (`.skip`) tests across all six specs, so a green run cannot mean "the scenario was never executed." Verified: `grep "forbidOnly" test/playwright.config.ts` returns `forbidOnly: true`; live full-suite runs (twice) reported 6/6 passed with zero skips. | closed |
| T-04-SC | Tampering | `npm install --save-dev @playwright/test` in `test/` (supply chain) | high | mitigate | Package-legitimacy gate: 04-03 Task 1 is a `gate="blocking-human"` checkpoint presenting the `[SUS]`-flagged (recency heuristic) verdict, the 56.9M weekly-download figure, and the canonical `microsoft/playwright` repo before any install ran. Never auto-approvable in any mode, including auto-advance. Verified: checkpoint was presented to and explicitly approved by the human this session before the executor's install task ran. | closed |

*Status: open · closed · open — below `high` threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above `workflow.security_block_on` (`high`) count toward `threats_open`*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-04-01 | T-04-04 | Root-in-container is a common, imperfect ASVS V14 finding; a fixed non-root UID would break writes to a bind mount owned by an arbitrary host user across students' machines. Acceptable for a single-user, local-only, no-multi-tenant educational deployment. Revisit before any non-local deployment. | Claude (gsd-security-auditor role, per 04-RESEARCH.md Open Question 2 and all four plans' own threat models) | 2026-08-27 |
| AR-04-02 | T-04-06 | `/api/health` already returns a minimal, non-sensitive payload as of Phase 1; this phase's Docker `HEALTHCHECK` reuses that endpoint unchanged, so no new exposure is introduced. | Claude (gsd-security-auditor role) | 2026-08-27 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-08-27 | 10 | 10 | 0 | Claude (grep-depth + live-evidence verification at ASVS L1; register authored at plan time by gsd-planner across all four 04-*-PLAN.md threat models, deduplicated by Threat ID) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-08-27
