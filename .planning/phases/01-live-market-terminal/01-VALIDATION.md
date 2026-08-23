---
phase: 1
slug: live-market-terminal
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-23
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3+ with pytest-asyncio (`asyncio_mode = "auto"`) |
| **Config file** | `backend/pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `cd backend && uv run --extra dev pytest -v` |
| **Full suite command** | `cd backend && uv run --extra dev pytest --cov=app` |
| **Estimated runtime** | ~10 seconds |

Frontend has no test framework yet — `frontend/` is empty and TEST-04 (frontend unit tests) is explicitly assigned to Phase 3 per REQUIREMENTS.md traceability. UI-01/02/03/10 in this phase are verified manually (UAT / `/gsd-ui-review`), not by an automated frontend suite.

---

## Sampling Rate

- **After every task commit:** Run `cd backend && uv run --extra dev pytest -v`
- **After every plan wave:** Run `cd backend && uv run --extra dev pytest --cov=app`
- **Before `/gsd-verify-work`:** Full suite must be green; UI requirements verified manually
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 0 | FOUND-01 | — | N/A | integration | `pytest backend/tests/api/test_health.py -x` | ❌ W0 | ⬜ pending |
| 01-01-02 | 01 | 0 | FOUND-02 | — | N/A | unit | `pytest backend/tests/db/test_init.py -x` | ❌ W0 | ⬜ pending |
| 01-01-03 | 01 | 0 | FOUND-03 | — | N/A | integration | `pytest backend/tests/api/test_static_frontend.py -x` | ❌ W0 | ⬜ pending |
| 01-01-04 | 01 | 0 | FOUND-04 | — | N/A | integration | `pytest backend/tests/api/test_app_startup.py -x` | ❌ W0 | ⬜ pending |
| 01-02-01 | 01 | 1 | WATCH-01/02/03 | — | N/A | unit + integration | `pytest backend/tests/watchlist/ -x` | ❌ W0 | ⬜ pending |
| 01-02-02 | 01 | 1 | WATCH-04 | — | N/A | integration | `pytest backend/tests/market/test_stream.py -x` (extended) | ✅ (extend) | ⬜ pending |
| 01-03-01 | 01 | 1 | PORT-05 | — | N/A | unit | `pytest backend/tests/market/test_failover.py -x` | ❌ W0 (new) | ⬜ pending |
| 01-03-02 | 01 | 1 | PORT-05 (regression) | — | N/A | unit | `pytest backend/tests/market/test_factory.py -x` (updated) | ✅ (edit) | ⬜ pending |
| 01-04-01 | 01 | 2 | UI-01/02/03/10 | — | N/A | manual | UAT / `/gsd-ui-review` | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/api/test_health.py` — covers FOUND-01
- [ ] `backend/tests/api/test_static_frontend.py` — covers FOUND-03
- [ ] `backend/tests/api/test_app_startup.py` — covers FOUND-04
- [ ] `backend/tests/db/test_init.py` — covers FOUND-02
- [ ] `backend/tests/db/test_seed.py` — covers FOUND-02 seed data correctness
- [ ] `backend/tests/watchlist/test_router.py` — covers WATCH-01/02/03
- [ ] `backend/tests/market/test_failover.py` — covers PORT-05 (new `FailoverMarketDataSource`)
- [ ] `backend/tests/market/test_factory.py` — MODIFY existing assertions to expect the failover wrapper
- [ ] `backend/tests/conftest.py` — currently a docstring-only stub; add shared fixtures (temp SQLite path, seeded `PriceCache`, FastAPI test client with lifespan)
- [ ] Framework install: none — pytest/pytest-asyncio already present via `uv sync --extra dev`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|--------------------|
| Watchlist grid renders with flashing price updates and sparklines | UI-01, UI-02 | No frontend test framework until Phase 3 | Open `http://localhost:8000`, confirm 10 seeded tickers, watch for green/red flash on price change, confirm sparkline fills in over time |
| Clicking a ticker shows a larger chart | UI-03 | No frontend test framework until Phase 3 | Click any watchlist row, confirm Lightweight Charts chart renders for that ticker |
| Dark trading-terminal theme applied | UI-10 | Visual verification, no automated visual regression suite this phase | Confirm background colors, accent colors (`#ecad0a`/`#209dd7`/`#753991`) match PLAN.md §2 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
