---
phase: 03
slug: ai-copilot
status: verified
threats_open: 0
asvs_level: 1
created: 2026-08-26
---

# Phase 03 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| browser → `POST /api/chat` | Untrusted free-text user input crosses into the server | User-typed chat text |
| backend → OpenRouter/Cerebras | Outbound network call carrying portfolio figures, bearing `OPENROUTER_API_KEY` | Portfolio context, chat history, API bearer key |
| LLM response → application state | Untrusted model output crosses into a parser and into state-changing operations | Structured JSON (trades, watchlist changes) |
| application → SQLite (`chat_messages`) | Single-writer database shared with the trade path and the 30s snapshot task | Chat messages, executed-action JSON |
| LLM structured output → trade execution | Model-proposed tickers/sides/quantities cross into state-changing writes with no confirmation dialog | Trade requests |
| LLM structured output → watchlist mutation | Model-proposed tickers cross into the active ticker set | Watchlist mutations |
| test process → network | A test that silently reaches a real API or LLM turns a hermetic suite flaky/key-dependent | N/A (must be zero) |
| `uv add` / `npm install` | Supply-chain: new third-party dependencies enter the codebase | Package artifacts |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-03-01 | Tampering | `app/llm/client.py` — `model_validate_json` on raw response | high | mitigate | `try/except (ValidationError)` around `model_validate_json`, returns `None`, degrades to `GENERIC_RETRY_MESSAGE` with zero execution/persistence. Verified: `client.py:52-68`. | closed |
| T-03-02 | Information Disclosure | `app/llm/router.py`, `client.py` — error surface | high | mitigate | Degraded path returns only the fixed `GENERIC_RETRY_MESSAGE` constant; no raw exception text ever placed in the HTTP response. Verified: `router.py:29,132`, no raw exception echo found. | closed |
| T-03-03 | Information Disclosure | `client.py`, `router.py` — logging | medium | mitigate | Raw model output logged only at `logger.warning()`, truncated to 500 chars. Verified: `client.py:68`. | closed |
| T-03-04 | Denial of Service | `client.py` — synchronous `completion()` | high | mitigate | Wrapped in `asyncio.to_thread()`; single `timeout=30`, `max_tokens=1024`; no outer `asyncio.wait_for` (would orphan the thread). Verified: `client.py:36-37,52`, no outer wait_for. | closed |
| T-03-05 | Denial of Service | `persistence.py` — SQLite single-writer lock | high | mitigate | Two-transaction split (`BEGIN`/`COMMIT`/`ROLLBACK`), zero coroutine suspension points inside either block. Verified: `persistence.py:40,47,49`. | closed |
| T-03-06 | Tampering | `prompt.py` — user text placed in model context | medium | mitigate | User text is a separate `role="user"` message, never interpolated into `SYSTEM_PROMPT`; injected instructions still pass unmodified `execute_trade()` validation. Verified: `prompt.py:77`. | closed |
| T-03-07 | Spoofing | `POST /api/chat` — no authentication | low | accept | Single hardcoded `user_id="default"`, no login, explicitly out of scope per REQUIREMENTS.md; no multi-user boundary exists to spoof across. | closed (accepted) |
| T-03-08 | Information Disclosure | `chat_messages` growth / context window | low | accept | Fixed 20-row replay window; simulated money, single local user, no PII. | closed (accepted) |
| T-03-SC | Tampering | `uv add` / `npm install` supply chain | high | mitigate | Package-legitimacy gate (`gate="blocking-human"` checkpoint) presented and approved by the human before any of the 9 new packages were installed (03-01 Task 1). Verified: checkpoint executed and approved during this phase's execution. | closed |
| T-03-09 | Elevation of Privilege | `app/llm/executor.py` — LLM-path trade validation | high | mitigate | Calls the unmodified `execute_trade()` the manual endpoint calls; validation never re-implemented for the chat path. Verified: `executor.py:85`. | closed |
| T-03-10 | Tampering | `schemas.py` — model-proposed ticker | high | mitigate | `TradeAction.ticker`/`WatchlistChange.ticker` run `normalize_ticker` plus `^[A-Z.\-]+$` pattern validator. Verified: `schemas.py:18,34-38,49-53`. | closed |
| T-03-11 | Repudiation | `router.py` — actions payload construction | high | mitigate | HTTP `actions` object and persisted `chat_messages.actions` JSON built exclusively from `execute_actions` return values; model's proposed list never serialized. Verified: `router.py:78`, no `parsed.trades`/`parsed.watchlist_changes` in response construction. | closed |
| T-03-12 | Tampering | `executor.py` — transaction nesting | medium | mitigate | Neither loop opens an outer `BEGIN`; `execute_trade`/`apply_watchlist_change` each own their transaction. Verified: no `conn.execute("BEGIN")` in `executor.py`. | closed |
| T-03-13 | Denial of Service | `executor.py` — unbounded action count per turn | low | accept | Deliberately not capped (AI-SPEC §6); a cap would be defensive coding against an unobserved failure. | closed (accepted) |
| T-03-14 | Tampering | `backend/tests/**` — database targeting | medium | mitigate | Every test obtains its connection through the `initialized_db` fixture (`tmp_path`-scoped). Verified: used in `tests/portfolio/test_router.py`, `tests/watchlist/test_router.py`. | closed |
| T-03-15 | Information Disclosure | `frontend/**/*.test.tsx` — network access from tests | medium | mitigate | Every frontend test stubs `global.fetch` with `vi.fn()`; no test issues a real request. Verified: `WatchlistPanel.test.tsx`, `ChatDrawer.test.tsx`. | closed |
| T-03-16 | Denial of Service | `frontend/package.json` test script | low | mitigate | Script is `vitest run`, not bare `vitest`, so `npm test` exits with a status code instead of hanging in watch mode. Verified: `package.json:10`. | closed |
| T-03-17 | Tampering | `client.py` — structured-output validation gate | high | mitigate | Same control as T-03-01 (shared code path across 03-01/03-04); parametrized suite over 4 malformed-payload classes. | closed |
| T-03-18 | Denial of Service | `client.py` — request time budget | high | mitigate | Same control as T-03-04. | closed |
| T-03-19 | Information Disclosure | `router.py` — degraded-path response body | high | mitigate | Same control as T-03-02; timeout and malformed-output paths share the identical `GENERIC_RETRY_MESSAGE` body, asserted against the imported constant (not a duplicated literal). | closed |
| T-03-20 | Information Disclosure | `GET /api/chat/history` — response size/content | low | accept | Single hardcoded local user, simulated money, no PII; `limit` bounded at 200 via `Query(le=200)`. Verified: `router.py:114`. | closed |
| T-03-21 | Information Disclosure | `backend/scripts/llm_smoke_check.py` — key handling | medium | mitigate | Reads `OPENROUTER_API_KEY` from the environment, never prints it — only checks presence/absence and prints parse outcome. Verified: `scripts/llm_smoke_check.py:44-59`. It is a developer script, never a CI step. | closed |
| T-03-22 | Repudiation | `chat_messages` append-only log | low | accept | A resent message after a timeout appends a second user row rather than deduplicating — correct behavior for an append-only log; the failed turn executed nothing, so nothing can double-apply. | closed (accepted) |

*Status: open · closed · open — below `high` threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above `workflow.security_block_on` (`high`) count toward `threats_open`*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-03-01 | T-03-07 | Single-user local app, no login boundary exists to spoof across (explicitly out of scope per REQUIREMENTS.md) | Planner (03-01 threat model) | 2026-08-25 |
| AR-03-02 | T-03-08 | Fixed 20-row context window; simulated money, no PII | Planner (03-01 threat model) | 2026-08-25 |
| AR-03-03 | T-03-13 | Uncapped action count per turn is deliberate — capping would be defensive coding against an unobserved failure mode | Planner (03-02 threat model) | 2026-08-25 |
| AR-03-04 | T-03-20 | Chat history route has no PII exposure risk; bounded by `limit<=200` regardless | Planner (03-04 threat model) | 2026-08-25 |
| AR-03-05 | T-03-22 | Append-only log correctness, not a defect — a resent message cannot double-apply since the failed turn executed nothing | Planner (03-04 threat model) | 2026-08-25 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-08-26 | 23 | 23 | 0 | Claude (orchestrator, grep-verified against implementation; ASVS L1) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-08-26
