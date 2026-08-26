---
phase: 04-one-command-deployment
plan: 02
subsystem: infra
tags: [docker, deployment, lifecycle-scripts, powershell, bash]

requires:
  - phase: 04-01
    provides: "finally Docker image, --stop-timeout/--timeout-graceful-shutdown contract, FINALLY_DB_PATH bind-mount convention"
provides:
  - "scripts/start_mac.sh / scripts/stop_mac.sh -- idempotent macOS/Linux one-command lifecycle for the finally container"
  - "scripts/start_windows.ps1 / scripts/stop_windows.ps1 -- branch-for-branch PowerShell port of the same lifecycle contract"
affects: [04-03, 04-04]

actuals:
  tokens: 1800
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Docker container lifecycle state resolved via exit-code branching (if STATE=\"$(docker inspect ... 2>/dev/null)\"; then ... else STATE=absent; fi) rather than piping a possibly-empty/garbled stdout into an `|| echo` fallback, which a Docker CLI stdout quirk on inspect-of-nonexistent-object can silently corrupt"
    - "PowerShell lifecycle scripts check $LASTEXITCODE immediately after docker info/inspect probes instead of parsing their captured output, sidestepping the same class of bug"

key-files:
  created:
    - scripts/start_mac.sh
    - scripts/stop_mac.sh
    - scripts/start_windows.ps1
    - scripts/stop_windows.ps1
  modified: []

key-decisions:
  - "Rule 1 bug fix: docker inspect -f '{{.State.Running}}' <nonexistent> on this host's Docker CLI (29.3.1) prints a stray blank line to stdout before failing with a non-zero exit code. The original STATE=\"$(docker inspect ... 2>/dev/null || echo absent)\" pattern concatenated that blank line with the echo fallback into the literal string \"\\nabsent\", which matched none of the case statement's patterns (true/false/absent) and silently skipped container creation entirely. Fixed by branching on the docker inspect command's own exit status via an if/else, never mixing its (possibly-corrupted) stdout with a fallback string in the same capture."
  - "PowerShell scripts already used the exit-code-first design from the start (per 04-RESEARCH.md Assumption A2's guidance to check $LASTEXITCODE rather than trust inspect's string output), so they were not subject to the same bug."

patterns-established:
  - "Lifecycle state detection: never combine a failing command's own (possibly non-empty) stdout with a shell-level `|| echo fallback` in one capture -- branch on exit status explicitly instead."

requirements-completed: [DEPLOY-03]

coverage:
  - id: D1
    description: "scripts/start_mac.sh and scripts/stop_mac.sh implement an idempotent macOS/Linux lifecycle: build gate, optional --env-file, three-state branch (running/stopped/absent), health poll, bounded --stop-timeout 15 / --timeout 15, never remove the container or touch db/"
    requirement: DEPLOY-03
    verification:
      - kind: other
        ref: "bash scripts/stop_mac.sh; bash scripts/start_mac.sh && bash scripts/start_mac.sh && test exactly one running finally-app container && curl /api/health && bash scripts/stop_mac.sh && bash scripts/stop_mac.sh && test -f db/finally.db (plan's <automated> verify, run live against Docker 29.3.1)"
        status: pass
      - kind: other
        ref: "grep-based acceptance criteria: docker info preflight present, --stop-timeout 15 / --timeout 15 literal, no docker rm/volume rm in stop_mac.sh, both scripts executable, start succeeds with .env absent"
        status: pass
    human_judgment: false
  - id: D2
    description: "scripts/start_windows.ps1 and scripts/stop_windows.ps1 branch-for-branch mirror the bash pair's contract (docker preflight, build gate, optional env file, three-state lifecycle via $LASTEXITCODE, Invoke-WebRequest health poll, bounded stop, no container/volume removal)"
    requirement: DEPLOY-03
    verification:
      - kind: other
        ref: "Static grep-based acceptance criteria (all 9 checks in 04-02-PLAN.md Task 2): $ErrorActionPreference=\"Stop\" on line 1, docker info present, --stop-timeout 15 / --timeout 15 literal, db:/app/db literal, LASTEXITCODE present, no docker rm/volume rm, Invoke-WebRequest present -- all passed"
        status: pass
    human_judgment: true
    rationale: "No Windows/Docker Desktop host is available in this environment to execute the .ps1 files; pwsh itself is also unavailable for a syntax-only dry run. The plan's own <verify><human-check> queues the real-Windows idempotency run as an end-of-phase human check, consistent with 04-RESEARCH.md Assumption A2 rating this PowerShell pattern [ASSUMED]-tier pending a real-Windows smoke test."

duration: 20min
completed: 2026-08-26
status: complete
---

# Phase 4 Plan 02: One-Command Lifecycle Scripts Summary

**Idempotent macOS/Linux (`start_mac.sh`/`stop_mac.sh`) and Windows (`start_windows.ps1`/`stop_windows.ps1`) lifecycle scripts for the `finally` container, with a real Docker-CLI-quirk bug caught and fixed live during acceptance verification.**

## Performance
- **Duration:** 20min
- **Started:** 2026-08-26T22:22:00Z
- **Completed:** 2026-08-26T22:42:50Z
- **Tasks:** 2 completed
- **Files modified:** 4 (4 created, 0 modified)

## Accomplishments
- `scripts/start_mac.sh` builds the `finally` image only when missing (or `--build` is passed), runs `finally-app` with the `db/` bind mount and `--stop-timeout 15`, includes `--env-file .env` only when present (printing a non-blocking notice otherwise), polls `/api/health` for up to 20s, and best-effort opens a browser
- `scripts/stop_mac.sh` issues a bounded `docker stop --timeout 15` only -- never `docker rm`/`volume rm` -- and always exits 0
- Live-verified against real Docker (29.3.1) on this host: `stop -> start -> start -> assert one container + healthy -> stop -> stop -> assert db/finally.db survives` all passed, including the no-`.env`-present path (the worktree has no `.env` file, so this was exercised naturally rather than simulated)
- `scripts/start_windows.ps1` / `scripts/stop_windows.ps1` are a branch-for-branch PowerShell port: `$LASTEXITCODE` checked immediately after `docker info`/`docker inspect` (per 04-RESEARCH.md Assumption A2's guidance), `Invoke-WebRequest` for the health poll (not the `curl` alias), same `--stop-timeout 15` / `--timeout 15` bound
- Found and fixed a real bug during Task 1's acceptance-criteria gate (not a hypothetical): this host's Docker CLI (29.3.1) emits a blank line to stdout when `docker inspect` targets a nonexistent container, which corrupted the original `STATE="$(docker inspect ... 2>/dev/null || echo absent)"` capture into the literal string `"\nabsent"` -- matching none of the `case` statement's patterns and silently skipping container creation. Root-caused with a hexdump of the captured variable, then fixed by branching on the command's own exit status instead of parsing its output.

## Task Commits
1. **Task 1: macOS/Linux start and stop scripts** - `5fd63fe` (feat)
2. **Task 2: Windows PowerShell start and stop scripts** - `0014cb5` (feat)

**Plan metadata:** (pending -- committed by the git_commit_metadata step)

## Files Created/Modified
- `scripts/start_mac.sh` - Idempotent build-and-run: Docker preflight, build gate, optional `--env-file`, three-state lifecycle branch (running/stopped/absent) resolved via exit-code, `db/` bind mount, `--stop-timeout 15`, bounded health poll, best-effort browser open
- `scripts/stop_mac.sh` - Bounded `docker stop --timeout 15` only, never a remove subcommand, always exits 0
- `scripts/start_windows.ps1` - PowerShell port of `start_mac.sh`; `$LASTEXITCODE`-based state detection, `Invoke-WebRequest` health poll, `$PSScriptRoot`-based repo-root resolution
- `scripts/stop_windows.ps1` - PowerShell port of `stop_mac.sh`; same bounded-stop-only contract

## Decisions Made
- Fixed the docker-inspect-blank-line bug (see Key Decisions in frontmatter) by branching on exit status rather than mixing a failing command's stdout with a shell `||` fallback string in one capture -- applied to both `start_mac.sh` and `stop_mac.sh` for consistency, even though `stop_mac.sh`'s original `case ... *)` catch-all happened to mask the bug there.
- Left the already-stopped `finally-app` container in place after verification (rather than removing it) since removing containers is explicitly out of scope for this plan's scripts and there is no requirement to leave a pristine Docker state between plans.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `docker inspect` blank-stdout-line corrupting lifecycle state detection**
- **Found during:** Task 1, running the plan's own `<automated>` verify command
- **Issue:** `STATE="$(docker inspect -f '{{.State.Running}}' "${NAME}" 2>/dev/null || echo "absent")"` produced the literal 7-character string `"\nabsent"` (confirmed via `xxd`) when `finally-app` did not yet exist, because this host's Docker CLI (29.3.1) writes an empty line to stdout before failing on an inspect of a nonexistent object. The `case` statement's three patterns (`true`/`false`/`absent`) never matched this corrupted value, so the `absent)` branch's `docker run` was never executed, and the script hung waiting on a health check against a container that was never created.
- **Fix:** Replaced the single-capture-with-fallback pattern with an explicit `if STATE="$(docker inspect ... 2>/dev/null"); then ...; else STATE="absent"; fi`, so a failing inspect never contributes its stdout to `STATE` at all. Applied identically to `start_mac.sh` and `stop_mac.sh`.
- **Files modified:** `scripts/start_mac.sh`, `scripts/stop_mac.sh`
- **Verification:** Full plan `<automated>` verify sequence re-run end to end after the fix -- `stop` (not-running) -> `start` (creates) -> `start` (idempotent, one running container) -> health check passes -> `stop` -> `stop` (idempotent) -> `db/finally.db` present. All steps passed.
- **Commit:** `5fd63fe`

**Total deviations:** 1 auto-fixed (Rule 1, bug). **Impact:** Without this fix, `start_mac.sh` would have silently failed to ever start a container from a clean state on any Docker CLI version that shares this blank-stdout-on-failed-inspect behavior -- a correctness-blocking bug in the plan's core idempotency contract, caught only because the executor ran the plan's own automated verify command rather than trusting the code by inspection.

## Issues Encountered
None beyond the deviation documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
`scripts/start_mac.sh`, `scripts/stop_mac.sh`, `scripts/start_windows.ps1`, and `scripts/stop_windows.ps1` are all in place, executable where applicable, and the bash pair is live-verified against this host's Docker Engine. The PowerShell pair is statically verified (all grep-based acceptance criteria pass) with its real-Windows idempotency run correctly queued as an end-of-phase human check per the plan's own `<verify><human-check>` and 04-RESEARCH.md Assumption A2. Ready for 04-03 (Wave 3) once 04-03 also completes.

## Self-Check: PASSED

- FOUND: scripts/start_mac.sh
- FOUND: scripts/stop_mac.sh
- FOUND: scripts/start_windows.ps1
- FOUND: scripts/stop_windows.ps1
- FOUND: commit 5fd63fe (Task 1)
- FOUND: commit 0014cb5 (Task 2)
- FOUND: commit 3159dcd (plan metadata)

---
*Phase: 04-one-command-deployment*
*Completed: 2026-08-26*
