# Phase 3: AI Copilot - Context

**Gathered:** 2026-08-25
**Status:** Ready for planning

<domain>
## Phase Boundary

A user converses with an AI assistant docked in the terminal UI. The assistant is grounded in the user's live cash, positions/P&L, and watchlist prices; it can auto-execute trades and watchlist changes through the same validation as manual actions, with results (success or rejection) confirmed inline in the chat. Conversation history persists across reloads (last 20 messages sent to the LLM). A 30-second timeout aborts with a generic retry message and no trade. With `LLM_MOCK=true`, the backend returns deterministic responses so the full backend/frontend unit suites (TEST-02, TEST-03, TEST-04) run offline and green. Docker packaging and E2E tests are Phase 4 — this phase is chat, LLM integration, and the test suites the mock mode unlocks.

</domain>

<decisions>
## Implementation Decisions

### Chat panel placement & collapse
- **D-01:** The AI chat panel is a bottom drawer, not a left/right sidebar — slides up from the bottom edge of the screen.
- **D-02:** The drawer overlays (floats) on top of the existing grid rather than pushing/reflowing the watchlist/chart/portfolio layout — simpler to implement, accepted tradeoff that it can obscure content underneath while open.
- **D-03:** Collapsed by default on first page load — the user sees the full trading grid first and opens chat via a toggle. Matches PLAN.md's "docked/collapsible" language and keeps the first impression focused on live prices, not the AI feature.

### Inline action confirmations
- **D-04:** A successful AI-executed trade renders as a summary card inline in the chat (ticker, side, quantity, fill price) — visually distinct from conversational text, not just a sentence.
- **D-05:** A rejected trade (failed validation — insufficient cash/shares) reuses the same summary card component but styled as failed (e.g. red border / "REJECTED" label), rather than falling back to plain error text. — **Reversibility:** reversible — a card-styling variant, easy to restyle later.
- **D-06:** AI-executed watchlist changes (add/remove ticker) get simpler treatment than trades — plain text in the assistant's reply, no card. Watchlist changes are lower-stakes (no money moves) than trades.

### Chat starter experience
- **D-07:** On first opening the (empty) chat, the user sees suggested quick-prompt buttons (e.g. "Analyze my portfolio", "What should I buy?") above the input, not just an empty input or a canned greeting.
- **D-08:** Clicking a quick-prompt sends it immediately rather than just filling the input box — consistent with the app's existing zero-friction, no-confirmation-dialog philosophy already established for manual trades.

### Timeout / retry UX
- **D-09:** The 30-second timeout's generic retry message renders as an error bubble inline in the chat thread (assistant-message-style), not a toast/banner — consistent with how normal replies render, no new UI pattern needed.
- **D-10:** The user's original message stays in the input box after a timeout so they can resend with one click, rather than being cleared.

### Mock mode demo behavior
- **D-11:** With `LLM_MOCK=true`, mock responses are pattern-recognizing (a small keyword/rule-based matcher — e.g. "buy"/"sell"/ticker mentions → a structured mock trade response; "portfolio"/"analyze" → mock analysis text) rather than one fixed canned response regardless of input. This lets mock mode exercise the trade-execution and watchlist-change paths for TEST-02/03/04 (and Phase 4's E2E "AI chat with an inline trade" scenario) without a live OpenRouter call. — **Reversibility:** costly — TEST-02/03/04 and the Phase 4 E2E chat scenario are written against whatever mock pattern rules ship here; changing the rule set later means updating those test expectations too.

### Claude's Discretion
The following were not raised during discussion — Claude's judgment applies, informed by PLAN.md and existing Phase 1/2 patterns:
- **Message bubble styling** — how user vs. assistant messages are visually distinguished (alignment, color-coding using the locked theme tokens). Was offered as a discussable area in the second round but not selected.
- **System prompt wording/tone** — PLAN.md §9 already specifies "FinAlly, an AI trading assistant... concise and data-driven"; exact phrasing is implementation detail.
- **Exact mock-mode pattern rules** — which keywords/phrases map to which mock trades/responses (D-11 locks the *approach*, not the specific rule table). Left to planner/researcher, informed by what TEST-02/03/04 and Phase 4's E2E chat scenario need to exercise.
- **litellm/pydantic dependency addition** — `uv add litellm pydantic` per the cerebras skill; mechanical, not a design decision.
- **Chat message persistence/DB write ordering** — chat_messages writes should follow the same "no await inside the transaction" discipline flagged in STATE.md's Blockers/Concerns for Phase 3; a backend implementation detail, not a user decision.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Master specification
- `planning/PLAN.md` §2 (color scheme — reuse for message/card styling), §7 (Database — `chat_messages` schema), §8 (API Endpoints — Chat), §9 (LLM Integration — full chat flow, structured output schema, auto-execution, system prompt guidance, mock mode) — authoritative spec for this phase
- `planning/MARKET_DATA_SUMMARY.md` — market data subsystem the chat's portfolio context reads live prices from

### LLM integration
- `.claude/skills/cerebras/SKILL.md` — mandatory pattern for the LLM call: `litellm.completion()`, `MODEL = "openrouter/openai/gpt-oss-120b"`, `extra_body = {"provider": {"order": ["cerebras"]}}`, `reasoning_effort="low"`, Pydantic model as `response_format` for structured output

### Codebase maps
- `.planning/codebase/STACK.md` — confirmed dependency versions; `litellm`/`pydantic` not yet added
- `.planning/codebase/INTEGRATIONS.md` — LLM integration section (planned → this phase implements it), chat_messages schema pointer
- `.planning/codebase/ARCHITECTURE.md` — Chat & Trade Auto-Execution layer (`backend/app/llm/`), depends on Portfolio layer for context/execution
- `.planning/codebase/CONCERNS.md` — known gaps relevant here (Missing LiteLLM Dependency)

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — CHAT-01..06, UI-08, TEST-02, TEST-03, TEST-04
- `.planning/ROADMAP.md` Phase 3 section — success criteria and phase notes (TEST-03/04 backfill scope, chat_messages persistence ordering, litellm/pydantic dependency note)

### Prior phase context
- `.planning/phases/01-live-market-terminal/01-CONTEXT.md` — dark theme tokens, inline-edit-no-modal UX precedent
- `.planning/phases/02-portfolio-trading/02-CONTEXT.md` — `selectedTicker` shared-state pattern, empty-state message conventions, explicit-transaction pattern for multi-write DB operations (trade execution) — chat message persistence should follow the same discipline
- `.planning/PROJECT.md` — Key Decisions table (theme tokens, explicit-transaction pattern, recharts precedent)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/db/schema.sql` — `chat_messages` table already exists and seeded (empty): `id`, `user_id`, `role`, `content`, `actions` (JSON), `created_at`. No migration needed.
- `backend/app/llm/` — empty placeholder package, ready for the LLM client module.
- `backend/app/portfolio/`, `backend/app/watchlist/` — existing trade execution and watchlist CRUD logic; chat auto-execution calls into these same code paths rather than duplicating validation.
- `frontend/lib/format.ts` — shared currency formatting helper (thousands separators) from Phase 2's quick task; reuse for prices/quantities shown in trade summary cards.
- `frontend/hooks/usePortfolio.ts`, `usePriceStream.ts` — existing hooks the chat panel can read from for the same live context the LLM prompt is built from.
- Theme tokens (`#0d1117`/`#1a1a2e` backgrounds, up `#3fb950`, down `#f85149`, accent yellow `#ecad0a`, blue `#209dd7`, purple `#753991`) locked in Phase 1 — apply to trade summary cards and message bubbles.

### Established Patterns
- Factory pattern for routers: `create_watchlist_router(...)`, mirror as `create_chat_router(get_conn, market_source, price_cache, llm_client)`.
- Explicit `BEGIN`/`COMMIT`/`ROLLBACK` transactions for multi-write operations (Phase 2's trade execution) — apply the same discipline to chat message persistence + auto-executed trade/watchlist writes, keeping awaits (the LLM call) outside the transaction.
- Pydantic request/response models with `field_validator` for normalization (`AddTickerRequest` in `watchlist/router.py`) — mirror for chat request/response and the LLM structured-output schema.
- `WatchlistPanel.tsx`'s inline-edit-no-modal, no-confirmation-dialog UX — the chat's quick-prompt-sends-immediately (D-08) and trade auto-execution follow the same zero-friction philosophy.

### Integration Points
- `backend/app/llm/` — new LLM client module (LiteLLM/OpenRouter/Cerebras call, structured output parsing, mock mode) and chat router (`POST /api/chat`).
- `backend/app/main.py` — mount the new chat router alongside watchlist/portfolio/stream routers.
- `frontend/app/page.tsx` — add the chat drawer (collapsed by default per D-03), toggle control in the header or grid.
- `frontend/components/` — new components needed: chat panel/drawer, message list, message bubble, trade/watchlist confirmation card, quick-prompt buttons.

</code_context>

<specifics>
## Specific Ideas

No specific visual references or "I want it like X" examples came up. Quick-prompt copy examples ("Analyze my portfolio", "What should I buy?") were Claude's illustrative phrasing during discussion, not locked strings — exact copy is open during planning/implementation as long as it stays terse and terminal-appropriate, matching Phase 2's established tone.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. Message bubble styling and exact mock-mode pattern rules were offered/touched on but left to Claude's discretion (see Claude's Discretion above) rather than deferred to a future phase.

</deferred>

---

*Phase: 3-AI Copilot*
*Context gathered: 2026-08-25*
