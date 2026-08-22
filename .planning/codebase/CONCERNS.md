# Codebase Concerns

**Analysis Date:** 2026-08-22

## Tech Debt

**Missing LiteLLM Dependency:**
- Issue: The backend `pyproject.toml` does not include `litellm` as a dependency, but the PLAN.md specifies LiteLLM should be used for all LLM integration via OpenRouter
- Files: `backend/pyproject.toml`
- Impact: The LLM module cannot be implemented until this dependency is added; any attempt to import or use LiteLLM will fail at runtime
- Fix approach: Add `litellm>=1.0.0` to the `dependencies` list in `pyproject.toml` and run `uv sync` to update the lockfile

**Incomplete Massive API Failover Implementation:**
- Issue: The PLAN.md (§5, §6) specifies that if Massive API requests fail (auth errors, rate limits, network errors, service errors), the backend should "permanently fail over to the built-in simulator for the remainder of the run; it does not attempt to switch back to Massive"
- Files: `backend/app/market/massive_client.py` (lines 118-121)
- Current behavior: On error, logs the failure and retries on the next poll interval indefinitely
- Impact: A misconfigured API key, rate limit exceeded, or service outage causes repeated failed API calls for the lifetime of the app, wasting resources and delaying market data updates. The user doesn't get the promised automatic failover to the simulator
- Fix approach: Modify `_poll_once()` to catch exceptions, flag a permanent error state, stop the polling task, transfer tracked tickers to the simulator instance, and ensure no further Massive API calls are attempted

**Unhandled Exceptions in Simulator Loop:**
- Issue: The simulator's `_run_loop()` method in `SimulatorDataSource` catches all exceptions and logs them, but then continues the loop
- Files: `backend/app/market/simulator.py` (lines 262-272)
- Current code: `except Exception: logger.exception(...)`
- Impact: A transient exception during price update generation could cause a single tick to be missed silently, degrading data quality; critical bugs in price generation could be masked
- Fix approach: Determine which exceptions are transient (and safe to retry) vs fatal; re-raise fatal exceptions to exit the loop and surface the error to the app startup; log transient exceptions but continue

## Known Bugs

**SSE Stream May Miss Updates on High-Frequency Price Changes:**
- Symptoms: If market data updates very rapidly (faster than the 500ms SSE interval), clients may not receive every intermediate price update
- Files: `backend/app/market/stream.py` (lines 55, 85)
- Trigger: High-frequency data source with very small time intervals between updates
- Workaround: Clients accumulate consecutive SSE events and render based on the last received update; no data is lost, just intermediate states may be skipped
- Note: This is a design choice (500ms updates via SSE is efficient); if per-tick updates are critical, consider WebSocket instead

## Security Considerations

**Environment Variables Not Validated:**
- Risk: If `OPENROUTER_API_KEY` is not set, the LLM module will fail at runtime instead of failing fast at startup
- Files: `backend/app/market/factory.py` (shows the pattern for checking `MASSIVE_API_KEY`), but no equivalent validation exists for the LLM module (not yet implemented)
- Current mitigation: None; the app will start but fail when the first chat request is made
- Recommendations: On app startup, validate all required environment variables (`OPENROUTER_API_KEY`, `MASSIVE_API_KEY` if intended to use real data) and fail fast with a clear error message if missing. Log a warning for optional keys that are not set.

**API Key Passed to RESTClient Without Validation:**
- Risk: If `MASSIVE_API_KEY` is set to an invalid value (empty string, whitespace, malformed key), the factory still creates a `MassiveDataSource` with it
- Files: `backend/app/market/factory.py` (line 24)
- Current mitigation: The factory checks `.strip()` but doesn't validate format; invalid keys are caught at the first poll attempt (line 118-121 in massive_client.py) rather than startup
- Recommendations: Perform basic validation (non-empty, reasonable length) at initialization time; fail fast if invalid

**Unencrypted Secrets in .env File:**
- Risk: The `.env` file contains `OPENROUTER_API_KEY` in plain text and is gitignored but could be exposed via misconfiguration or backups
- Files: `.env` (not in repo, but .env.example should be created to show the pattern)
- Current mitigation: `.env` is in `.gitignore`; secrets are not committed
- Recommendations: Create `.env.example` with placeholder values; document in README that `.env` should never be committed and should be gitignored; consider documenting secure patterns (e.g., using environment variable providers in production)

## Performance Bottlenecks

**Correlation Matrix Rebuild on Every Ticker Change:**
- Problem: Every time a ticker is added or removed, the simulator rebuilds the entire Cholesky decomposition (O(n²) time complexity)
- Files: `backend/app/market/simulator.py` (lines 120-125, 154-172)
- Cause: Correlations between tickers must be recomputed whenever the ticker set changes
- Current capacity: Works fine up to ~50 tickers; for 1000+ tickers, rebuilding becomes noticeable
- Improvement path: Cache Cholesky matrices for common ticker sets; use incremental updates instead of full recomputation; lazy rebuild (rebuild only when needed for the next step) to batch multiple changes

**Inefficient Price Cache Snapshot in SSE Stream:**
- Problem: Every SSE event creates a shallow copy of the entire price cache dictionary (`get_all()` at line 78 in stream.py)
- Files: `backend/app/market/stream.py` (lines 78-83), `backend/app/market/cache.py` (lines 49-52)
- Cause: JSON serialization requires a dict copy; even with 1000+ tickers, this is a dict copy operation, not too expensive, but could be optimized
- Current capacity: With 10-100 tickers, negligible impact; with 10k+ tickers, SSE event generation becomes bottleneck
- Improvement path: Only include changed tickers in SSE events (delta updates); use a diff mechanism to send only what changed since the last event

**Massive API Free Tier Limited to 5 req/min:**
- Problem: Free tier allows only 5 requests per minute (poll interval 15 seconds), which means stale data for 15 seconds between updates
- Files: `backend/app/market/massive_client.py` (line 32)
- Cause: Polygon.io's API rate limits are based on tier
- Current capacity: Acceptable for a demo or low-activity user; not suitable for high-frequency trading scenarios
- Improvement path: Document rate limits clearly in the app; provide option to configure poll intervals; suggest users upgrade to paid tier for real trading; consider batch API calls to multiple tickers per request

## Fragile Areas

**Market Data Source Abstraction Not Fully Resilient:**
- Files: `backend/app/market/interface.py`, `backend/app/market/factory.py`, `backend/app/market/massive_client.py`, `backend/app/market/simulator.py`
- Why fragile: The factory creates one or the other data source at startup, but there's no failover mechanism built in. If Massive starts successfully but then fails later, the app is stuck with broken Massive polling; the simulator has no way to take over dynamically
- Safe modification: Design a decorator or wrapper around the MarketDataSource that monitors for repeated failures and automatically switches to a fallback source; implement this as a layer above the factory
- Test coverage: No tests cover the failover scenario (Massive starts, then fails 10 times in a row); tests only cover factory selection at initialization time

**Empty Directory Stubs Create Silent Failures:**
- Files: `backend/app/portfolio/`, `backend/app/watchlist/`, `backend/app/llm/`, `backend/app/db/`
- Why fragile: These directories exist but are empty (only `__pycache__/`). If the app tries to import from these modules before they're implemented, Python will succeed (empty module) but not provide the expected functionality. Imports like `from app.portfolio import ...` will fail at runtime with "no module named" only if `__init__.py` is not present; if an empty `__init__.py` exists, the import succeeds but the module is useless
- Safe modification: Add a `__init__.py` with a clear "not implemented" docstring and a `NotImplementedError` if the module is imported; or delete the directories until they're ready to be implemented
- Test coverage: None; there are no tests for portfolio, watchlist, llm, or db modules

**Exception Handling During Market Data Polling:**
- Files: `backend/app/market/simulator.py` (line 270), `backend/app/market/massive_client.py` (line 118)
- Why fragile: Both sources silently catch and log exceptions during polling. A bug in price generation, cache update, or API parsing could be masked by a generic log line. The app appears to be running fine even if price updates have failed for 10 ticks in a row
- Safe modification: Distinguish between transient and fatal errors; fail the polling task and alert the app on fatal errors; log metrics on the number of consecutive transient errors; add monitoring/alerting
- Test coverage: No tests cover exception scenarios during the polling loop

## Scaling Limits

**In-Memory Price Cache Without Size Limits:**
- Current capacity: Stores one `PriceUpdate` per ticker; with 100 tickers, negligible memory (each `PriceUpdate` is ~300 bytes)
- Limit: At 100,000 tickers, the cache would be ~30 MB of memory; not critical for a single user, but not designed for multi-user or multi-instrument scenarios
- Scaling path: Add TTL or LRU eviction policy to PriceCache; persist historical prices to SQLite; paginate large price sets in API responses

**SQLite Database Without Concurrent Write Protection:**
- Current capacity: Single-user app with periodic snapshot writes (~every 30 seconds)
- Limit: SQLite allows only one writer at a time; with multiple background tasks writing (market data, portfolio snapshots, chat messages), contention is possible
- Scaling path: Add write queue with serialization; use WAL (Write-Ahead Logging) mode in SQLite; consider upgrading to Postgres for true multi-user scenarios

**Event Loop Blocking on Synchronous Operations:**
- Files: `backend/app/market/massive_client.py` (lines 96-97)
- Current code: Uses `asyncio.to_thread()` to run the synchronous Massive REST client in a thread
- Scaling path: This is already handled well; no blocking issues expected

## Dependencies at Risk

**Massive API Client Dependency on External Service:**
- Risk: If Polygon.io's Massive API service goes down, even with a valid API key, the app cannot fetch real market data
- Impact: Falls back to the simulator (once failover is implemented), so the app remains functional but with simulated data
- Migration plan: Already implemented — the app defaults to the simulator and only uses Massive if explicitly configured; no migration needed

**numpy Dependency for Cholesky Decomposition:**
- Risk: numpy is a large external dependency; if it has security vulnerabilities or compatibility issues, the market simulator is affected
- Impact: Price simulation would fail if numpy is not available or incompatible
- Migration plan: numpy is standard in Python data science; alternatives (manual matrix decomposition) would be significantly slower; keep numpy as a dependency but monitor for vulnerabilities

**LiteLLM Dependency (Once Added):**
- Risk: LiteLLM is a wrapper around multiple LLM providers; if it has bugs or incompatibilities with the OpenRouter API, chat functionality will fail
- Impact: The chat feature will not work
- Migration plan: LiteLLM is well-maintained; if issues arise, alternatives include direct OpenAI or Anthropic SDK usage, or raw HTTP requests to OpenRouter

## Missing Critical Features

**No Database Module Implementation:**
- Problem: The `db` module is empty, but the PLAN.md specifies:
  - Schema definitions for users_profile, watchlist, positions, trades, portfolio_snapshots, chat_messages
  - Lazy initialization on first request
  - Seed data with 10 default watchlist tickers and $10k initial cash
- Blocks: Portfolio management, trade history, watchlist persistence, chat history, P&L tracking
- Impact: Without this, the entire portfolio and trading system cannot function

**No Portfolio Module Implementation:**
- Problem: The `portfolio` module is empty, but the PLAN.md specifies:
  - GET /api/portfolio endpoint
  - POST /api/portfolio/trade endpoint with validation (cash/quantity checks)
  - GET /api/portfolio/history endpoint
  - Trade execution logic with P&L calculation
- Blocks: Users cannot buy/sell, view holdings, or track P&L

**No Watchlist Module Implementation:**
- Problem: The `watchlist` module is empty, but the PLAN.md specifies:
  - GET /api/watchlist endpoint
  - POST /api/watchlist endpoint (add ticker)
  - DELETE /api/watchlist/{ticker} endpoint (remove ticker)
- Blocks: Users cannot manage their watchlist

**No LLM Integration Module:**
- Problem: The `llm` module is empty, but the PLAN.md specifies:
  - POST /api/chat endpoint
  - LLM system prompt + portfolio context + conversation history
  - Structured JSON response parsing
  - Auto-execution of trades and watchlist changes
  - Trade validation and error handling
  - LLM_MOCK support for testing
- Blocks: AI assistant functionality; this is a core feature

**No Main FastAPI Application:**
- Problem: `backend/app/__init__.py` is empty; there's no `main.py` or entry point that creates the FastAPI app and registers routes
- Blocks: Cannot start the backend server; no HTTP endpoints available
- Expected structure: A main entry point (e.g., `backend/main.py` or `backend/app/main.py`) that:
  - Creates the FastAPI app instance
  - Initializes the database (lazy)
  - Creates the PriceCache and market data source
  - Registers routers from market, portfolio, watchlist, llm, db modules
  - Starts the market data source on app startup
  - Stops the market data source on app shutdown

**No Frontend Implementation:**
- Problem: `frontend/` directory is empty; no Next.js project exists
- Blocks: Users have no UI to view prices, trade, chat, or manage portfolio
- Expected: A complete Next.js app with components, state management, API client, and styling

**No Docker Support:**
- Problem: No Dockerfile, docker-compose.yml, or deployment configuration
- Blocks: Cannot run the app in Docker (the primary deployment method per the spec)
- Expected: A multi-stage Dockerfile that builds Next.js frontend, installs Python backend, and runs FastAPI on port 8000

**No Start/Stop Scripts:**
- Problem: `scripts/` directory doesn't exist; no shell scripts for launching the app
- Blocks: Users cannot easily start/stop the Docker container; must use raw docker commands
- Expected: `scripts/start_mac.sh`, `scripts/stop_mac.sh`, `scripts/start_windows.ps1`, `scripts/stop_windows.ps1`

**No .env.example File:**
- Problem: README references `.env.example` but it doesn't exist in the repo
- Blocks: Users don't know what environment variables to set
- Expected: A committed `.env.example` file with placeholders for `OPENROUTER_API_KEY`, `MASSIVE_API_KEY`, and `LLM_MOCK`

## Test Coverage Gaps

**No Tests for Portfolio Functionality:**
- What's not tested: Trade execution, P&L calculation, position tracking, cash balance updates, insufficient cash/quantity validation
- Files: `backend/app/portfolio/` (not implemented)
- Risk: Trades could be executed incorrectly; users could lose money (even though it's virtual)
- Priority: High — this is core functionality

**No Tests for Watchlist Management:**
- What's not tested: Adding/removing tickers, watchlist persistence, duplicate prevention, UNIQUE constraint on (user_id, ticker)
- Files: `backend/app/watchlist/` (not implemented)
- Risk: Duplicate watchlist entries, tickers disappearing unexpectedly
- Priority: Medium

**No Tests for Database Layer:**
- What's not tested: Lazy initialization, schema creation, seed data, migrations, edge cases (corrupted DB, permissions, disk full)
- Files: `backend/app/db/` (not implemented)
- Risk: App fails to start if database initialization fails; data loss if schema is incorrect
- Priority: High

**No Tests for LLM Integration:**
- What's not tested: Structured output parsing, trade validation during auto-execution, chat history persistence, error handling (LLM timeout, malformed response)
- Files: `backend/app/llm/` (not implemented)
- Risk: Chat feature could crash; trades could be executed with bad data; timeouts not handled
- Priority: High

**No Tests for Market Data Failover:**
- What's not tested: Massive API failure scenarios (401, 429, network timeout); permanent switch to simulator
- Files: `backend/app/market/massive_client.py`
- Risk: Failover may not work as specified; app could get stuck with broken API client
- Priority: High — this is explicitly specified in the PLAN

**No E2E Tests:**
- What's not tested: Full end-to-end workflows (fresh start → watchlist → trade → portfolio update → chat)
- Files: `test/` (no test files, only node_modules)
- Risk: Integration bugs only discovered in manual testing
- Priority: Medium — E2E tests are listed in the PLAN but not implemented

**No Fixtures or Factories for Test Data:**
- What's not tested: Conftest.py is empty; no reusable test fixtures for prices, positions, trades, chat messages
- Files: `backend/tests/conftest.py`
- Risk: Tests duplicate setup code; brittle and hard to maintain
- Priority: Low — but would improve test quality

---

*Concerns audit: 2026-08-22*
