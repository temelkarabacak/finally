# Milestones

## v1.0 MVP (Shipped: 2026-08-27)

**Phases completed:** 4 phases, 15 plans, 38 tasks

**Key accomplishments:**

- SQLite lazy-init schema (six tables) + FastAPI entry point with a single module-scope PriceCache serving a Next.js 16 static export with live SSE prices for the 10 seeded default tickers, plus 105 passing backend tests.
- Watchlist CRUD (GET/POST/DELETE) wired end to end through DB, source, and UI, plus a permanent Massive-to-simulator failover with API-key log redaction — closing the CONCERNS.md gap where the old code retried a failing provider forever.
- Dark Bloomberg-style terminal with price-flash animations, per-row sparklines, and a Lightweight Charts main chart — human-verified against all 9 checkpoint items, closing out Phase 1.
- Market-order trade execution (buy/sell, fractional shares, explicit-transaction integrity) wired from a new `backend/app/portfolio/` package through `POST /api/portfolio/trade` and `GET /api/portfolio` to a new `TradeBar` + `usePortfolio` frontend, with the header showing live total value, cash, and a connection-status dot.
- A 30-second background recorder starts unconditionally at app startup and writes `portfolio_snapshots` rows for the life of the process; `GET /api/portfolio/history` serves them back oldest-first with a stable tie-break and a 2000-row cap; `PnlChart.tsx` plots them as a `lightweight-charts` line with the "Building portfolio history" empty state until at least two points exist.
- A live-revaluing positions table and a Recharts `Treemap` heatmap, both driving the same `selectedTicker` state the watchlist already owns, complete Phase 2's visual portfolio surfaces -- `recharts` entered the project only after a human approved its Task 2 legitimacy checkpoint.
- usePortfolio now re-fetches `/api/portfolio` and `/api/portfolio/history` on a 10s interval (cleared on unmount) instead of once on mount, so the P&L chart fills in on its own within ~70s of a cold start with no trade -- closing UAT gap G-02-4.
- Thinnest complete AI-chat slice: LiteLLM/OpenRouter/Cerebras structured-output call, two-transaction persistence around the one unavoidable await, a `POST /api/chat` router mirroring the existing factory pattern, and a collapsed-by-default bottom chat drawer, all wired end to end and switchable to a deterministic offline matcher via `LLM_MOCK=true`.
- LLM-proposed trades and watchlist changes now auto-execute through the exact `execute_trade()`/watchlist helpers the manual trade bar and watchlist panel call, with the reported actions payload built exclusively from executor return values and rendered inline as success/REJECTED confirmation cards in the chat.
- Exhaustive portfolio/watchlist route status-code and response-shape matrix in pytest, plus the project's first frontend component test (WatchlistPanel) and first frontend hook test (usePortfolio), all offline and hermetic.
- GET /api/chat/history restores a reloaded conversation with its trade cards; timeout and four classes of malformed structured output now collapse to one proven, shared generic-retry body that executes nothing and persists no assistant row; and the drawer greets an empty conversation with three one-click quick prompts instead of a blank box.
- Multi-stage Dockerfile packages the built FastAPI+Next.js app into one port-8000 image with a bind-mounted SQLite path and a bounded-shutdown uvicorn CMD, proven by a repeatable, idempotent `scripts/verify_container.sh` gate that also fixed the long-standing `scripts/smoke.sh` shutdown hang.
- Idempotent macOS/Linux (`start_mac.sh`/`stop_mac.sh`) and Windows (`start_windows.ps1`/`stop_windows.ps1`) lifecycle scripts for the `finally` container, with a real Docker-CLI-quirk bug caught and fixed live during acceptance verification.
- Compose-paired Playwright E2E harness runs the actual `finally` production image against a real `/api/health` healthcheck, proving the fresh-start scenario (seeded 10-ticker watchlist, $10,000.00 cash, live SSE prices) end to end while never touching the developer's real database.
- All six TEST-05 scenarios (fresh start, watchlist add/remove, buy/sell, heatmap + P&L rendering, AI chat with an inline trade, SSE reconnection) now pass twice in a row in one `docker compose` command against the real production image, closing out the phase's E2E verification requirement.

**Known verification overrides:** 1 newly acknowledged, 0 carried forward from a prior close (see STATE.md Deferred Items) — a documentation-count discrepancy on 4 pre-existing, non-blocking `react-hooks/set-state-in-effect` lint warnings; no functional gap.

---
