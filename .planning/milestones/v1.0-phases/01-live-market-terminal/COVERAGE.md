# Phase 1 — API Coverage Declaration

**Decided:** 2026-08-23
**Gate:** `workflow.api_coverage_gate`
**Detector result:** `detected: true` — reviewed and dismissed as a false positive.

## Declaration

No external API integration: the Massive/Polygon client already exists and is fully integrated from a prior milestone; this phase only fixes its failover behavior (PORT-05), it does not expand or newly integrate any external API capability surface.

## Why the detector fired

The detector matched the noun `api` inside the ROADMAP Phase 1 section, paired with a synthetic `(surface)` verb rather than a real integration verb (`integrate`, `wrap`, `consume`, `wire`, `onboard`). Every `api` occurrence in the phase scope refers to **this project's own internal REST/SSE endpoints** — `/api/health`, `/api/watchlist`, `/api/stream/prices` — not to a third-party capability surface being adopted.

## Evidence

| Claim | Evidence |
|---|---|
| The Massive client is pre-existing, not new | `backend/app/market/massive_client.py` (135 lines, `MassiveDataSource`) exists and is exercised by `backend/tests/market/test_factory.py` |
| It is already wired into the source-selection path | `backend/app/market/factory.py:16` `create_market_data_source()` already branches on `MASSIVE_API_KEY` |
| This phase does not widen its capability surface | PORT-05 changes only failure handling: a `_permanently_failed` guard in `_poll_once()`/`_poll_loop()` plus a `FailoverMarketDataSource` wrapper. No new Massive endpoints, no new response fields, no new SDK methods. The single SDK call `get_snapshot_all(market_type, tickers)` is unchanged. |
| No other external API is introduced | `backend/pyproject.toml` gains no new runtime dependency this phase; the only version change is bumping the existing `fastapi` floor to `>=0.138.0` |

## Consequence

No capability matrix is produced for this phase. Fabricating one would document coverage of an integration that is not happening.

Frontend package installs (`next`, `react`, `tailwindcss`, `lightweight-charts`, …) are **package** supply-chain surface, not API-capability surface. They are gated separately by the blocking package-legitimacy checkpoint in `01-01-PLAN.md` (task 1) and tracked as threat `T-01-SC`.
