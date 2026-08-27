---
phase: 02
slug: portfolio-trading
status: verified
threats_open: 0
asvs_level: 1
created: 2026-08-25
---

# Phase 02 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| browser → `POST /api/portfolio/trade` | Untrusted ticker, side, and quantity cross into money-mutating code | ticker (string), side (enum), quantity (float) |
| trade handler → SQLite | Four writes must land as one unit or not at all | cash_balance, positions, trades, portfolio_snapshots rows |
| PriceCache → fill price | The only source of the price a market order fills at | float price |
| API response → React render | Server-supplied strings and numbers become DOM content | ticker, error detail, P&L strings |
| background task → SQLite | An unattended writer runs for the life of the process against the shared connection | portfolio_snapshots rows |
| `GET /api/portfolio/history` → browser | An unbounded table becomes a response payload | time-series snapshot rows |
| snapshot rows → charting library | Stored timestamps become time values the library validates | timestamp, value |
| npm registry → frontend bundle | `recharts` executes in the browser as part of the shipped static export | third-party package code |
| `/api/portfolio` response → SVG render | Server-supplied ticker strings and numbers become SVG text and geometry | ticker, P&L, weight |
| user click → shared selection state | Tile and row clicks mutate the state that drives the chart and the trade bar | ticker (string) |
| browser → FastAPI `/api/*` | Same-origin, unauthenticated, single-user local app; a repeating client-initiated read across this boundary | polled GET requests every 10s |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-02-01 | Tampering | `TradeRequest` fields reaching SQL | high | mitigate | All queries in `trades.py`/`valuation.py`/`snapshots.py`/`router.py` use `?` placeholders; `ticker` validated via `normalize_ticker` + `_TICKER_PATTERN` (`^[A-Z.\-]+$`) — confirmed in `app/portfolio/router.py:23,36-37` | closed |
| T-02-02 | Tampering | partially-applied trade under `autocommit=True` | high | mitigate | Explicit `BEGIN`/`COMMIT`/`ROLLBACK` wraps the four writes — confirmed in `app/portfolio/trades.py:126,144,146` | closed |
| T-02-03 | Tampering | double-spend from two concurrent trade requests reading stale cash | high | mitigate | No await between `BEGIN` and `COMMIT`; synchronous SQLite calls on the single-threaded event loop prevent interleaving — confirmed by code structure in `trades.py` | closed |
| T-02-04 | Tampering | quantity clamped rather than refused, letting an over-budget order partially fill | high | mitigate | Sufficiency checks raise `TradeError` before the transaction opens — confirmed in `app/portfolio/trades.py:101-102,109-110` | closed |
| T-02-05 | Tampering | float drift admitting an over-large sell or leaving dust positions | medium | mitigate | `POSITION_EPSILON` guards comparisons and zeroes residual dust — confirmed in `app/portfolio/trades.py:34,118` | closed |
| T-02-06 | Information Disclosure | error responses leaking database internals or file paths | low | mitigate | Only curated `TradeError.detail` reaches the client via `HTTPException(400, ...)`; unexpected exceptions fall through as generic 500 — confirmed in `app/portfolio/router.py:79-85` | closed |
| T-02-07 | Repudiation | trade history mutated or overwritten | low | accept | `trades` table is append-only INSERT with a fresh UUID per row; no UPDATE/DELETE path exists. Accepted at ASVS L1 for a single-user simulated portfolio. | closed |
| T-02-08 | Tampering | rendering server-supplied `detail` and ticker strings into the DOM | medium | mitigate | Values render as JSX text children (React-escaped); no `dangerouslySetInnerHTML` anywhere in `frontend/` — confirmed via repo-wide grep | closed |
| T-02-01-SC | Tampering | package-manager installs (Plan 01) | n/a | accept | Plan 01 adds no npm/Python package. | closed |
| T-02-09 | Denial of Service | unbounded `portfolio_snapshots` growth at 2 rows/minute forever | medium | mitigate | `HISTORY_LIMIT = 2000` caps the response — confirmed in `app/portfolio/snapshots.py:31,57` | closed |
| T-02-10 | Denial of Service | a snapshot loop iteration raising and killing the recorder | medium | mitigate | Loop catches and logs non-cancellation exceptions and continues; `CancelledError` re-raised — confirmed in `app/portfolio/snapshots.py:103,105,128` | closed |
| T-02-11 | Tampering | background writer landing inside a trade's open transaction | high | mitigate | Loop's only suspension point is `asyncio.sleep`; no SQLite call offloaded to a thread — confirmed by module structure | closed |
| T-02-12 | Denial of Service | the loop writing to a closed connection during shutdown | medium | mitigate | `stop_snapshot_task` awaited in `lifespan` before `conn.close()` — confirmed in `app/main.py:19,54` and `app/portfolio/snapshots.py:120` | closed |
| T-02-13 | Information Disclosure | history endpoint exposing internal row ids or file paths | low | accept | Response carries only `time`, `value`, `recorded_at`; row `id` never serialized. Single-user app, no auth boundary at ASVS L1. | closed |
| T-02-14 | Tampering | snapshot values rendered into the DOM | low | mitigate | Numbers rendered through the charting library's typed API; error branch uses a JSX text child — confirmed via no-`dangerouslySetInnerHTML` grep | closed |
| T-02-02-SC | Tampering | package-manager installs (Plan 02) | n/a | accept | Plan 02 adds no npm/Python package; `lightweight-charts` already installed and cleared in Phase 1. | closed |
| T-02-03-SC | Tampering | `npm install recharts` | high | mitigate | Blocking-human legitimacy gate in `02-03-PLAN.md` Task 2 required manual confirmation of the canonical `recharts/recharts` repo and version history before install — confirmed by `"recharts": "^3.10.1"` in `frontend/package.json` and gate record in the plan | closed |
| T-02-15 | Tampering | ticker and P&L strings rendered as SVG `<text>` and table cells | medium | mitigate | JSX text children (React-escaped in SVG same as HTML); numeric props reach Recharts through its typed API — confirmed via no-`dangerouslySetInnerHTML` grep | closed |
| T-02-16 | Denial of Service | treemap re-layout/re-animation on every price tick | medium | mitigate | `isAnimationActive={false}` on `Treemap` — confirmed in `frontend/components/PortfolioHeatmap.tsx:132` | closed |
| T-02-17 | Information Disclosure | tooltip/label exposing more than the user's own positions | low | mitigate | Treemap dataset built solely from `GET /api/portfolio`'s `positions` prop, scoped to the single user — confirmed in `frontend/components/PortfolioHeatmap.tsx:104-107` | closed |
| T-02-18 | Denial of Service | `ResponsiveContainer` measuring a zero-height parent and looping | low | mitigate | Heatmap row carries explicit bounded height; treemap not mounted when `positions.length === 0` — confirmed in `frontend/components/PortfolioHeatmap.tsx:105,128` | closed |
| T-02-04A | Denial of Service | repeating GET /api/portfolio + GET /api/portfolio/history from the browser | low | accept | Two small reads every 10s against a local single-user SQLite app; interval cleared on unmount — confirmed in `frontend/hooks/usePortfolio.ts:167-168` | closed |
| T-02-04B | Information Disclosure | GET /api/portfolio/history response body | low | accept | Simulated portfolio values only, same-origin, no credentials/secrets in payload. | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on (high) count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-02-01 | T-02-07 | Append-only trade log needs no stronger audit control at ASVS L1 for a single-user simulated portfolio | Plan 02-01 author | 2026-08-25 |
| R-02-02 | T-02-01-SC | No package installs in Plan 01 | Plan 02-01 author | 2026-08-25 |
| R-02-03 | T-02-13 | History response carries no internal ids; no auth boundary exists at ASVS L1 | Plan 02-02 author | 2026-08-25 |
| R-02-04 | T-02-02-SC | No package installs in Plan 02 | Plan 02-02 author | 2026-08-25 |
| R-02-05 | T-02-04A | Low-volume polling against a local single-user app; timer is cleaned up on unmount | Plan 02-04 author | 2026-08-25 |
| R-02-06 | T-02-04B | Response body carries only simulated, same-origin, non-sensitive values | Plan 02-04 author | 2026-08-25 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-08-25 | 22 | 22 | 0 | gsd-secure-phase (L1 grep-depth, register authored at plan time) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-08-25
