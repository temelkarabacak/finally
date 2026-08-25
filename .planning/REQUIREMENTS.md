# Requirements: FinAlly — AI Trading Workstation

**Defined:** 2026-08-23
**Core Value:** A user can launch the app with one command, watch live prices stream in, buy/sell shares instantly, and ask the AI assistant to analyze or trade on their behalf — and it just works, end to end, in a single Docker container.

## v1 Requirements

Requirements for this milestone (the whole remaining platform, per PLAN.md). Each maps to roadmap phases.

### Foundation

- [x] **FOUND-01**: Backend exposes `GET /api/health` for health checks
- [x] **FOUND-02**: Backend lazily creates the SQLite schema and seeds default data (default user with $10,000 cash, 10 default watchlist tickers) on first run if `db/finally.db` doesn't exist or is empty
- [x] **FOUND-03**: FastAPI serves the built Next.js static export for all non-`/api/*` routes from a single port (8000)
- [x] **FOUND-04**: Market data source (simulator or Massive) starts at app startup, tracking the active ticker set (watchlist ∪ open positions)

### Watchlist

- [x] **WATCH-01**: User can view current watchlist tickers with latest prices via `GET /api/watchlist`
- [x] **WATCH-02**: User can add a ticker to the watchlist via `POST /api/watchlist`
- [x] **WATCH-03**: User can remove a ticker via `DELETE /api/watchlist/{ticker}`; it keeps streaming if an open position still references it
- [x] **WATCH-04**: `GET /api/stream/prices` (SSE) pushes price updates for every ticker in watchlist ∪ open positions at ~500ms cadence

### Portfolio & Trading

- [x] **PORT-01**: User can view portfolio (positions, cash balance, total value, unrealized P&L) via `GET /api/portfolio`
- [x] **PORT-02**: User can execute a market buy or sell order via `POST /api/portfolio/trade`, fractional share quantities supported
- [x] **PORT-03**: A buy is rejected outright (never clamped) when cash is insufficient; a sell is rejected outright when held quantity is insufficient
- [x] **PORT-04**: Portfolio value snapshots are recorded every 30 seconds and immediately after each trade, retrievable via `GET /api/portfolio/history`
- [x] **PORT-05**: Massive API failures (auth, rate limit, network, or service error) permanently fail the running app over to the simulator for the remainder of the run — never switches back

### AI Chat

- [x] **CHAT-01**: User can send a message via `POST /api/chat` and receive one complete JSON response (message + executed actions) — no token streaming
- [x] **CHAT-02**: The LLM's response can include trades that auto-execute through the same validation as manual trades; results are reflected in the chat response
- [x] **CHAT-03**: The LLM's response can include watchlist changes that auto-execute
- [ ] **CHAT-04**: Chat history (last 20 messages) persists across requests; the user's message is saved before the LLM call, the assistant's after successful completion
- [x] **CHAT-05**: A chat request that exceeds a 30-second LLM timeout aborts with a generic retry message and executes no trade; the failed attempt is not persisted to chat history
- [x] **CHAT-06**: When `LLM_MOCK=true`, the backend returns deterministic mock responses instead of calling OpenRouter

### Frontend UI

- [x] **UI-01**: Watchlist grid shows ticker, current price, daily change %, and a sparkline accumulated from the SSE stream since page load
- [x] **UI-02**: Prices flash green (uptick) or red (downtick) with a fading CSS animation on change
- [x] **UI-03**: Clicking a watchlist ticker shows a larger price chart for that ticker in the main chart area
- [x] **UI-04**: Portfolio heatmap (treemap) sized by position weight, colored by P&L
- [x] **UI-05**: P&L line chart of total portfolio value over time
- [x] **UI-06**: Positions table (ticker, quantity, avg cost, current price, unrealized P&L, % change)
- [x] **UI-07**: Trade bar lets the user submit a buy or sell market order (ticker, quantity, buy/sell buttons)
- [ ] **UI-08**: Docked/collapsible AI chat panel with loading state and inline trade/watchlist action confirmations
- [x] **UI-09**: Header shows live portfolio total value, connection status indicator (green/yellow/red dot), and cash balance
- [x] **UI-10**: Dark trading-terminal theme applied throughout (backgrounds, accent colors `#ecad0a`/`#209dd7`/`#753991`, price flash colors)

### Testing

- [x] **TEST-01**: Backend unit tests cover portfolio trade execution, P&L calculation, and edge cases (insufficient cash/shares)
- [x] **TEST-02**: Backend unit tests cover LLM structured-output parsing, including malformed responses
- [ ] **TEST-03**: Backend unit tests cover API route status codes and response shapes for portfolio/watchlist/chat
- [ ] **TEST-04**: Frontend unit tests cover price flash animation, watchlist CRUD, portfolio calculations, and chat rendering/loading state
- [ ] **TEST-05**: Playwright E2E suite (`test/`, `LLM_MOCK=true`) covers fresh start, watchlist add/remove, buy/sell, visualizations, AI chat, and SSE reconnection

### Deployment

- [ ] **DEPLOY-01**: Multi-stage Dockerfile builds the Next.js export and Python backend into a single image serving port 8000
- [ ] **DEPLOY-02**: SQLite database persists via a volume-mounted `db/` directory across container restarts
- [ ] **DEPLOY-03**: Idempotent start/stop scripts for macOS/Linux (`scripts/start_mac.sh`, `stop_mac.sh`) and Windows (`start_windows.ps1`, `stop_windows.ps1`)

## v2 Requirements

None — the full remaining platform is in scope for this milestone (per explicit user decision during initialization).

## Out of Scope

| Feature | Reason |
|---------|--------|
| Limit orders, order book, partial fills | Market orders only — dramatically simplifies portfolio math (PLAN.md §3) |
| Multi-user support / authentication | Single hardcoded `user_id="default"`, no login; schema leaves room for it later |
| WebSockets | SSE is simpler and sufficient for one-way price push |
| Postgres or other server-based DB | SQLite is self-contained and sufficient for single-user |
| Trade confirmation dialogs | Instant fill by design — zero stakes with simulated money |
| Token-by-token LLM streaming | Cerebras inference is fast enough that a loading indicator suffices |
| Terraform / cloud deployment (App Runner, Render) | Stretch goal only, not part of core build |

## Traceability

Populated during roadmap creation (2026-08-23).

| Requirement | Phase | Status |
|-------------|-------|--------|
| FOUND-01 | Phase 1 | Complete |
| FOUND-02 | Phase 1 | Complete |
| FOUND-03 | Phase 1 | Complete |
| FOUND-04 | Phase 1 | Complete |
| WATCH-01 | Phase 1 | Complete |
| WATCH-02 | Phase 1 | Complete |
| WATCH-03 | Phase 1 | Complete |
| WATCH-04 | Phase 1 | Complete |
| PORT-01 | Phase 2 | Complete |
| PORT-02 | Phase 2 | Complete |
| PORT-03 | Phase 2 | Complete |
| PORT-04 | Phase 2 | Complete |
| PORT-05 | Phase 1 | Complete |
| CHAT-01 | Phase 3 | Complete |
| CHAT-02 | Phase 3 | Complete |
| CHAT-03 | Phase 3 | Complete |
| CHAT-04 | Phase 3 | Pending |
| CHAT-05 | Phase 3 | Complete |
| CHAT-06 | Phase 3 | Complete |
| UI-01 | Phase 1 | Complete |
| UI-02 | Phase 1 | Complete |
| UI-03 | Phase 1 | Complete |
| UI-04 | Phase 2 | Complete |
| UI-05 | Phase 2 | Complete |
| UI-06 | Phase 2 | Complete |
| UI-07 | Phase 2 | Complete |
| UI-08 | Phase 3 | Pending |
| UI-09 | Phase 2 | Complete |
| UI-10 | Phase 1 | Complete |
| TEST-01 | Phase 2 | Complete |
| TEST-02 | Phase 3 | Complete |
| TEST-03 | Phase 3 | Pending |
| TEST-04 | Phase 3 | Pending |
| TEST-05 | Phase 4 | Pending |
| DEPLOY-01 | Phase 4 | Pending |
| DEPLOY-02 | Phase 4 | Pending |
| DEPLOY-03 | Phase 4 | Pending |

**Coverage:**

- v1 requirements: 37 total
- Mapped to phases: 37 ✓
- Unmapped: 0 ✓

**By phase:**

| Phase | Count |
|-------|-------|
| Phase 1 — Live Market Terminal | 13 |
| Phase 2 — Portfolio & Trading | 10 |
| Phase 3 — AI Copilot | 10 |
| Phase 4 — One-Command Deployment | 4 |

---
*Requirements defined: 2026-08-23*
*Last updated: 2026-08-23 after roadmap creation (traceability populated)*
