# Phase 2: Portfolio & Trading - Context

**Gathered:** 2026-08-23
**Status:** Ready for planning

<domain>
## Phase Boundary

A user can buy and sell shares instantly from the terminal and watch cash, positions, and P&L revalue live as prices stream. This phase adds: portfolio endpoints (positions, cash, P&L, trade execution with market orders, fractional shares, buy/sell validation), portfolio snapshot recording (every 30s + after each trade) for the P&L chart, and the frontend visualizations — portfolio heatmap (treemap), P&L line chart, positions table, trade bar, and a header showing live portfolio value, cash balance, and connection status. AI chat, watchlist auto-management via LLM, and Docker packaging are later phases — this phase is trading and portfolio visibility only.

</domain>

<decisions>
## Implementation Decisions

### Empty portfolio state
- **D-01:** Before the first trade, the positions table shows a centered empty-state message (e.g. "No positions yet — buy shares to get started") in place of the table body, rather than hiding the panel or showing bare headers.
- **D-02:** The heatmap uses the same empty-state message pattern pre-trade, in place of the treemap.
- **D-03:** The P&L chart uses the same empty-state message pattern until at least 2 snapshot points exist to draw a line.
- **D-04:** The 30-second portfolio snapshot recorder starts at app startup (in the FastAPI `lifespan`), not gated on the first trade — it records a flat $10,000 history from minute one regardless of whether the user has traded yet. This also means the P&L chart's empty-state window is short-lived even for a user who hasn't traded (fills in within ~60s of app start), and portfolio snapshot recording does not need a "first trade" trigger to begin — only the existing "immediately after each trade" trigger is additional to the always-on 30s cadence. — **Reversibility:** reversible — purely a background task start condition, easy to change later.

### Ticker selection consistency
- **D-05:** Clicking a positions-table row selects that ticker and drives the main chart, using the same `onSelect(ticker)` pattern `WatchlistPanel` already uses via `page.tsx`'s `selectedTicker` state.
- **D-06:** Clicking a heatmap tile does the same — all three ticker surfaces (watchlist, positions table, heatmap) converge on one shared `selectedTicker` state in `page.tsx`.
- **D-07:** Selecting a ticker from any of the three surfaces also prefills the trade bar's ticker field, so the flow is: click a row/tile → chart updates → trade bar is ready to buy/sell that ticker without retyping it.
- **D-08:** The currently-selected ticker gets a consistent visual highlight (e.g. accent-yellow border/background) wherever it appears — watchlist row, positions row, heatmap tile — reusing whatever selected-row treatment `WatchlistPanel` already has, rather than only showing selection via the chart changing.

### Claude's Discretion
User discussed 2 of the 4 offered areas (Empty portfolio state, Ticker selection consistency) and was satisfied with that coverage. The following were offered but not discussed — Claude's judgment applies, informed by PLAN.md and existing Phase 1 patterns:
- **Trade bar placement & layout** — where it sits in the grid, exact field/button arrangement. PLAN.md §2 locks purple (`#753991`) for submit buttons; no confirmation dialog (already established for trades). Prefill behavior is locked by D-07 above.
- **Header live stats layout** — how portfolio total value, cash balance, and the connection status dot arrange relative to the existing "FinAlly" title / "Connection: {status}" text in `page.tsx:24-32`. Whether value/cash flash on change like prices do is Claude's call — PLAN.md only specifies flash for watchlist prices (§2), not header stats.
- **Trade execution & snapshot write serialization** — SQLite is WAL-mode with `autocommit=True` (`backend/app/db/connection.py`); trade execution touches `positions`, `trades`, `users_profile.cash_balance`, and `portfolio_snapshots` across multiple statements. Whether to wrap a trade in an explicit transaction, and how the 30s snapshot task avoids interleaving badly with concurrent trade writes, is a backend implementation detail — flagged in `.planning/STATE.md` under Blockers/Concerns for Phase 2, not something the user needs to decide.
- **Heatmap treemap library choice** — mirrors the Phase 1 precedent of picking a charting library without asking (Lightweight Charts was Claude's call there); PLAN.md §10 doesn't mandate a specific treemap library.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Master specification
- `planning/PLAN.md` §2 (color scheme, purple submit buttons), §7 (Database — positions/trades/portfolio_snapshots schema), §8 (API Endpoints — Portfolio), §10 (Frontend Design — heatmap, P&L chart, positions table, trade bar, header) — authoritative spec for schema, endpoints, and UI elements this phase builds
- `planning/MARKET_DATA_SUMMARY.md` — summary of the completed market data subsystem this phase's trade execution reads prices from

### Codebase maps
- `.planning/codebase/ARCHITECTURE.md` — system layering; note the Portfolio & Trading Layer section is written as "planned" and predates Phase 1's actual implementation (see `code_context` below for what's now real)
- `.planning/codebase/STRUCTURE.md` — directory layout and naming conventions for `app/portfolio/`
- `.planning/codebase/CONCERNS.md` — known gaps, including the SQLite write-serialization concern for snapshot + trade writes (see Claude's Discretion above)
- `.planning/codebase/STACK.md` — confirmed dependency versions

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — PORT-01, PORT-02, PORT-03, PORT-04, UI-04, UI-05, UI-06, UI-07, UI-09, TEST-01
- `.planning/ROADMAP.md` Phase 2 section — success criteria and phase notes (active-ticker-set extension, snapshot dual-trigger)

### Prior phase context
- `.planning/phases/01-live-market-terminal/01-CONTEXT.md` — Phase 1 decisions (Lightweight Charts, inline watchlist edit UX, dark theme tokens) this phase's frontend work extends
- `.planning/PROJECT.md` — Key Decisions table (theme tokens locked, `lightweight-charts@5.2.1`, FailoverMarketDataSource behavior)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/db/connection.py` `get_active_tickers()` — already computes watchlist ∪ open-positions-with-quantity>0; once trades write real positions, this function's second half becomes live (currently always empty since `positions` has no rows yet).
- `backend/app/db/connection.py` `ticker_has_open_position()` — already checks `positions.quantity > 0`; the watchlist router already calls this on ticker removal (Phase 1 built this defensively ahead of Phase 2).
- `backend/app/db/schema.sql` — full six-table schema already exists and is seeded; `positions`, `trades`, `portfolio_snapshots` tables are ready with the exact columns PLAN.md §7 specifies (no migration needed, just start writing to them).
- `frontend/app/page.tsx` — `selectedTicker` state + `onSelect` prop pattern already established via `WatchlistPanel`; D-05/D-06/D-07 extend this same pattern to the new components rather than inventing a new one.
- `frontend/hooks/usePriceStream.ts` (referenced by page.tsx) — already exposes `prices`, `history`, `timeline`, `status`; portfolio valuation and the header's live total value will read from `prices` the same way the watchlist does.
- `backend/app/main.py` — `lifespan()` already the place where `source.start(tickers)` runs; the 30s snapshot background task (D-04) starts here alongside it.

### Established Patterns
- Factory pattern for routers: `create_watchlist_router(get_conn, market_source, price_cache)` returns a fresh `APIRouter` — mirror this for `create_portfolio_router(...)`.
- DB write-then-external-call ordering: `watchlist/router.py`'s `add_to_watchlist` writes to SQLite first, then calls `market_source.add_ticker()` — same ordering logic likely applies to trade execution (write trade/position/cash first, since that's the source of truth; price lookup already happened before the write).
- Ticker normalization via `normalize_ticker()` (`app/market/interface.py`) — apply consistently to any ticker accepted in a trade request.
- Pydantic request models with `field_validator` for normalization (see `AddTickerRequest` in `watchlist/router.py`) — mirror for the trade request body.

### Integration Points
- `backend/app/portfolio/` — empty placeholder; this phase adds the portfolio router (`GET /api/portfolio`, `POST /api/portfolio/trade`, `GET /api/portfolio/history`) and trade execution / P&L logic.
- `backend/app/main.py` — mount the new portfolio router alongside the existing watchlist and stream routers; add the snapshot background task to `lifespan()`.
- `frontend/app/page.tsx` — extend the grid layout to add positions table, heatmap, P&L chart, trade bar; extend the header (currently just title + connection text) with live value/cash/status dot.
- `frontend/components/` — new components needed: positions table, heatmap (treemap), P&L chart, trade bar; existing `WatchlistPanel.tsx` selection pattern and `PriceChart.tsx` (Lightweight Charts) are the templates to follow.

</code_context>

<specifics>
## Specific Ideas

No specific visual references or "I want it like X" examples came up. The empty-state message wording ("No positions yet — buy shares to get started") was Claude's example phrasing during discussion, not a locked string — copy is open to refinement during planning/implementation as long as it follows the same terse, terminal-appropriate tone.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. Trade bar layout and header stats layout were offered as discussable areas but the user was satisfied after covering empty states and ticker selection; both remain in-scope for this phase, just left to Claude's discretion (see Claude's Discretion above) rather than deferred to a future phase.

</deferred>

---

*Phase: 2-Portfolio & Trading*
*Context gathered: 2026-08-23*
