# Phase 4 — API Coverage

No external API integration: this phase packages already-built application code into a Docker image, adds cross-platform start/stop lifecycle scripts, and stands up a containerized Playwright E2E harness — it introduces no new external API, SDK, or service client.

**Detector result (run at plan time):** `{"detected": false, "signals": []}` — `node .claude/gsd-core/bin/lib/api-coverage.cjs --json` over the Phase 4 ROADMAP scope.

**Why the surrounding vocabulary is not an integration:**
- Docker, Docker Compose, and the `mcr.microsoft.com/playwright` base image are build/runtime tooling, not an API surface this phase codes against.
- `@playwright/test` is a test runner consumed through its own test DSL, not a service integration; its capability surface is exercised by the six TEST-05 specs.
- The app's own `/api/*` routes, SSE stream, and chat endpoint were built and covered in Phases 1-3; this phase only serves them from a container and asserts them end to end.
- The two genuine external providers in this project (OpenRouter via LiteLLM, Massive/Polygon.io) were integrated in earlier phases. This phase runs the E2E suite with `LLM_MOCK=true` and `MASSIVE_API_KEY=""` precisely so neither provider is called.
