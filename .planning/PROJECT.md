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

### Active

Remaining platform from `planning/PLAN.md`, structured as vertical MVP slices (each phase delivers an end-to-end user capability, not just a technical layer):

- [ ] Portfolio endpoints: positions, cash, P&L, trade execution (market orders, fractional shares, buy/sell validation)
- [ ] Portfolio value snapshot recording (every 30s + after each trade) for the P&L chart
- [ ] AI-driven watchlist changes (via LLM chat, on top of Phase 1's manual CRUD)
- [ ] LLM chat integration via LiteLLM → OpenRouter (Cerebras inference, `openai/gpt-oss-120b`), structured output schema, auto-executed trades/watchlist changes, 30s timeout with generic retry message, mock mode (`LLM_MOCK=true`) for tests
- [ ] Portfolio heatmap (treemap), P&L line chart, positions table, trade bar, AI chat panel, header with connection status and live portfolio value
- [ ] Backend unit tests (pytest) for portfolio, LLM, API routes beyond what market data and Phase 1 already have
- [ ] Frontend unit tests (React Testing Library or similar)
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
*Last updated: 2026-08-23 after Phase 1*
