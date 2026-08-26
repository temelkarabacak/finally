# FinAlly — AI Trading Workstation

## What This Is

FinAlly is a visually stunning, single-container AI trading workstation: a Bloomberg-terminal-style app that streams live (simulated or real) market data, lets a user trade a simulated $10,000 portfolio with instant market-order fills, and includes an AI chat copilot (via LiteLLM/OpenRouter/Cerebras) that can analyze the portfolio and auto-execute trades on the user's behalf. It's the capstone project for an agentic AI coding course — built entirely by orchestrated coding agents. Full spec lives in `planning/PLAN.md`.

## Core Value

A user can launch the app with one command, watch live prices stream in, buy/sell shares instantly, and ask the AI assistant to analyze or trade on their behalf — and it just works, end to end, in a single Docker container.

## Requirements

### Validated

- ✓ Pluggable market data source (simulator via GBM, or real Massive/Polygon API) behind a shared abstract interface — existing, `backend/app/market/`
- ✓ Thread-safe in-memory price cache with versioning — existing, `backend/app/market/cache.py`
- ✓ SSE price streaming endpoint factory — existing, `backend/app/market/stream.py`
- ✓ Correlated GBM price simulation with occasional shock events — existing, `backend/app/market/simulator.py`
- ✓ Full test coverage for the market data subsystem — existing, `backend/tests/market/`
- ✓ FastAPI app entry point wiring together market data, DB, and static frontend serving — Phase 1, `backend/app/main.py`
- ✓ SQLite schema with lazy initialization and seed data (all six tables; `positions`/`trades`/`portfolio_snapshots`/`chat_messages` stay empty until later phases) — Phase 1, `backend/app/db/`
- ✓ Manual watchlist management (add/remove tickers, GET with live prices) — Phase 1, `backend/app/watchlist/router.py`; AI-driven watchlist changes still pending (Phase 3)
- ✓ Massive API permanent failover to simulator on auth/rate-limit/network/service errors (never switches back) — Phase 1, `backend/app/market/failover.py`
- ✓ Watchlist grid with price flash animations + progressive sparklines, main price chart (Lightweight Charts) for the selected ticker — Phase 1, `frontend/components/{WatchlistPanel,Sparkline,PriceChart}.tsx`
- ✓ Dark trading-terminal theme (`#0d1117`/`#1a1a2e` backgrounds, accent yellow `#ecad0a`, blue `#209dd7`, purple `#753991`) — Phase 1, `frontend/app/globals.css`; human-verified against all 9 checkpoint items
- ✓ Portfolio endpoints: positions, cash, P&L, trade execution (market orders, fractional shares, buy/sell validation rejected outright, never clamped) — Phase 2, `backend/app/portfolio/`
- ✓ Portfolio value snapshot recording (30s background task + immediately after each trade) for the P&L chart — Phase 2, `backend/app/portfolio/snapshots.py`
- ✓ Portfolio heatmap (treemap), P&L line chart, positions table, trade bar, header with live connection status and portfolio value — Phase 2, `frontend/components/{PortfolioHeatmap,PnlChart,PositionsTable,TradeBar}.tsx`; human-verified via UAT (8/8 passed)
- ✓ Backend unit tests (pytest) for trade execution, valuation, snapshot recording, and portfolio/watchlist routes — Phase 2, `backend/tests/portfolio/`
- ✓ AI-driven watchlist changes via LLM chat, composed over the same validated `add_watchlist_ticker`/`remove_watchlist_ticker` paths as manual CRUD — Phase 3, `backend/app/llm/executor.py`
- ✓ LLM chat integration via LiteLLM → OpenRouter (Cerebras inference, `openai/gpt-oss-120b`), structured output schema (`ChatResponse`), auto-executed trades/watchlist changes derived only from execution results, 30s timeout + malformed-output both degrading to one shared generic retry message, `LLM_MOCK=true` deterministic mock mode for tests — Phase 3, `backend/app/llm/`
- ✓ AI chat panel — collapsed by default, transcript persists across reloads (`GET /api/chat/history`), loading/empty/error states, inline trade confirmation cards — Phase 3, `frontend/components/{ChatDrawer,ChatMessageBubble,ChatMessageList,TradeConfirmationCard}.tsx`; human-verified via UAT (2/2 passed)
- ✓ Backend unit tests (pytest) for LLM structured-output parsing, chat routes, and the portfolio/watchlist route status-code/response-shape matrix — Phase 3, `backend/tests/llm/`, `backend/tests/portfolio/`, `backend/tests/watchlist/`
- ✓ Frontend unit tests (Vitest + Testing Library) — first-ever frontend test coverage: price flash, watchlist CRUD, portfolio calculations, chat rendering/loading/error states — Phase 3, `frontend/**/*.test.{ts,tsx}` (5 files, 31 tests)

### Active

Remaining platform from `planning/PLAN.md`, structured as vertical MVP slices (each phase delivers an end-to-end user capability, not just a technical layer):

- [ ] Playwright E2E tests in `test/` (docker-compose.test.yml) covering fresh start, watchlist CRUD, buy/sell, visualizations, AI chat, SSE reconnection
- [ ] Multi-stage Dockerfile (Node build → Python runtime), single port 8000, volume-mounted SQLite
- [ ] Start/stop scripts for macOS/Linux and Windows

### Out of Scope

- Limit orders, order book, partial fills — market orders only, dramatically simplifies portfolio math (per PLAN.md §3)
- Multi-user support / authentication — single hardcoded `user_id="default"`, no login (schema leaves room for it later)
- WebSockets — SSE chosen for simplicity; one-way push is sufficient
- Postgres or other server-based DB — SQLite is self-contained and sufficient for single-user
- Trade confirmation dialogs — instant fill by design, zero stakes with simulated money
- Token-by-token LLM streaming — Cerebras inference is fast enough that a loading indicator suffices
- Terraform/cloud deployment (App Runner, Render) — stretch goal only, not part of core build

## Context

- **Brownfield, single milestone covering the whole remaining platform.** Only the market data subsystem is built; everything else (DB, portfolio, watchlist, chat/LLM, frontend, Docker) is greenfield within this repo.
- Empty placeholder directories already exist: `backend/app/db/`, `backend/app/llm/`, `backend/app/portfolio/`, `backend/app/watchlist/` — no `.py` files yet, ready for implementation.
- No FastAPI entry point exists yet (`backend/app/__init__.py` is minimal, no `main.py`) — this blocks running the backend at all until built.
- `frontend/` directory exists but is empty — no Next.js project scaffolded yet.
- `.env` at project root already contains `OPENROUTER_API_KEY` for LLM integration.
- Full technical spec (schema, API contracts, LLM structured-output format, Docker layout) is authoritative in `planning/PLAN.md` — treat it as the source of truth; `.planning/` (GSD) documents track execution against it.
- Codebase map available at `.planning/codebase/` (STACK.md, ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, INTEGRATIONS.md, CONCERNS.md).

## Constraints

- **Roadmap structure**: Vertical MVP — each phase should deliver an end-to-end user-visible capability, not an isolated technical layer, given how interdependent DB/portfolio/chat are (all touch the same tables).
- **Docker**: Included as the final phase of this roadmap — the milestone isn't done until there's a working single-container deployment (per PLAN.md §11), not deferred to a later milestone.
- **Timeline**: No hard deadline — optimize for quality and completeness over speed.
- **Tech stack**: FastAPI + uv (Python backend), Next.js + TypeScript static export (frontend), SQLite (single file, lazy init), LiteLLM → OpenRouter with Cerebras inference — all fixed by PLAN.md, not open decisions.
- **Single container, single port (8000)**: FastAPI serves both `/api/*` and the static Next.js export — no CORS configuration needed, no docker-compose required for production.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Build the entire remaining platform in one roadmap (not a narrower slice) | User wants the full capstone scope covered in this cycle | — Pending |
| Vertical MVP phase structure over Horizontal Layers | Backend layers (DB/portfolio/chat) are tightly coupled through shared tables; slicing by user capability avoids half-finished layers | — Pending |
| Docker containerization as the final phase, not deferred | Milestone isn't "done" without a working single-command deployment | — Pending |
| FastAPI floor bumped to `>=0.138.0` | `app.frontend()` (single-port static+API serving) requires it; installed 0.128.7 predates the method | Shipped — Phase 1 |
| `httpx` added as backend dev dependency | Starlette's `TestClient` requires it; surfaced by the framework's own import error, not discretionary | Shipped — Phase 1 |
| `FailoverMarketDataSource` does a lock-guarded, idempotent, one-way swap to the simulator on first Massive error | Matches PLAN.md §6's "permanent failover, never switches back" contract; avoids flapping between sources | Shipped — Phase 1 |
| Dark theme tokens locked: up `#3fb950`, down `#f85149`, border `#30363d`, text `#e6edf3`, muted `#8b949e`; charting via `lightweight-charts@5.2.1` | Human-verified live against all 9 checkpoint items (theme, flash calmness, reduced-motion, sparklines, chart) | Shipped — Phase 1 |
| Accepted npm registry's `react`/`react-dom` repo listing as `github.com/react/react` (not the historical `facebook/react`) as a legitimate org migration | Verified via live registry lookup before any install; no `[SLOP]` verdict, versions matched RESEARCH.md's audit exactly | Shipped — Phase 1 |
| Trade transaction wraps four writes (cash, position, trade log, snapshot) in explicit `BEGIN`/`COMMIT`/`ROLLBACK` rather than relying on `autocommit` | SQLite `Connection.commit()` is a documented no-op in this connection mode; explicit transaction boundaries are the only way to guarantee all-or-nothing trade writes | Shipped — Phase 2 |
| `recharts` accepted for the heatmap after a blocking-human legitimacy checkpoint | `02-RESEARCH.md`'s automated recency heuristic flagged `[SUS]`; human confirmed 58.5M weekly downloads, canonical `recharts/recharts` org, and multi-year version history before install | Shipped — Phase 2 |
| `usePortfolio.ts` polls `/api/portfolio/history` every 10s instead of only on mount/post-trade | Gap-closure fix (G-02-4): the mount-only fetch raced the backend's first 30s snapshot, leaving the P&L panel stuck on the empty state indefinitely with no trade | Shipped — Phase 2 |
| Currency values in the header and P&L chart formatted with thousands separators via a shared `frontend/lib/format.ts` helper | User-requested display fix; pinned to `en-US` locale for deterministic output regardless of viewer's browser language | Shipped — Phase 2 (quick task) |
| `litellm`/`pydantic`/`vitest` and 6 other new packages accepted after a `gate="blocking-human"` legitimacy checkpoint | `03-RESEARCH.md`'s automated checker flagged 6/9 as `[SUS]` on age/download-count heuristics only (zero `[SLOP]`); human spot-checked registry pages before any install ran | Shipped — Phase 3 |
| Chat panel redesigned mid-phase from a bottom-overlay drawer to a right-side sidebar that pushes/reflows the grid | Superseded CONTEXT.md decisions D-01 (bottom drawer)/D-02 (overlay, no reflow) — first UAT pass on the original design found the fixed toggle button overlapping the Send button (unclickable); user then requested the sidebar-that-pushes layout directly, which structurally removes the overlap (toggle now lives in the panel's own header, not a floating fixed element) | Shipped — Phase 3 |
| Chat history loaded before persisting the current turn's user message, not after | Code-review-caught bug (CR-01): persisting first meant the just-inserted row appeared as the last history row AND got appended again as the explicit final turn, sending every real LLM call a duplicated current message | Shipped — Phase 3 |
| `WatchlistPanel` exposes an imperative `refetch` via `forwardRef`/`useImperativeHandle`; `page.tsx`'s `refreshAll` combines it with the portfolio refresh for both `TradeBar` and `ChatDrawer` | Code-review-caught bug (CR-02): a chat-executed (or manual, for an unwatched ticker) watchlist add/remove updated the backend but never refreshed the grid until a full reload, since `onActionsExecuted`/`onTraded` only refreshed portfolio data | Shipped — Phase 3 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-08-26 after Phase 3*
