# Phase 3 — External API Coverage Matrix

> Produced by the API Coverage Decision Checkpoint (`workflow.api_coverage_gate: true`).
> Full coverage is the default; every `OPT-OUT` carries a one-line reason.

## Detector result

`node gsd-core/bin/lib/api-coverage.cjs` returned `detected: false` when run against the bare
ROADMAP Phase 3 section (the section's prose happens to avoid the trigger vocabulary), and
`detected: true` when run against representative plan-body text for this phase
(signals: `integrate`/`api`, `integrate`/`sdk`, `wires`/`endpoint`, `wires`/`rest`,
`consuming`/`api`, surface `api`, surface `sdk`). This phase demonstrably adds a **new external
API integration** — OpenRouter chat completions via the LiteLLM SDK — so the matrix is produced
rather than skipped.

**Scope:** only the NEW external surface this phase adds. The Massive / Polygon.io market-data
surface predates this phase (Phases 1–2, already shipped with permanent simulator failover) and
is out of scope for this matrix.

## Surface: OpenRouter API (via `litellm.completion()`)

| capability | decision | reason |
|---|---|---|
| `POST /chat/completions` (non-streaming completion) | `INTEGRATE` | |
| `response_format` structured outputs (Pydantic model) | `INTEGRATE` | |
| `provider.order` routing (Cerebras) via `extra_body` | `INTEGRATE` | |
| `reasoning_effort` generation control | `INTEGRATE` | |
| `max_tokens` generation bound | `INTEGRATE` | |
| `timeout` / request cancellation | `INTEGRATE` | |
| multi-turn `messages[]` history (system + context + turns) | `INTEGRATE` | |
| error surface (`APITimeoutError` and sibling `openai.*` mappings) | `INTEGRATE` | |
| streaming completions (`stream: true`) | `OPT-OUT` | explicitly out of scope — REQUIREMENTS.md "Out of Scope" and PLAN.md §9 rule out token-by-token streaming; the response must be validated as complete JSON before any trade executes |
| tool / function calling (`tools[]`, `tool_choice`) | `OPT-OUT` | not needed — AI-SPEC §1 classifies this as Conversational with server-side auto-execution, not an agentic tool loop; the model's only "tool" is its structured `trades[]`/`watchlist_changes[]` output |
| sampling parameters (`temperature`, `top_p`, `seed`) | `OPT-OUT` | not needed — AI-SPEC §4 keeps provider defaults; this is a deterministic-schema task, not a creative one |
| multimodal input (images, audio, files) | `OPT-OUT` | not needed — chat is text-only per PLAN.md §10 |
| embeddings endpoint | `OPT-OUT` | not needed — no retrieval anywhere in this system (AI-SPEC §1: not RAG) |
| `GET /models` model listing / discovery | `OPT-OUT` | not needed — the model is fixed to `openrouter/openai/gpt-oss-120b` by PLAN.md §9 and the cerebras skill |
| fallback model routing (`models[]` array) | `OPT-OUT` | not needed yet — AI-SPEC §2 records a raw-`httpx` fallback plan for schema unreliability instead of a second model |
| prompt caching | `OPT-OUT` | explicitly out of scope — AI-SPEC §4b rules it out by design: every turn's prompt carries live portfolio numbers, so cache hits would serve stale state |
| web-search plugin / online model variants | `OPT-OUT` | not needed — out of phase scope; no external research surface in the chat product |
| `GET /generation` per-generation metadata lookup | `OPT-OUT` | not needed — AI-SPEC §7's per-turn structured log line covers the observability need without a second network call |
| `GET /credits` / usage + cost accounting | `OPT-OUT` | not needed yet — single-user demo at well under $0.001 per turn (AI-SPEC §4b); `max_tokens` already bounds worst case |
| API-key provisioning / management API | `OPT-OUT` | not needed — one `OPENROUTER_API_KEY` supplied via `.env`, per PLAN.md §5 |
| BYOK / per-provider credential passthrough | `OPT-OUT` | not needed — single OpenRouter key, no direct provider accounts |
| Zero-Data-Retention / privacy policy headers | `OPT-OUT` | not needed — simulated money, single local user, no real PII crosses the boundary (AI-SPEC §1b: no regulatory context) |

## Schema Push Detection

Scanned the phase scope for the matched ORM patterns (Prisma / Drizzle / Payload / Supabase /
TypeORM). No match: this project uses hand-written SQLite DDL (`backend/app/db/schema.sql`) with
lazy `init_db()` initialization, and the `chat_messages` table this phase consumes **already
exists and is already created/seeded** (Phase 1). No schema change and therefore no schema-push
task is injected.

## Assumption-Delta

`gsd_run query assumption-delta scan 03 --json` returned `detected: false`. Checkpoint skipped
silently, as specified.
