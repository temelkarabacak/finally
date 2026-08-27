---
phase: 3
slug: ai-copilot
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-25
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

**Backend**

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.0+ / pytest-asyncio 0.24.0+ / pytest-cov 5.0.0+ (already installed) |
| **Config file** | `backend/pyproject.toml:31-37` (`[tool.pytest.ini_options]`, `asyncio_mode = "auto"`) |
| **Quick run command** | `LLM_MOCK=true uv run --directory backend --extra dev pytest tests/llm -q` |
| **Full suite command** | `LLM_MOCK=true uv run --directory backend --extra dev pytest -q --cov=app` |
| **Estimated runtime** | ~5-10 seconds (hermetic, no network) |

**Frontend**

| Property | Value |
|----------|-------|
| **Framework** | vitest (not yet installed — Wave 0 install required) |
| **Config file** | `frontend/vitest.config.mts` (new, Wave 0) |
| **Quick run command** | `npm run test --prefix frontend -- --run <path>` |
| **Full suite command** | `npm test --prefix frontend` (`"test": "vitest run"` script, Wave 0) |
| **Estimated runtime** | ~5-15 seconds once configured |

---

## Sampling Rate

- **After every task commit:** Run the quick-run command for the module just touched (backend `pytest tests/llm -q` or frontend `vitest run <path>`)
- **After every plan wave:** Run both full suites — `pytest -q --cov=app` (backend) and `npm test` (frontend)
- **Before `/gsd-verify-work`:** Both full suites must be green, plus the hermeticity guard (`block_real_llm_calls` autouse fixture in `backend/tests/llm/conftest.py`) must pass
- **Max feedback latency:** ~15 seconds (both suites are hermetic — no network, no real LLM calls under `LLM_MOCK=true`)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-W0 | 01 | 0 | — | — | Wave 0 scaffolding (see below) | infra | n/a | ❌ W0 | ⬜ pending |
| 03-0x-xx | TBD | TBD | CHAT-01 | — | `POST /api/chat` returns one complete response, no streaming | integration | `pytest tests/llm/test_router.py -x` | ❌ W0 | ⬜ pending |
| 03-0x-xx | TBD | TBD | CHAT-02 | — | Trades auto-execute via existing validation, rejection reported inline | integration | `pytest tests/llm/test_executor.py -x` | ❌ W0 | ⬜ pending |
| 03-0x-xx | TBD | TBD | CHAT-03 | — | Watchlist changes auto-execute | integration | `pytest tests/llm/test_executor.py -x` | ❌ W0 | ⬜ pending |
| 03-0x-xx | TBD | TBD | CHAT-04 | — | History persists; user msg written pre-call, assistant msg post-success | unit | `pytest tests/llm/test_persistence.py -x` | ❌ W0 | ⬜ pending |
| 03-0x-xx | TBD | TBD | CHAT-05 | — | 30s timeout: no trade executed, nothing persisted | unit | `pytest tests/llm/test_client.py -x` (mocked `APITimeoutError`) | ❌ W0 | ⬜ pending |
| 03-0x-xx | TBD | TBD | CHAT-06 | — | `LLM_MOCK=true` yields deterministic pattern-matched responses | unit | `pytest tests/llm/test_mock.py -x` | ❌ W0 | ⬜ pending |
| 03-0x-xx | TBD | TBD | UI-08 | — | Chat drawer: collapsed default, loading state, inline confirmations | component | `vitest run components/ChatDrawer.test.tsx` | ❌ W0 | ⬜ pending |
| 03-0x-xx | TBD | TBD | TEST-02 | — | Malformed/partial structured-output degrades safely, never crashes | unit | `pytest tests/llm/test_schemas.py tests/llm/test_client.py -x` | ❌ W0 | ⬜ pending |
| 03-0x-xx | TBD | TBD | TEST-03 | — | Portfolio/watchlist/chat route status codes and response shapes | integration | `pytest tests/llm/test_router.py tests/portfolio/test_router.py tests/watchlist/test_router.py -x` | Partial (portfolio/watchlist exist; chat ❌ W0) | ⬜ pending |
| 03-0x-xx | TBD | TBD | TEST-04 | — | Frontend: price flash, watchlist CRUD, portfolio calc, chat rendering/loading | component | `vitest run` | ❌ W0 (no frontend tests exist yet at all) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky. Task IDs/plan/wave columns are filled in by the planner once tasks are assigned — this table's requirement/command mapping is the fixed contract; the planner slots real task IDs into it.*

---

## Wave 0 Requirements

- [ ] `backend/tests/llm/conftest.py` — `chat_client` fixture + `block_real_llm_calls` autouse fixture (monkeypatches `litellm.completion` to raise if invoked, per AI-SPEC §5's CI hermeticity guard)
- [ ] `backend/tests/llm/fixtures/chat_scenarios.py` — the 12 scenarios from AI-SPEC §5 (Reference Dataset), shared across `test_mock.py` and `test_router.py`
- [ ] `frontend/vitest.config.mts` + `frontend/vitest.setup.ts` — no frontend test runner exists at all yet
- [ ] `frontend/package.json` — add `"test": "vitest run"` script and the vitest/testing-library/jsdom devDependencies
- [ ] Delete `backend/app/llm/__pycache__/` and `backend/tests/llm/__pycache__/` — stale bytecode from an earlier, structurally different implementation attempt (non-ancestor commit `d4010c1`); remove before adding new source files to avoid confusion during review
- [ ] `uv add litellm pydantic` inside `backend/` — new runtime dependencies, not yet declared

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Action-report fidelity against a real (non-mock) LLM response, and context-grounding of prose commentary (AI-SPEC EV-1b/EV-4b) | CHAT-01, CHAT-02 | `LLM_MOCK=true` structurally cannot exercise the real `litellm` + `response_format` path (AI-SPEC §5's documented gap) — only a live call against `gpt-oss-120b` via Cerebras can confirm the schema survives the wire and the model's prose stays grounded | Set `OPENROUTER_API_KEY`, run the app with `LLM_MOCK` unset, send a handful of real chat turns covering a successful trade, a rejected trade, and a portfolio-analysis question; compare the assistant's prose against the `actions` JSON and the live portfolio state per AI-SPEC §5's "Live smoke check" |
| Chat panel visual/UX checkpoints (D-01 through D-11 from 03-CONTEXT.md: bottom-drawer overlay collapse, quick-prompt send-immediately, trade card vs. failed-card styling, timeout error bubble) | UI-08 | Visual/interaction polish is not meaningfully assertable by component tests alone | Open the app in a browser, exercise each CONTEXT.md decision by hand (open/collapse the drawer, click a quick-prompt, trigger a rejected trade, trigger a timeout) and confirm it matches the locked decision |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
