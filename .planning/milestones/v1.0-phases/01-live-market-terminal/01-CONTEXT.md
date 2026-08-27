# Phase 1: Live Market Terminal - Context

**Gathered:** 2026-08-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Stand up the whole application end to end: a FastAPI entry point that wires together the existing market data subsystem, a new SQLite schema (all six tables, lazily initialized and seeded), watchlist CRUD (manual, via REST), and a Next.js dark-terminal frontend that streams live prices over SSE with flash animations, sparklines, and a larger per-ticker chart. Portfolio trading, AI chat, and Docker packaging are explicitly later phases — this phase makes the app runnable and prices visible, nothing more.

</domain>

<decisions>
## Implementation Decisions

User was offered specific gray areas (charting library, watchlist edit UX, real-Massive-API testing) and chose "use your judgment" for all of them. Decisions below are Claude's calls, made to fit the existing codebase conventions and PLAN.md's stated preferences — not user-specified.

### Claude's Discretion

- **Charting library — Lightweight Charts.** PLAN.md lists it first ("Lightweight Charts or Recharts preferred") and it's purpose-built for financial time series (proper price-axis/time-axis behavior), matching the Bloomberg-terminal aesthetic better than a general-purpose charting library. Used for the main per-ticker chart (UI-03).
- **Sparklines — no charting library.** The per-row watchlist sparkline (UI-01) is a trivial polyline over an in-memory price array accumulated since page load. A lightweight inline SVG (or tiny canvas draw) avoids per-row overhead from a full charting library instantiated 10+ times in the grid.
- **Watchlist edit UX — inline, no modal.** Add via a small input directly in the watchlist panel (type ticker, Enter); remove via a small "×" per row. Matches the terminal aesthetic (dense, keyboard-friendly, no dialogs) and keeps consistent with the "no confirmation dialogs" spirit already established for trades.
- **Real Massive API — simulator-only for this phase's build and automated tests.** The Massive client already exists and is unit-tested (Validated requirement). This phase wires the factory selection (`MASSIVE_API_KEY` env var) and the failover path, but development and automated verification target the simulator. If a real Massive key is present in `.env`, a manual spot-check is reasonable but not a phase gate — automated tests must not depend on a live external API.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Master specification
- `planning/PLAN.md` §6 (Market Data), §7 (Database), §8 (API Endpoints — Market Data & Watchlist), §10 (Frontend Design), §11 (Docker — for later phases, not this one) — authoritative spec for schema, endpoints, and SSE contract
- `planning/MARKET_DATA_SUMMARY.md` — summary of the already-completed market data subsystem this phase builds on top of

### Codebase maps
- `.planning/codebase/ARCHITECTURE.md` — system layering, data flow, existing anti-patterns (no entry point yet, empty placeholder modules)
- `.planning/codebase/STRUCTURE.md` — directory layout, naming conventions, "where to add new code" guidance for `app/db/`, `app/watchlist/`, and `frontend/`
- `.planning/codebase/CONCERNS.md` — known gaps, including "Incomplete Massive API Failover Implementation" (PORT-05 must actually close this gap, not just document it) and "Missing LiteLLM/pydantic dependency" (not relevant to this phase, but noted for Phase 3)
- `.planning/codebase/STACK.md` — confirmed dependency versions (FastAPI 0.115+, Uvicorn 0.32+, pytest 8.3+, numpy 2.0+, massive 1.0+)

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — FOUND-01..04, WATCH-01..04, PORT-05, UI-01, UI-02, UI-03, UI-10
- `.planning/ROADMAP.md` Phase 1 section — success criteria and phase notes (full-schema-in-Phase-1 rationale, PORT-05 placement rationale)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/market/factory.py:16` `create_market_data_source()` — already selects simulator vs Massive based on `MASSIVE_API_KEY`; the new FastAPI app just needs to call this at startup and hold the resulting source + `PriceCache` for the app lifetime.
- `backend/app/market/stream.py:17` `create_stream_router()` — SSE endpoint factory already exists; mount it as-is.
- `backend/app/market/cache.py` `PriceCache` — thread-safe, versioned; inject the same instance into the DB/watchlist layer so "active ticker set = watchlist ∪ open positions" can be computed and pushed into the cache/source.
- `backend/app/market/seed_prices.py` — seed prices and correlation groups for the 10 default tickers; matches PLAN.md §7 seed data (AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX).

### Established Patterns
- Abstract interface + factory pattern (`MarketDataSource`) — mirror this for the DB layer if a similar pluggability need arises (it doesn't for SQLite, but keep the one-directional import style: `factory` → implementations → `interface`/`cache`/`models`).
- Frozen dataclasses for immutable models (`PriceUpdate`) — use similarly for API response models where appropriate, though FastAPI/Pydantic models are the natural fit for request/response schemas.
- Module-level `logger = logging.getLogger(__name__)`, one responsibility per module, `lowercase_with_underscores.py` naming, 100-char line length (ruff-enforced).

### Integration Points
- `backend/app/__init__.py` — currently minimal; this phase creates the FastAPI app object here (or in a new `backend/app/main.py` imported by `__init__.py`), wires the market data startup, DB init, and the watchlist router.
- `backend/app/db/` — empty placeholder; this phase adds schema SQL, seed logic, and lazy init (create tables + seed on first run if `db/finally.db` doesn't exist or is empty).
- `backend/app/watchlist/` — empty placeholder; this phase adds the watchlist CRUD router (`GET/POST /api/watchlist`, `DELETE /api/watchlist/{ticker}`).
- `frontend/` — empty; this phase scaffolds the Next.js TypeScript project (`output: 'export'`, Tailwind, dark theme tokens for `#0d1117`/`#1a1a2e` backgrounds and `#ecad0a`/`#209dd7`/`#753991` accents) and builds the watchlist grid + main chart.

</code_context>

<specifics>
## Specific Ideas

No specific implementation examples or "I want it like X" references came up — user deferred all discussed gray areas to Claude's judgment. PLAN.md's color scheme and layout descriptions (§2, §10) are the concrete visual anchors to follow; deeper visual design decisions belong to `/gsd-ui-phase 1` if run before planning.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. Portfolio, AI chat, and Docker packaging are already scoped to Phases 2-4 in ROADMAP.md; nothing new came up that needs deferring.

</deferred>

---

*Phase: 1-Live Market Terminal*
*Context gathered: 2026-08-23*
