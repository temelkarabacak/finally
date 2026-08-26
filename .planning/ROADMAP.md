# Roadmap: FinAlly — AI Trading Workstation

## Overview

FinAlly starts from a completed market data subsystem (`backend/app/market/`) and nothing else — no FastAPI entry point, no database, no frontend, no container. This roadmap builds the remaining platform as four vertical MVP slices, each delivering an end-to-end user-visible capability rather than an isolated technical layer. Phase 1 stands the whole stack up and makes prices visible: FastAPI wiring, the full SQLite schema, watchlist CRUD, and a Next.js terminal UI streaming live prices. Phase 2 adds money — trading, positions, P&L, and the portfolio visualizations. Phase 3 adds the AI copilot that can analyze and trade on the user's behalf, plus the unit test suites that the mock LLM mode makes possible. Phase 4 packages everything into the single Docker container the core value promises, and proves it with a Playwright E2E suite running against that container.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Live Market Terminal** - Stand up the app end to end: FastAPI + SQLite + watchlist + streaming price UI (completed 2026-08-23)
- [x] **Phase 2: Portfolio & Trading** - Buy and sell shares, watch positions, P&L, and portfolio visualizations update live (completed 2026-08-25)
- [x] **Phase 3: AI Copilot** - Chat with an assistant that analyzes the portfolio and auto-executes trades and watchlist changes (completed 2026-08-26)
- [ ] **Phase 4: One-Command Deployment** - Ship as a single container with persistent data, start/stop scripts, and E2E verification

## Phase Details

### Phase 1: Live Market Terminal

**Goal**: A user opens a browser at port 8000 and watches an editable watchlist of live-streaming prices in the dark trading-terminal UI
**Mode:** mvp
**Depends on**: Nothing (first phase — builds on the existing `backend/app/market/` subsystem)
**Requirements**: FOUND-01, FOUND-02, FOUND-03, FOUND-04, WATCH-01, WATCH-02, WATCH-03, WATCH-04, PORT-05, UI-01, UI-02, UI-03, UI-10
**Success Criteria** (what must be TRUE):

  1. User opens `http://localhost:8000` on a fresh database and sees the 10 seeded default tickers with prices updating roughly twice a second, each row flashing green on an uptick and red on a downtick with a fading animation
  2. User can add a ticker and remove one; the grid and the SSE price stream reflect the change immediately, and a removed ticker keeps streaming while an open position still references it
  3. Clicking a watchlist row shows a larger price chart for that ticker in the main chart area, and every row carries a sparkline accumulated from prices seen since page load
  4. The entire interface renders in the dark trading-terminal theme (`#0d1117`/`#1a1a2e` backgrounds, accent yellow `#ecad0a`, blue `#209dd7`, purple `#753991`)
  5. `GET /api/health` reports healthy, and prices keep streaming even when the Massive provider is misconfigured or fails mid-run — the app falls over to the simulator permanently and never switches back

**Plans**: 3/3 plans executed

Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Walking Skeleton: DB lazy init + seed, FastAPI entry point, static export served on 8000, live prices streaming (FOUND-01..04, WATCH-01, WATCH-04)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02-PLAN.md — Editable watchlist (add/remove end to end) and permanent Massive failover to the simulator (WATCH-02, WATCH-03, PORT-05)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-03-PLAN.md — Terminal UI: dark theme, price flash, sparklines, per-ticker chart (UI-01, UI-02, UI-03, UI-10)

**UI hint**: yes

**Notes**:

- The full six-table schema (`users_profile`, `watchlist`, `positions`, `trades`, `portfolio_snapshots`, `chat_messages`) is created and seeded here even though positions/trades/chat are unused until later phases — this is what lets WATCH-03's "watchlist ∪ open positions" active-ticker rule be implemented correctly from the start.
- `PORT-05` (Massive permanent failover) lives here, not with the other PORT requirements, because it is market-data resilience: it belongs with the phase that first wires a data source into a running app. Known gap documented at `.planning/codebase/CONCERNS.md` (Incomplete Massive API Failover Implementation).
- `frontend/` is empty — this phase scaffolds the Next.js TypeScript project with `output: 'export'` and Tailwind, and establishes the theme other phases build on.

### Phase 2: Portfolio & Trading

**Goal**: A user can buy and sell shares instantly from the terminal and watch cash, positions, and P&L revalue live as prices stream
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: PORT-01, PORT-02, PORT-03, PORT-04, UI-04, UI-05, UI-06, UI-07, UI-09, TEST-01
**Success Criteria** (what must be TRUE):

  1. User enters a ticker and quantity (fractional quantities accepted) in the trade bar, clicks Buy or Sell, and the order fills instantly — cash, positions, and header totals update without a page reload and with no confirmation dialog
  2. A buy exceeding available cash or a sell exceeding the held quantity is rejected outright with a clear error and nothing is partially filled or clamped; backend unit tests cover these edges alongside trade execution and P&L math
  3. User sees a positions table showing ticker, quantity, average cost, current price, unrealized P&L, and % change, all revaluing as prices stream in
  4. User sees a portfolio heatmap where each position is sized by portfolio weight and colored by P&L, and a P&L line chart of total portfolio value that gains a new point at least every 30 seconds and immediately after each trade
  5. The header shows live portfolio total value, cash balance, and a connection status dot that goes green when connected, yellow while reconnecting, and red when disconnected

**Plans**: 4/4 plans executed

Plans:
**Wave 1**

- [x] 02-01-PLAN.md — Tracer: buy and sell end to end — trade engine, `GET /api/portfolio`, trade bar, header stats, trade tests (PORT-01, PORT-02, PORT-03, PORT-04, UI-07, UI-09, TEST-01)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 02-02-PLAN.md — Portfolio value over time: 30s snapshot recorder, `GET /api/portfolio/history`, P&L chart, valuation and route tests (PORT-04, UI-05, TEST-01)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 02-03-PLAN.md — Positions table and portfolio heatmap, with a blocking package-legitimacy gate before `recharts` (UI-04, UI-06)

**Wave 4** *(gap closure — blocked on Wave 3 completion)*

- [x] 02-04-PLAN.md — Gap G-02-4: poll portfolio history in `usePortfolio` so the P&L chart fills in on a cold start without a trade (UI-05)

**UI hint**: yes

**Notes**:

- Opening a position must extend the active ticker set so a held ticker keeps streaming after it leaves the watchlist — this closes the loop on Phase 1's WATCH-03 behavior.
- Snapshot recording has two triggers (30s background task and post-trade), both writing to `portfolio_snapshots`; SQLite has a single writer, so snapshot writes and trade writes need to be serialized (see `.planning/codebase/CONCERNS.md`).

### Phase 3: AI Copilot

**Goal**: A user can converse with an AI assistant that reads their live portfolio and executes trades and watchlist changes on their behalf
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: CHAT-01, CHAT-02, CHAT-03, CHAT-04, CHAT-05, CHAT-06, UI-08, TEST-02, TEST-03, TEST-04
**Success Criteria** (what must be TRUE):

  1. User types a question into the docked, collapsible chat panel, sees a loading indicator, and gets back one complete response grounded in their actual cash, positions with P&L, and live watchlist prices — no token-by-token streaming
  2. Asking the assistant to buy or sell executes the trade through the same validation as the trade bar; the execution appears inline in the chat as a confirmation and the portfolio updates, and a rejected trade is reported back in the reply rather than silently dropped
  3. Asking the assistant to add or remove a watchlist ticker updates the watchlist and price stream, confirmed inline in the chat
  4. Conversation history survives a page reload, and a request that hangs past 30 seconds returns a generic retry message with no trade executed and no failed attempt left in the history
  5. With `LLM_MOCK=true` the chat returns deterministic responses without calling OpenRouter, so the full backend and frontend unit suites run offline and green — covering structured-output parsing (including malformed responses), portfolio/watchlist/chat route status codes and response shapes, and UI components (price flash, watchlist CRUD, portfolio calculations, chat rendering and loading state)

**Plans**: 4/4 plans executed

Plans:
**Wave 1**

- [x] 03-01-PLAN.md — Tracer: chat turn end to end — LiteLLM/Cerebras client, structured-output contract, two-transaction persistence, `POST /api/chat`, collapsed bottom drawer, plus the litellm/pydantic and vitest installs behind a package-legitimacy gate (CHAT-01, CHAT-04, CHAT-06, UI-08)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 03-02-PLAN.md — Auto-executed trades and watchlist changes through the existing validated paths, the 12-scenario mock rule table, and inline success/REJECTED confirmation cards (CHAT-02, CHAT-03, CHAT-06, UI-08)
- [x] 03-03-PLAN.md — Test backfill: portfolio/watchlist route status-code and response-shape matrix, plus the first frontend tests (price flash, watchlist CRUD, portfolio calculations) (TEST-03, TEST-04)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 03-04-PLAN.md — Resilience and starter experience: `GET /api/chat/history`, timeout/malformed safe degrade, quick prompts, loading and error states (CHAT-04, CHAT-05, TEST-02, TEST-03, TEST-04, UI-08)

**UI hint**: yes

**Notes**:

- Use the project's `cerebras` skill (`.claude/skills/cerebras/SKILL.md`) for the LLM call: LiteLLM `completion()` with `MODEL = "openrouter/openai/gpt-oss-120b"`, `extra_body = {"provider": {"order": ["cerebras"]}}`, `reasoning_effort="low"`, and a Pydantic model passed as `response_format` for structured output.
- `litellm` and `pydantic` are not yet in `backend/pyproject.toml` — they must be added via `uv add` (see `.planning/codebase/CONCERNS.md`, "Missing LiteLLM Dependency").
- TEST-03 and TEST-04 span routes and components built in Phases 1 and 2 as well; they land here because chat is the last piece and the mock mode that makes the suites fast and free arrives with it. Expect some backfill of coverage for earlier phases' code.
- The user's message persists to `chat_messages` before the LLM call; the assistant's message persists only after successful generation and action execution. Only the last 20 messages go into the LLM context.

### Phase 4: One-Command Deployment

**Goal**: Anyone can launch the whole verified app with a single command and keep their portfolio across restarts
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: DEPLOY-01, DEPLOY-02, DEPLOY-03, TEST-05
**Success Criteria** (what must be TRUE):

  1. A single start script builds and runs one container, and the complete app — static frontend, REST API, SSE stream, and AI chat — is usable at `http://localhost:8000` on one port with no CORS configuration
  2. Stopping and restarting the container preserves cash balance, positions, trade history, and chat history through the volume-mounted SQLite file at `db/finally.db`
  3. Start and stop scripts work and are safe to run repeatedly on both macOS/Linux (`start_mac.sh`, `stop_mac.sh`) and Windows (`start_windows.ps1`, `stop_windows.ps1`); stopping never destroys the data volume
  4. The Playwright E2E suite runs against the container with `LLM_MOCK=true` and passes: fresh start with seeded watchlist and $10k, watchlist add/remove, buy and sell, heatmap and P&L chart rendering, AI chat with an inline trade, and SSE reconnection after a disconnect

**Plans**: TBD

**Notes**:

- Multi-stage build: Node 20 slim builds the Next.js static export, Python 3.12 slim runs uv-synced FastAPI and serves the export.
- E2E infrastructure (`test/docker-compose.test.yml`) pairs the app container with a Playwright container so browser dependencies stay out of the production image — which is why TEST-05 is here rather than in Phase 3.
- Per explicit user decision, this phase is last and the milestone is not done without it.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Live Market Terminal | 3/3 | Complete    | 2026-08-23 |
| 2. Portfolio & Trading | 4/4 | Complete    | 2026-08-25 |
| 3. AI Copilot | 4/4 | Complete    | 2026-08-26 |
| 4. One-Command Deployment | 0/TBD | Not started | - |

## Requirement Coverage

All 37 v1 requirements mapped to exactly one phase. No orphans, no duplicates.

| Phase | Requirements | Count |
|-------|--------------|-------|
| 1. Live Market Terminal | FOUND-01, FOUND-02, FOUND-03, FOUND-04, WATCH-01, WATCH-02, WATCH-03, WATCH-04, PORT-05, UI-01, UI-02, UI-03, UI-10 | 13 |
| 2. Portfolio & Trading | PORT-01, PORT-02, PORT-03, PORT-04, UI-04, UI-05, UI-06, UI-07, UI-09, TEST-01 | 10 |
| 3. AI Copilot | CHAT-01, CHAT-02, CHAT-03, CHAT-04, CHAT-05, CHAT-06, UI-08, TEST-02, TEST-03, TEST-04 | 10 |
| 4. One-Command Deployment | DEPLOY-01, DEPLOY-02, DEPLOY-03, TEST-05 | 4 |
| **Total** | | **37** |

---
*Roadmap created: 2026-08-23*
