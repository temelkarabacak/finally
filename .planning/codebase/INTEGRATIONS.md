# External Integrations

**Analysis Date:** 2026-08-22

## APIs & External Services

**Market Data:**
- Massive (Polygon.io) - Real-time stock market data via REST API
  - SDK/Client: `massive` package (1.0.0+)
  - Auth: `MASSIVE_API_KEY` environment variable
  - Usage: `backend/app/market/massive_client.py` — implements `MassiveDataSource` class that polls `/v2/snapshot/locale/us/markets/stocks/tickers` endpoint
  - Rate limits: Free tier 5 req/min (polls every 15s); Paid tiers support 2-5s polling (configurable)
  - Failure behavior: On authentication, rate limit, network, or service errors at startup or during polling, logs error and permanently fails over to built-in simulator for remainder of run (see PLAN.md §5, §6)

**LLM Integration (Planned):**
- OpenRouter via LiteLLM - AI chat and trade execution
  - SDK/Client: `litellm` (not yet in dependencies; to be added)
  - Auth: `OPENROUTER_API_KEY` environment variable
  - Model: `openrouter/openai/gpt-oss-120b` with Cerebras inference provider (from project PLAN.md §9)
  - Timeout: 30 seconds per request (aborts with generic retry message if exceeded; no trade executed)
  - Status: Planned; specification in PLAN.md §9; implementation not yet started

## Data Storage

**Databases:**
- SQLite (planned, not yet implemented)
  - Connection: File-based at `db/finally.db` (volume-mounted in Docker)
  - Client: No ORM; raw SQL or sqlite3 module planned
  - Schema: Defined in PLAN.md §7 (users_profile, watchlist, positions, trades, portfolio_snapshots, chat_messages tables)
  - Lazy initialization: Backend checks on startup and creates schema if missing (planned)

**File Storage:**
- Local filesystem only
  - SQLite database file: `db/finally.db` (persisted via Docker volume)
  - Frontend static build: Served by FastAPI from `app/static/` or similar (planned; Next.js static export)

**Caching:**
- In-memory price cache
  - Implementation: `backend/app/market/cache.py` — `PriceCache` class
  - Thread-safe (uses `asyncio.Lock`)
  - Stores latest price, previous price, timestamp per ticker
  - Scope: Union of watchlist tickers + tickers with open positions
  - No external caching service (Redis, Memcached)

## Authentication & Identity

**Auth Provider:**
- Custom / None
  - Implementation: No user authentication; hardcoded single user with `user_id="default"` (see PLAN.md §7)
  - Approach: All routes serve the default user; multi-user support planned for future but schema already has `user_id` column on all tables

## Monitoring & Observability

**Error Tracking:**
- None detected
  - Status: No Sentry, Rollbar, or similar integration found in codebase

**Logs:**
- Python `logging` module (standard library)
  - Approach: Used throughout backend (`backend/app/market/simulator.py`, `backend/app/market/massive_client.py` show `logger = logging.getLogger(__name__)`)
  - Output: Console (stderr by default when run via Uvicorn)
  - Note: Rich library (`backend/market_data_demo.py`) used for formatted console output in demo but not in main API

## CI/CD & Deployment

**Hosting:**
- Docker container (planned)
  - Specification in PLAN.md §11: Multi-stage Dockerfile (Node 20 for frontend build → Python 3.12 slim for backend + static files)
  - Port: 8000 (single container, single port)
  - Status: Not yet implemented

**CI Pipeline:**
- None detected
  - GitHub Actions workflows may exist in `.github/workflows/` but not analyzed for this mapping
  - E2E testing infrastructure: Playwright in `test/` directory (docker-compose.test.yml planned but not yet implemented)

**Start/Stop Scripts:**
- Bash/PowerShell wrappers in `scripts/` (planned)
  - Status: Not yet implemented

## Environment Configuration

**Required env vars:**
- `OPENROUTER_API_KEY` - LLM chat integration (once implemented)

**Optional env vars:**
- `MASSIVE_API_KEY` - Real market data; if absent/empty, uses built-in simulator (default)
- `LLM_MOCK=true` - Deterministic mock LLM responses for testing (once implemented)

**Secrets location:**
- `.env` file at project root (gitignored)
- Passed to Docker container via `--env-file .env` flag in start scripts (planned)
- Example `.env.example` file planned but not yet created

## Webhooks & Callbacks

**Incoming:**
- None detected

**Outgoing:**
- None currently implemented
- Planned: LLM chat interface may trigger trade/watchlist changes via `/api/chat` endpoint response parsing (PLAN.md §9), but these are processed synchronously within the same request, not webhooks

## Real-Time Data Flow

**Server-Sent Events (SSE):**
- Endpoint: `GET /api/stream/prices`
- Implementation: `backend/app/market/stream.py` — `create_stream_router()` factory returns FastAPI APIRouter
- Data source: `PriceCache` (reads from either simulator or Massive poller, depending on configuration)
- Cadence: ~500ms (simulator default), configurable per source
- Payload: `PriceUpdate.to_dict()` — ticker, price, previous_price, timestamp, change, change_percent, direction
- Client handling: Frontend uses native `EventSource` API with automatic reconnection

---

*Integration audit: 2026-08-22*
