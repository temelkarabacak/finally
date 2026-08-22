<!-- refreshed: 2026-08-22 -->
# Architecture

**Analysis Date:** 2026-08-22

## System Overview

FinAlly is a single Docker container serving a Python FastAPI backend that provides market data streaming and will integrate portfolio management, trading, and LLM chat. The architecture separates concerns into distinct subsystems with clear interfaces.

```text
┌─────────────────────────────────────────────────────────────┐
│                   Client Layer (Browser)                    │
│  Next.js Static Export (TypeScript)                          │
│  - Watchlist UI                                              │
│  - Chart visualizations                                      │
│  - Portfolio dashboard                                       │
│  - AI chat panel                                             │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP/SSE
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI Backend Layer                      │
│                  `backend/app/` (Python)                     │
├──────────────────┬──────────────────┬───────────────────────┤
│  Market Data     │  Portfolio/      │  Chat/               │
│  Subsystem       │  Trading Layer   │  LLM Layer           │
│  `app/market/`   │  `app/portfolio` │  `app/llm/`          │
│                  │  `app/watchlist` │                       │
├──────────────────┴──────────────────┴───────────────────────┤
│  Database Access Layer: `app/db/`                           │
│  - Schema definitions                                        │
│  - Lazy initialization                                       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    Data Layer                                │
├──────────────────┬──────────────────┬───────────────────────┤
│  Price Cache     │  SQLite DB       │  External APIs        │
│  (In-Memory)     │  `db/finally.db` │  - Massive/Polygon    │
│  Thread-safe     │  Volume-mounted  │  - OpenRouter (LLM)   │
│  `PriceCache`    │                  │                       │
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File(s) |
|-----------|----------------|---------|
| **PriceUpdate** | Immutable dataclass for price snapshot | `app/market/models.py` |
| **PriceCache** | Thread-safe in-memory price store | `app/market/cache.py` |
| **MarketDataSource** | Abstract interface for data providers | `app/market/interface.py` |
| **SimulatorDataSource** | GBM simulator implementation | `app/market/simulator.py` |
| **MassiveDataSource** | Polygon.io API client | `app/market/massive_client.py` |
| **GBMSimulator** | Geometric Brownian Motion engine | `app/market/simulator.py` |
| **Market Factory** | Creates appropriate data source | `app/market/factory.py` |
| **SSE Stream Router** | FastAPI SSE endpoint factory | `app/market/stream.py` |

## Pattern Overview

**Overall:** Dependency injection + abstract interfaces + background task architecture

**Key Characteristics:**
- **Pluggable data sources** — Two implementations (simulator, Massive) behind `MarketDataSource` interface; selected at startup via environment variable
- **Async/await throughout** — Leverages FastAPI's async model; data source lifecycle managed with `asyncio.Task`
- **Thread-safe shared state** — `PriceCache` uses `Lock` for concurrent reads/writes from SSE streaming and background update tasks
- **Factory pattern** — `create_market_data_source()` and `create_stream_router()` isolate object creation and configuration

## Layers

**Market Data Subsystem:**
- **Purpose:** Stream live prices from either a simulator or real API; make prices available to all downstream systems
- **Location:** `backend/app/market/`
- **Contains:** Price models, abstract interface, two implementations (simulator + Massive), shared cache, SSE streaming logic
- **Depends on:** Nothing in the app; external: `massive` SDK, `numpy` (for GBM math)
- **Used by:** SSE endpoint, portfolio valuation, trade execution, frontend via HTTP

**Portfolio & Trading Layer:**
- **Purpose:** Manage positions, cash balance, trades, and portfolio snapshots (P&L history)
- **Location:** `backend/app/portfolio/`, `backend/app/watchlist/`
- **Contains:** Trade execution logic, position tracking, P&L calculations, watchlist CRUD
- **Depends on:** Market Data (price lookup), Database
- **Used by:** Chat/LLM (for trade execution), API endpoints

**Chat & LLM Layer:**
- **Purpose:** Accept user messages, call LLM for analysis and trade suggestions, auto-execute trades
- **Location:** `backend/app/llm/`
- **Contains:** LLM client (LiteLLM via OpenRouter), structured output parsing, trade/watchlist action execution
- **Depends on:** Portfolio (to read context and execute actions), Market Data (for live prices)
- **Used by:** `/api/chat` endpoint

**Database Access Layer:**
- **Purpose:** Schema definitions, seed data, initialization logic
- **Location:** `backend/app/db/`
- **Contains:** SQLite schema SQL, seed scripts, database setup on first run
- **Depends on:** Nothing (pure schema/DDL)
- **Used by:** Portfolio layer

## Data Flow

### Primary Request Path: Price Updates

1. **Startup** — `create_market_data_source()` selects SimulatorDataSource or MassiveDataSource based on `MASSIVE_API_KEY` environment variable (`app/market/factory.py:16`)
2. **Start** — `await source.start(tickers)` initializes the data source and starts a background task (`app/market/simulator.py:219` or `app/market/massive_client.py:41`)
3. **Update loop** — Background task periodically calls `GBMSimulator.step()` (every 500ms) or `MassiveDataSource._poll_once()` (every 15s)
4. **Cache write** — `cache.update(ticker, price)` stores `PriceUpdate` and increments version counter (`app/market/cache.py:23`)
5. **SSE streaming** — `/api/stream/prices` endpoint detects version change and yields price JSON to client (`app/market/stream.py:76`)
6. **Client receives** — Browser's `EventSource` API receives JSON event and re-renders watchlist/chart with green/red flash animation

### Trade Execution Path

1. User sends POST to `/api/portfolio/trade` with `{ticker, quantity, side}` (planned)
2. Portfolio layer validates: sufficient cash for buy, sufficient shares for sell
3. If valid, update positions table, adjust cash balance, record trade in trades log
4. Capture portfolio value snapshot immediately (current total value vs. cost basis)
5. Return execution result

### Chat & Trade Auto-Execution

1. User sends message via `/api/chat`
2. Backend loads portfolio context (positions, cash, prices from `PriceCache`)
3. Loads last 20 chat messages from `chat_messages` table (planned)
4. Calls LLM via LiteLLM → OpenRouter with structured output schema
5. Parses JSON response: `{ message, trades[], watchlist_changes[] }`
6. Auto-executes each trade through portfolio layer (same validation as manual trades)
7. Auto-executes watchlist changes
8. Persists assistant message + executed actions to `chat_messages`
9. Returns full JSON response to client

### State Management

- **Price state** — Owned by `PriceCache`; written by market data source; read by SSE, portfolio, chat
- **Portfolio state** — SQLite tables: `positions`, `trades`, `portfolio_snapshots`, `users_profile` (planned)
- **Chat state** — SQLite table: `chat_messages` (planned)
- **Watchlist state** — SQLite table: `watchlist` (planned)

No module-level singletons except the `PriceCache` instance (created once at app startup and injected via dependency injection into data source and SSE router).

## Key Abstractions

**MarketDataSource:**
- **Purpose:** Pluggable contract for price sources (simulator or API)
- **Examples:** `SimulatorDataSource`, `MassiveDataSource`
- **Pattern:** Abstract base class (`app/market/interface.py`) with async lifecycle methods
- **Why it matters:** Allows swapping data source at startup with zero code changes; same interface for both

**PriceUpdate:**
- **Purpose:** Immutable snapshot of a price with computed properties (direction, change, change_percent)
- **Pattern:** Frozen dataclass (`app/market/models.py`)
- **Benefit:** Thread-safe, JSON-serializable, rich with derived data

**GBMSimulator:**
- **Purpose:** Generates correlated price movements using geometric Brownian motion with random events
- **Math:** `S(t+dt) = S(t) * exp((mu - 0.5*sigma^2)*dt + sigma*sqrt(dt)*Z)` where Z is correlated normal
- **Correlation:** Tech and finance groups move together; TSLA independent; ~0.1% chance per tick of 2-5% shock

## Entry Points

**FastAPI Application:**
- **Location:** `backend/app/__init__.py` (currently minimal)
- **Triggers:** `uvicorn app:app --host 0.0.0.0 --port 8000` (via Dockerfile)
- **Responsibilities:** Wire up market data source, SSE router, portfolio endpoints (when implemented), chat endpoint, serve static frontend files

**Market Data Startup:**
- **Location:** Backend application initialization (planned in main app creation)
- **Triggers:** App startup
- **Responsibilities:** Create cache, create and start data source with default watchlist tickers

**Background Tasks:**
- **Simulator loop:** `SimulatorDataSource._run_loop()` (`app/market/simulator.py:250`) — runs indefinitely, sleeps 500ms between steps
- **Massive poller:** `MassiveDataSource._poll_loop()` (`app/market/massive_client.py:83`) — runs indefinitely, sleeps 15s between polls
- **Portfolio snapshot recorder:** (planned) — runs indefinitely, records portfolio value every 30s and after each trade

## Architectural Constraints

- **Threading:** Single-threaded event loop (FastAPI/uvicorn). Market data and SSE are async tasks, not threads. `PriceCache` uses a Lock for thread-safety because the Massive client runs REST calls in a thread pool (`asyncio.to_thread()` at `app/market/massive_client.py:97`) to avoid blocking.
- **Global state:** Single `PriceCache` instance created once; injected into data source and SSE router. No module-level singletons except this.
- **Circular imports:** None detected. Imports are one-directional: `factory` → `simulator`/`massive_client`; both → `interface`/`cache`/`models`.
- **Blocking operations:** Massive REST client is synchronous; offloaded to thread pool with `asyncio.to_thread()` (`app/market/massive_client.py:97`).

## Anti-Patterns

### No Entry Point Yet

**What happens:** `backend/app/__init__.py` is empty; there's no `main()` or FastAPI app object defined
**Why it's wrong:** Can't run the backend yet; tests can't import the full app
**Do this instead:** Create a `backend/app/main.py` with FastAPI app factory; import in `__init__.py`. This will be done when the backend phases execute.

### Empty Placeholder Modules

**What happens:** `app/db/`, `app/llm/`, `app/portfolio/`, `app/watchlist/` directories exist but are empty
**Why it's wrong:** Confusion about where implementation should go; wasted directory structure
**Do this instead:** Add `__init__.py` with module-level docstrings explaining purpose; implement incrementally as phases complete.

### Market Data Only, No API Routes Yet

**What happens:** Market data subsystem is complete, but no `/api/portfolio`, `/api/chat`, or `/api/watchlist` endpoints exist
**Why it's wrong:** Frontend can't trade, chat, or manage watchlist yet
**Do this instead:** Phases will add portfolio layer (trades, positions), chat layer (LLM integration), and watchlist layer incrementally; each depends on the market data that's already complete.

## Error Handling

**Strategy:** Log and gracefully degrade; no silent failures

**Patterns:**
- **Massive API failures** (`app/market/massive_client.py:102`) — Log error, continue polling; no automatic fallback to simulator (failover must be designed during portfolio phase)
- **Market data source stop** — Idempotent; safe to call multiple times
- **SSE client disconnect** — Detected via `request.is_disconnected()`; loop exits cleanly
- **Price cache access** — No exceptions; missing tickers return `None`

## Cross-Cutting Concerns

**Logging:**
- Module-level loggers: `logger = logging.getLogger(__name__)` in each file
- Info level for startup/shutdown, debug for per-tick activity (e.g., random events)
- Client IP tracked in SSE connections

**Validation:**
- Ticker normalization via `normalize_ticker()` — uppercase, trimmed (`app/market/interface.py:8`)
- Applied consistently in both data sources and cache

**Thread Safety:**
- `PriceCache` uses `Lock` for all access
- Massive REST client calls offloaded to thread pool

---

*Architecture analysis: 2026-08-22*
