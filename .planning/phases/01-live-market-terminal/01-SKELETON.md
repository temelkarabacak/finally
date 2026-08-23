# Walking Skeleton — FinAlly (AI Trading Workstation)

**Phase:** 1
**Generated:** 2026-08-23

## Capability Proven End-to-End

A user runs one command, opens `http://localhost:8000`, and sees the 10 seeded default tickers streaming live prices that were read out of a real SQLite database and pushed over SSE — served as a Next.js static export from the same FastAPI process on the same port.

This single path exercises every architectural layer the remaining three phases build on: SQLite write (lazy seed) → SQLite read (active-ticker query) → market-data source → `PriceCache` → SSE → static-served browser page → `EventSource`.

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Backend framework | FastAPI `>=0.138.0` (installed floor bumped from `>=0.115.0`), served by Uvicorn | Fixed by `planning/PLAN.md` §3. Floor raised because `app.frontend()` — the static-export serving mechanism — first shipped in 0.138.0. **Verified this session:** `app.frontend` is absent on the currently installed 0.128.7 and present on 0.141.1 with signature `frontend(path, *, directory, fallback='auto', check_dir='auto')`. |
| App entry point | `backend/app/main.py` exposing module-level `app`; `backend/app/__init__.py` stays a docstring-only package marker | Matches `.planning/codebase/STRUCTURE.md`; keeps `uvicorn app.main:app` unambiguous and importable by pytest without side effects. |
| Startup/shutdown | `@asynccontextmanager` `lifespan` | `@app.on_event` is legacy. Lifespan owns `init_db()`, market-source start, and clean `source.stop()`. |
| Shared price state | Exactly ONE `PriceCache()` constructed at module scope in `main.py`, threaded into `create_market_data_source()`, `create_stream_router()`, and the watchlist router | `create_stream_router(price_cache)` captures its argument in a closure (`backend/app/market/stream.py:17`). A second `PriceCache()` anywhere silently splits SSE from watchlist reads. This is the phase's single most dangerous wiring mistake. |
| Data layer | Python stdlib `sqlite3`, no ORM, `PRAGMA journal_mode=WAL` | No new dependency. WAL gives one-writer/many-reader concurrency ahead of Phase 2's snapshot + trade write load. `sqlite3.Connection.autocommit` verified present on the project interpreter (Python 3.14.6). |
| DB connection lifetime | One long-lived `sqlite3.Connection` on `app.state.db`, `check_same_thread=False` | Single-process, single-worker deployment target. Revisit only if Phase 2 shows contention. |
| DB file location | `FINALLY_DB_PATH` env var; default `<repo-root>/db/finally.db` resolved from `Path(__file__).resolve().parents[3]` | `db/` is the Phase-4 Docker volume mount target. The env var is the seam that lets the container point at `/app/db/finally.db` without code change. |
| Schema | All six tables created in Phase 1: `users_profile`, `watchlist`, `positions`, `trades`, `portfolio_snapshots`, `chat_messages` | Verbatim from `planning/PLAN.md` §7. Creating `positions` now is what lets the "watchlist ∪ open positions" active-ticker rule be written correctly from the start instead of being retrofitted in Phase 2. **Reversibility: one-way** — Phases 2-3 read these tables; changing them later means migrating every existing `db/finally.db`. |
| Multi-user seam | Every table carries `user_id TEXT NOT NULL DEFAULT 'default'` | Hardcoded single user now; no schema migration needed if auth ever lands. |
| Static frontend serving | `app.frontend("/", directory=<backend>/static, fallback="index.html", check_dir=False)` registered AFTER all `/api/*` routers | First-class FastAPI feature; handles SPA fallback and dotted-path traversal internally. `check_dir=False` keeps the app importable in tests before a build exists. |
| Frontend framework | Next.js 16.3.2 App Router + React 19.2.8 + TypeScript, `output: 'export'`, `images.unoptimized: true` | Fixed by `planning/PLAN.md` §3. Static export means one origin, one port, zero CORS. **Reversibility: costly** — it forecloses Server Actions, `i18n`, and dynamic route handlers project-wide, and Phase 4's Dockerfile consumes `frontend/out/`. |
| Styling | Tailwind CSS 4.3.3, CSS-first `@theme` tokens in `app/globals.css` (no `tailwind.config.js`) | v4 dropped the JS config + content globs. Theme tokens are the Phase-1 contract every later UI phase reuses. |
| Charting | `lightweight-charts` 5.2.1 for the main per-ticker chart; hand-rolled inline SVG for per-row sparklines | Per `01-CONTEXT.md` Claude's Discretion. v5 API is `chart.addSeries(LineSeries, opts)` — the v4 `addLineSeries()` shown in most tutorials does not exist in 5.x. |
| Real-time transport | Native `EventSource` against `/api/stream/prices`; no client library, no custom retry logic | Browsers reconnect automatically and `backend/app/market/stream.py:62` already emits `retry: 1000`. |
| Directory layout | `backend/app/<subsystem>/` with a barrel `__init__.py` per subsystem; `frontend/` at root with `app/` + `components/` + `hooks/`, no `src/` | Mirrors the existing `backend/app/market/` convention documented in `01-PATTERNS.md`. |
| Dev run | `scripts/dev.sh` — builds the export, syncs it into `backend/static/`, runs Uvicorn on 8000 | The documented full-stack local command. Phase 4 replaces it with the container, not the architecture. |

## Stack Touched in Phase 1

- [ ] **Project scaffold** — `create-next-app` (TypeScript, Tailwind, App Router, no `src/`); backend already has pytest 8.3 + ruff 0.7 configured in `backend/pyproject.toml`
- [ ] **Routing** — real routes: `GET /api/health`, `GET /api/watchlist`, `POST /api/watchlist`, `DELETE /api/watchlist/{ticker}`, `GET /api/stream/prices`, and the catch-all static frontend
- [ ] **Database** — real write (lazy schema create + seed of `users_profile` and 10 `watchlist` rows) AND real read (the `watchlist UNION positions` active-ticker query driving the market source)
- [ ] **UI** — real interactive elements wired to the API: live-updating price grid fed by `EventSource`, inline add-ticker input (`POST`), per-row remove (`DELETE`), click-to-select main chart
- [ ] **Deployment** — `scripts/dev.sh` exercises the full stack locally; `scripts/smoke.sh` asserts it end-to-end in CI-shaped form

## Out of Scope (Deferred to Later Slices)

Explicitly NOT in the skeleton. This list exists so later phases do not re-litigate Phase 1's minimalism:

- Trading, positions, cash mutation, P&L math, portfolio snapshots — Phase 2 (the `positions`/`trades`/`portfolio_snapshots` tables exist but stay empty)
- Portfolio heatmap, P&L chart, positions table, trade bar, header totals — Phase 2
- AI chat, LiteLLM/OpenRouter/Cerebras, `LLM_MOCK`, `chat_messages` writes — Phase 3
- Frontend unit test framework (TEST-04) — Phase 3
- Dockerfile, volume persistence, start/stop scripts, Playwright E2E — Phase 4
- Authentication, multi-user, sessions — out of scope for the whole milestone; the `user_id` column is the only concession
- Limit orders, order book, partial fills, WebSockets, Postgres — permanently out of scope per `.planning/REQUIREMENTS.md`
- Startup-time validation of `MASSIVE_API_KEY` format — deliberately omitted; a bad key fails the first poll and takes the same permanent-failover path (PORT-05), which is the behavior `planning/PLAN.md` §5 requires either way
- Any watchlist size cap — no limit is specified; noted as an accepted risk (`T-01-02`), not a gap

## Subsequent Slice Plan

Each later phase adds one vertical slice on top of this skeleton without altering its architectural decisions:

- **Phase 2 — Portfolio & Trading:** adds `/api/portfolio*` routers against the already-created `positions`/`trades`/`portfolio_snapshots` tables; opening a position extends the active ticker set through the same `get_active_tickers()` query this phase writes.
- **Phase 3 — AI Copilot:** adds `/api/chat` against the already-created `chat_messages` table; reuses the Phase 2 trade path and the Phase 1 watchlist path for auto-executed actions.
- **Phase 4 — One-Command Deployment:** replaces `scripts/dev.sh` with a multi-stage Dockerfile that performs the same two steps (build the export, serve it from FastAPI) and mounts `db/` as a volume.
