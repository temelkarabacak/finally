---
phase: 04-one-command-deployment
plan: 03
subsystem: testing
tags: [playwright, docker-compose, e2e, healthcheck, tmpfs]

requires:
  - phase: 04-01
    provides: The `finally` production image, DEPLOY-01/DEPLOY-02 Dockerfile with a real /api/health HEALTHCHECK, bounded uvicorn shutdown
provides:
  - Containerized E2E harness in test/ (package.json, playwright.config.ts, docker-compose.test.yml) that runs the actual production image, not a dev server
  - First TEST-05 scenario (fresh-start) proven end to end against the container
  - Confirmed the compose app service's ephemeral tmpfs database never touches the developer's real db/finally.db
affects: [04-04]

actuals:
  tokens: 1900
  tasks: 3
  commits: 2

tech-stack:
  added:
    - "@playwright/test@1.62.1 (devDependency in test/, approved via package-legitimacy checkpoint)"
    - "mcr.microsoft.com/playwright:v1.62.1-noble (pinned to the same version as the npm package)"
  patterns:
    - "Compose-paired E2E: app service builds the production Dockerfile with LLM_MOCK=true, empty MASSIVE_API_KEY, and a tmpfs-mounted /app/db; playwright service is gated on depends_on: condition: service_healthy against the real /api/health healthcheck, never a sleep"
    - "workers: 1 + fullyParallel: false + numbered spec filenames (01-fresh-start.spec.ts) so every spec sharing one seeded portfolio runs serially in a defined order"

key-files:
  created:
    - test/package.json
    - test/package-lock.json
    - test/playwright.config.ts
    - test/docker-compose.test.yml
    - test/.gitignore
    - test/tests/01-fresh-start.spec.ts
  modified: []

key-decisions:
  - "Task 1's package-legitimacy checkpoint for @playwright/test (gate=\"blocking-human\") was approved by the user before any npm install ran. Re-verified at implementation time: npm view @playwright/test version still returns 1.62.1, matching 04-RESEARCH.md's audited version exactly, so the npm devDependency and the mcr.microsoft.com/playwright image tag are pinned to the same string."
  - "Renamed the compose app service from the plan's literal \"app\" to \"webapp\": \"app\" is a Google-registered HSTS-preloaded gTLD compiled into Chromium's static preload list, so a bare Docker service named exactly \"app\" gets every http:// navigation force-upgraded to https:// by the browser, failing with net::ERR_SSL_PROTOCOL_ERROR against this plain-HTTP container. Reproduced twice during Task 3's own <verify> run before diagnosing the cause; fixed by renaming the service (BASE_URL now http://webapp:8000) rather than trying to disable the browser behavior, since HSTS preload enforcement is not affected by Chromium feature flags."
  - "Regenerated test/package-lock.json from a clean node_modules instead of trusting the lockfile written against a stray pre-existing node_modules already present in the test/ directory before this plan started -- that stale lockfile was missing the fsevents optional-dependency entry, which made `npm ci` fail inside the Playwright container with EUSAGE."

patterns-established:
  - "Compose service names in this project must avoid any string matching a registered HSTS-preloaded gTLD (app, dev, page, etc.) -- verified pitfall for any future compose file in this repo."

requirements-completed: [TEST-05]

coverage:
  - id: D1
    description: "Playwright project (test/package.json, playwright.config.ts) and docker-compose.test.yml pair the production image with the official Playwright container, gated on a real /api/health healthcheck"
    requirement: TEST-05
    verification:
      - kind: other
        ref: "docker compose -f test/docker-compose.test.yml config (exits 0, parses cleanly, webapp service has tmpfs but no volumes key, only playwright mounts test/)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Fresh-start E2E scenario passes against the running container: terminal-root visible, all 10 seeded tickers present, $10,000.00 cash shown, connection reaches open, and a watched ticker's price changes within a bounded 10s poll"
    requirement: TEST-05
    verification:
      - kind: e2e
        ref: "docker compose -f test/docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from playwright (run twice, both exit 0, 1 passed each time)"
        status: pass
    human_judgment: false
  - id: D3
    description: "The E2E suite never touches the developer's real db/finally.db -- the webapp service's database lives entirely on tmpfs"
    requirement: TEST-05
    verification:
      - kind: other
        ref: "md5sum/existence check on db/finally.db before and after both compose runs -- file absent in all four checks"
        status: pass
    human_judgment: false
  - id: D4
    description: "The one new npm package this phase introduces (@playwright/test) passed a human legitimacy gate before installation"
    requirement: TEST-05
    verification:
      - kind: other
        ref: "Task 1 checkpoint:human-verify, gate=\"blocking-human\" -- user responded \"approved\""
        status: pass
    human_judgment: true
    rationale: "Package-legitimacy approval is an explicit human decision by protocol (STATE.md's Phase 02/03 precedent); it is not something this executor can self-certify, only record as satisfied."

duration: 45min
completed: 2026-08-26
status: complete
---

# Phase 4 Plan 03: Containerized E2E Harness Summary

**Compose-paired Playwright E2E harness runs the actual `finally` production image against a real `/api/health` healthcheck, proving the fresh-start scenario (seeded 10-ticker watchlist, $10,000.00 cash, live SSE prices) end to end while never touching the developer's real database.**

## Performance
- **Duration:** 45min
- **Started:** 2026-08-26T23:05:00Z
- **Completed:** 2026-08-26T23:50:00Z
- **Tasks:** 3 completed (Task 1 checkpoint approved, Task 2 and Task 3 executed)
- **Files modified:** 6 created

## Accomplishments
- Task 1's package-legitimacy checkpoint for `@playwright/test` was approved by the user ("approved") before any install ran; re-verified `npm view @playwright/test version` still returns `1.62.1` at implementation time, matching 04-RESEARCH.md exactly
- `test/package.json`, `test/playwright.config.ts`, `test/docker-compose.test.yml`, and `test/.gitignore` stand up a full compose-paired E2E harness: the `webapp` service builds the actual `Dockerfile` (LLM_MOCK=true, empty MASSIVE_API_KEY, tmpfs `/app/db`) and the `playwright` service (pinned to `mcr.microsoft.com/playwright:v1.62.1-noble`) waits on `condition: service_healthy` against the real `/api/health` healthcheck
- `test/tests/01-fresh-start.spec.ts` proves the ROADMAP's fresh-start scenario against the running container: `terminal-root` visible, all 10 seeded tickers (`AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX`) present as watchlist rows, header shows `10,000.00` cash, connection indicator reaches `open`, and a watched ticker's displayed price changes within a bounded 10-second poll
- `docker compose -f test/docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from playwright` exits 0 twice in a row with 1 test passed each time, proving idempotency
- `db/finally.db` was absent before and after both compose runs, proving the E2E suite's tmpfs-mounted database never touches the developer's real portfolio file
- Discovered and fixed two real bugs during Task 3's own `<verify>` loop (see Deviations)

## Task Commits
1. **Task 1: Package-legitimacy gate for @playwright/test** - approved by user, no code changes of its own (gate satisfied before Task 2's install)
2. **Task 2: Playwright project and the compose-paired E2E harness** - `dc8faf6` (feat)
3. **Task 3: First E2E scenario — fresh start against the container** - `ba666fd` (feat)

**Plan metadata:** (pending — committed by the git_commit_metadata step)

## Files Created/Modified
- `test/.gitignore` - Excludes `node_modules/`, `playwright-report/`, `test-results/`, `.cache/`, `.npm/`
- `test/package.json` - `finally-e2e`, private, `"test": "playwright test"` script, `@playwright/test@^1.62.1` devDependency
- `test/package-lock.json` - Full npm lockfile including the `fsevents` optional-dependency entry (regenerated from a clean install)
- `test/playwright.config.ts` - `baseURL` from `BASE_URL`, single `chromium` project, `workers: 1`, `fullyParallel: false`, `forbidOnly: true`, no dev-server auto-start block
- `test/docker-compose.test.yml` - `webapp` service (production Dockerfile, `LLM_MOCK=true`, `MASSIVE_API_KEY=""`, `tmpfs: /app/db`, real healthcheck) + `playwright` service (pinned image, `depends_on: condition: service_healthy`, `npm ci && npx playwright test`)
- `test/tests/01-fresh-start.spec.ts` - Fresh-start E2E scenario against the container

## Decisions Made
- Task 1's `gate="blocking-human"` checkpoint for `@playwright/test` was approved by the user with evidence (56.9M weekly downloads, canonical `github.com/microsoft/playwright` repo, version `1.62.1`) before `npm install --save-dev @playwright/test` ran.
- Renamed the compose app service from the plan's literal `app` to `webapp` — see Deviations.
- Regenerated `test/package-lock.json` from a clean `node_modules` rather than the one produced against a stray pre-existing directory — see Deviations.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pre-existing `test/node_modules`, `.npm`, `playwright-report`, `test-results` were already committed to git**
- **Found during:** Task 2, immediately after adding `test/.gitignore`
- **Issue:** `git ls-files test/` showed 68 tracked files, all of them inside `node_modules/`, `.npm/`, `playwright-report/`, and `test-results/` — accidentally committed in the repo's very first commit (`f29bae3 Start of GSD process`), before any GSD phase execution began. A `.gitignore` alone cannot un-track already-committed files, so Task 2's own acceptance criterion (`git status --porcelain test/` shows no `node_modules`/`playwright-report`/`test-results` entries) would have failed without a fix.
- **Fix:** `git rm -r --cached test/node_modules test/.npm test/playwright-report test/test-results`, keeping the working-tree files (harmless local build artifacts) but removing them from the index so the new `.gitignore` takes effect going forward.
- **Files modified:** git index only (no source file changes)
- **Verification:** `git status --porcelain test/` clean after commit
- **Commit:** `dc8faf6`

**2. [Rule 1 - Bug] Stale `test/package-lock.json` missing the `fsevents` optional-dependency entry**
- **Found during:** Task 3's `<verify>` — first full compose run
- **Issue:** `npm ci` inside the `playwright` container failed with `EUSAGE: Missing: fsevents@2.3.2 from lock file`. The lockfile had been generated by `npm install --save-dev @playwright/test` running against the stray pre-existing `node_modules` from Task 2 (see Deviation 1), which already contained `playwright`'s files but not a fully-resolved `fsevents` optional-dependency record, producing an internally-inconsistent lockfile that passed a plain `npm install` but failed `npm ci`'s stricter sync check.
- **Fix:** Deleted `test/node_modules` and `test/package-lock.json`, then re-ran `npm install --save-dev @playwright/test` from a clean state. Verified locally with `npm ci` before re-running the full compose suite.
- **Files modified:** `test/package-lock.json`
- **Verification:** `npm ci` succeeds locally; full compose suite's `playwright` service `npm ci` step succeeds
- **Commit:** `ba666fd`

**3. [Rule 1 - Bug] Compose service named `app` triggered a forced HTTPS upgrade, breaking navigation**
- **Found during:** Task 3's `<verify>` — first and second full compose run (after fixing Deviation 2)
- **Issue:** `page.goto("/")` against `http://app:8000/` failed with `net::ERR_SSL_PROTOCOL_ERROR`, and the `app` container's uvicorn log showed `WARNING: Invalid HTTP request received` at the same moment — the unmistakable signature of a TLS ClientHello arriving at a plain-HTTP server. Root cause: `.app` is a Google-registered top-level domain that Google requires to be HSTS-preloaded across the entire TLD as a condition of registry operation; Chromium ships this in its compiled-in static preload list, so any hostname matching `app` (the bare TLD apex, which is exactly what a Docker Compose service literally named `app` resolves as) gets every `http://` navigation force-upgraded to `https://` before the request ever leaves the browser. Attempting `--disable-features=HttpsUpgrades` in `launchOptions.args` had no effect, confirming this is HSTS preload enforcement (which Chromium does not gate behind that feature flag), not the separate "HTTPS-Upgrades" heuristic.
- **Fix:** Renamed the compose service from `app` to `webapp` (and its `depends_on`/`BASE_URL` references) rather than fighting browser-level HSTS enforcement. This is a deviation from the plan's literal prose (which named the service `app`) but not from any `<acceptance_criteria>` grep pattern — none of Task 2's or Task 3's automated checks reference the literal string `app` as a service key.
- **Files modified:** `test/docker-compose.test.yml`
- **Verification:** Full compose suite passes twice in a row after the rename (`docker compose ... up --build --abort-on-container-exit --exit-code-from playwright` exits 0 both times, 1 test passed each run)
- **Commit:** `ba666fd`

**Total deviations:** 3 auto-fixed (all Rule 1 — bugs blocking task completion). **Impact:** All three were required for Task 2/Task 3's own acceptance criteria and `<verify>` gates to pass; none represent scope creep beyond what this plan's tasks already specified. The compose service rename is worth carrying forward as a named pattern (see `patterns-established`) for the 04-04 wave.

## Issues Encountered
None beyond the three deviations above, all resolved within this plan.

## User Setup Required
None - the package-legitimacy approval for `@playwright/test` was the only human input this plan required, and it was already provided.

## Next Phase Readiness
The E2E harness (`test/package.json`, `test/playwright.config.ts`, `test/docker-compose.test.yml`, `test/tests/01-fresh-start.spec.ts`) is proven end to end against the real production image. Ready for 04-04 (Wave 3), which adds `test/tests/02-watchlist.spec.ts` through `06-sse-reconnect.spec.ts` on top of this same harness — those specs should use `BASE_URL: http://webapp:8000` (not `app`) and follow the same numbered-filename, serial-execution convention established here.

---
*Phase: 04-one-command-deployment*
*Completed: 2026-08-26*
