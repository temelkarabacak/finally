<!-- GSD:project-start source:PROJECT.md -->

## Project

**FinAlly — AI Trading Workstation**

FinAlly is a visually stunning, single-container AI trading workstation: a Bloomberg-terminal-style app that streams live (simulated or real) market data, lets a user trade a simulated $10,000 portfolio with instant market-order fills, and includes an AI chat copilot (via LiteLLM/OpenRouter/Cerebras) that can analyze the portfolio and auto-execute trades on the user's behalf. It's the capstone project for an agentic AI coding course — built entirely by orchestrated coding agents. Full spec lives in `planning/PLAN.md`.

**Core Value:** A user can launch the app with one command, watch live prices stream in, buy/sell shares instantly, and ask the AI assistant to analyze or trade on their behalf — and it just works, end to end, in a single Docker container.

### Constraints

- **Roadmap structure**: Vertical MVP — each phase should deliver an end-to-end user-visible capability, not an isolated technical layer, given how interdependent DB/portfolio/chat are (all touch the same tables).
- **Docker**: Included as the final phase of this roadmap — the milestone isn't done until there's a working single-container deployment (per PLAN.md §11), not deferred to a later milestone.
- **Timeline**: No hard deadline — optimize for quality and completeness over speed.
- **Tech stack**: FastAPI + uv (Python backend), Next.js + TypeScript static export (frontend), SQLite (single file, lazy init), LiteLLM → OpenRouter with Cerebras inference — all fixed by PLAN.md, not open decisions.
- **Single container, single port (8000)**: FastAPI serves both `/api/*` and the static Next.js export — no CORS configuration needed, no docker-compose required for production.

<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->

## Technology Stack

## Languages

- Python 3.12+ - Backend API, market data simulation, database logic
- TypeScript/JavaScript - Frontend (Next.js project in `frontend/`, currently not implemented)

## Runtime

- Python 3.12+ (defined in `backend/pyproject.toml`)
- uv (modern Python project manager; replaces pip)
- Lockfile: `backend/uv.lock` (present)

## Frameworks

- FastAPI 0.115.0+ - API framework for HTTP endpoints and SSE streaming (`backend/app/`)
- Uvicorn 0.32.0+ - ASGI server for running FastAPI application
- pytest 8.3.0+ - Test runner
- pytest-asyncio 0.24.0+ - Async test support (FastAPI and async market data source)
- pytest-cov 5.0.0+ - Code coverage measurement
- Configuration: `backend/pyproject.toml` (lines 30-36)
- ruff 0.7.0+ - Linting (line length 100, Python 3.12 target) — see `backend/pyproject.toml` (lines 38-43)
- hatchling - Build backend for wheel packaging

## Key Dependencies

- `numpy 2.0.0+` - Geometric Brownian Motion (GBM) calculations in market simulator; used for correlated random number generation
- `massive 1.0.0+` - Polygon.io REST API client for real-time market data; provides `RESTClient` and `SnapshotMarketType` models (see `backend/app/market/massive_client.py`, line 8-9)
- `rich 13.0.0+` - Rich text and formatting for TUI; used in market data demo dashboard (`backend/market_data_demo.py`, line 15-20); Console, Layout, Live, Panel, Table components
- None currently (SQLite database planned but not yet integrated; LiteLLM for LLM planned but not yet integrated)

## Configuration

- `OPENROUTER_API_KEY` - LLM integration (not yet implemented)
- `MASSIVE_API_KEY` - Switches market data source to Polygon.io; if absent or empty, uses built-in simulator (see `backend/app/market/factory.py`)
- `LLM_MOCK` - Set to "true" for deterministic mock responses in tests (not yet implemented)
- `backend/pyproject.toml` - Python project metadata and dependencies
- `backend/uv.lock` - Dependency lockfile for reproducible builds
- Wheel package configuration: `backend/pyproject.toml` (lines 27-28) — packages the `app` module

## Platform Requirements

- Python 3.12+
- uv package manager
- `pytest` and development dependencies installed via `uv sync --extra dev`
- Single Docker container (planned; not yet implemented)
- Port 8000 (specified in PLAN.md)
- SQLite database volume mount at `/app/db/` (planned)

## Versioning Notes

- **Python**: 3.12 minimum (ensures compatibility with latest async/await patterns and type hints)
- **FastAPI**: 0.115.0+ (ensures support for modern async patterns, structured outputs, and SSE)
- **Uvicorn**: 0.32.0+ with standard extras (includes libuv for async I/O)
- **NumPy**: 2.0.0+ (major version for modern array operations)
- **Ruff**: 0.7.0+ (modern Python linter, single binary, fast)

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

## Naming Patterns

- Lowercase with underscores: `simulator.py`, `price_cache.py`, `market_data.py`
- Test files: `test_<module_name>.py` (e.g., `test_simulator.py`, `test_cache.py`)
- Private/internal files prefixed with underscore: `_generate_events` function in stream module
- Package modules use descriptive names matching their responsibility: `interface.py` for abstract base classes, `factory.py` for creation logic, `models.py` for data structures
- Lowercase with underscores: `normalize_ticker()`, `_poll_once()`, `get_tickers()`, `add_ticker()`
- Private methods prefixed with single underscore: `_add_ticker_internal()`, `_rebuild_cholesky()`, `_pairwise_correlation()`, `_poll_loop()`
- Async functions use `async def`: `async def start()`, `async def stop()`, `async def add_ticker()`
- Properties use `@property` decorator for computed attributes: `@property def direction()`, `@property def version`
- Verb-noun pattern for actions: `update()`, `get()`, `remove()`, `fetch()`, `step()`
- Lowercase with underscores for regular variables: `price_cache`, `previous_price`, `event_prob`, `update_interval`
- Private class attributes: `self._prices`, `self._lock`, `self._version`, `self._task`
- Constants: UPPERCASE with underscores: `DEFAULT_DT`, `TRADING_SECONDS_PER_YEAR`, `SEED_PRICES`
- Abbreviations acceptable: `dt` (delta time), `Z` (random normal), `S` (security price), `ts` (timestamp), `sim` (simulator)
- Type hints used throughout: `-> None`, `-> dict[str, float]`, `-> PriceUpdate | None`, `async def ... -> None`
- Union types use `|` syntax (Python 3.10+): `float | None` instead of `Optional[float]`
- Generic collections: `list[str]`, `dict[str, PriceUpdate]`
- Dataclass fields use type hints: `ticker: str`, `price: float`, `timestamp: float`
- PascalCase: `PriceUpdate`, `PriceCache`, `GBMSimulator`, `SimulatorDataSource`, `MassiveDataSource`, `MarketDataSource`
- Test classes: `Test<Component>` (e.g., `TestPriceUpdate`, `TestPriceCache`, `TestSimulatorDataSource`)
- Abstract base classes: `MarketDataSource` (inherits from `ABC`)

## Code Style

- Line length: 100 characters (enforced by ruff configuration)
- Indentation: 4 spaces (Python standard)
- Module docstrings: Triple-quoted at top of file, concise one-liner: `"""Data models for market data."""`
- Class docstrings: Immediately after class declaration, full description of responsibility and public interface
- Method docstrings: Immediately after method signature, explain what it does, parameters if not obvious, return type if useful
- Tool: `ruff` (installed as dev dependency)
- Configuration in `pyproject.toml`:
- Run with: `uv run --extra dev ruff check app/ tests/`
- No `.eslintrc` or `.prettierrc` — Python relies on ruff for both lint and format rules

## Import Organization

- No aliases defined; imports use relative paths within packages
- Relative imports within a module: `from .models import PriceUpdate` (same level), `from .interface import MarketDataSource` (same level)
- Absolute imports from app root: `from app.market.cache import PriceCache`
- Single imports per line: `from threading import Lock` (not `from threading import Lock, RLock`)
- Exception: Multiple imports from same module acceptable if logically grouped: `from fastapi import APIRouter, Request`
- Avoid `import *`
- Import submodules explicitly rather than importing the parent and accessing attributes

## Error Handling

- Specific exception catching: `except asyncio.CancelledError:` (for cancellation), `except (AttributeError, TypeError):` (for parsing errors)
- Broad exception handling in background loops: `except Exception as e:` at the top level of polling/streaming tasks, log and continue (don't re-raise)
- Example from `massive_client.py`:
- Validation errors: Return `None` or raise descriptive errors early; no silent failures
- Thread-safe error handling: Lock critical sections, use context managers
- Async task cancellation: Catch `asyncio.CancelledError` and handle cleanup gracefully:

## Logging

- Module-level logger: `logger = logging.getLogger(__name__)` at top of each file
- Log levels:
- Do not log at `logger.critical()` level (reserved for unrecoverable failures)
- Example from `massive_client.py`:

## Comments

- Docstrings for all public classes and functions (mandatory)
- Inline comments for non-obvious math, algorithm choices, or gotchas
- Example: GBM simulator includes mathematical formula comment:
- Example: Timestamp conversion in massive_client:
- Not applicable (Python project)
- Use docstring format (PEP 257) for type and parameter documentation

## Function Design

- `get_price()` in cache: 3 lines
- `remove()` in cache: 3 lines
- `normalize_ticker()` in interface: 2 lines
- Larger methods (e.g., `step()` in GBMSimulator) have clear sections with comments separating logic phases
- Type hints always included: `def update(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate:`
- Positional parameters for required args, keyword-only for optional
- Default values documented in docstring
- Factory functions pass cache/config as parameters, not singletons: `create_market_data_source(price_cache: PriceCache) -> MarketDataSource`
- Typed return values: `-> PriceUpdate`, `-> dict[str, float]`, `-> PriceUpdate | None`
- Return `None` rather than raising for "not found" cases: `def get(self, ticker: str) -> PriceUpdate | None:`
- Setter-style methods return `None`: `async def start(self, tickers: list[str]) -> None:`
- Computed properties return the value: `@property def direction(self) -> str:`

## Module Design

- No `__all__` definitions currently; all public classes/functions are importable
- Private internals prefixed with underscore
- Public API clearly marked by lack of underscore prefix
- `__init__.py` in `app/market/` exports public API:
- Allows: `from app.market import PriceCache, PriceUpdate, MarketDataSource`
- `app/market/` — all market data logic (cache, simulator, API client, streaming)
- Each module has a single responsibility:

## Dataclass Usage

- `PriceUpdate` is `@dataclass(frozen=True, slots=True)` — immutable, memory-efficient
- Computed properties derive values from immutable fields: `change`, `change_percent`, `direction`
- Serialization method: `to_dict()` for JSON conversion
- Mutable class state protected with `threading.Lock`:
- All reads/writes to `_prices` are guarded: `with self._lock: ...`

## Async/Await Patterns

- Created with `asyncio.create_task()` with optional name:
- Cleanup on stop: cancel, catch `CancelledError`, set to `None`
- Synchronous third-party APIs (e.g., Massive REST client) run in thread pool:
- Periodic tasks use `await asyncio.sleep(interval)` in a loop
- Zero delay in tests for responsiveness: `update_interval=0` or very small values

<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

## System Overview

```text

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

- **Pluggable data sources** — Two implementations (simulator, Massive) behind `MarketDataSource` interface; selected at startup via environment variable
- **Async/await throughout** — Leverages FastAPI's async model; data source lifecycle managed with `asyncio.Task`
- **Thread-safe shared state** — `PriceCache` uses `Lock` for concurrent reads/writes from SSE streaming and background update tasks
- **Factory pattern** — `create_market_data_source()` and `create_stream_router()` isolate object creation and configuration

## Layers

- **Purpose:** Stream live prices from either a simulator or real API; make prices available to all downstream systems
- **Location:** `backend/app/market/`
- **Contains:** Price models, abstract interface, two implementations (simulator + Massive), shared cache, SSE streaming logic
- **Depends on:** Nothing in the app; external: `massive` SDK, `numpy` (for GBM math)
- **Used by:** SSE endpoint, portfolio valuation, trade execution, frontend via HTTP
- **Purpose:** Manage positions, cash balance, trades, and portfolio snapshots (P&L history)
- **Location:** `backend/app/portfolio/`, `backend/app/watchlist/`
- **Contains:** Trade execution logic, position tracking, P&L calculations, watchlist CRUD
- **Depends on:** Market Data (price lookup), Database
- **Used by:** Chat/LLM (for trade execution), API endpoints
- **Purpose:** Accept user messages, call LLM for analysis and trade suggestions, auto-execute trades
- **Location:** `backend/app/llm/`
- **Contains:** LLM client (LiteLLM via OpenRouter), structured output parsing, trade/watchlist action execution
- **Depends on:** Portfolio (to read context and execute actions), Market Data (for live prices)
- **Used by:** `/api/chat` endpoint
- **Purpose:** Schema definitions, seed data, initialization logic
- **Location:** `backend/app/db/`
- **Contains:** SQLite schema SQL, seed scripts, database setup on first run
- **Depends on:** Nothing (pure schema/DDL)
- **Used by:** Portfolio layer

## Data Flow

### Primary Request Path: Price Updates

### Trade Execution Path

### Chat & Trade Auto-Execution

### State Management

- **Price state** — Owned by `PriceCache`; written by market data source; read by SSE, portfolio, chat
- **Portfolio state** — SQLite tables: `positions`, `trades`, `portfolio_snapshots`, `users_profile` (planned)
- **Chat state** — SQLite table: `chat_messages` (planned)
- **Watchlist state** — SQLite table: `watchlist` (planned)

## Key Abstractions

- **Purpose:** Pluggable contract for price sources (simulator or API)
- **Examples:** `SimulatorDataSource`, `MassiveDataSource`
- **Pattern:** Abstract base class (`app/market/interface.py`) with async lifecycle methods
- **Why it matters:** Allows swapping data source at startup with zero code changes; same interface for both
- **Purpose:** Immutable snapshot of a price with computed properties (direction, change, change_percent)
- **Pattern:** Frozen dataclass (`app/market/models.py`)
- **Benefit:** Thread-safe, JSON-serializable, rich with derived data
- **Purpose:** Generates correlated price movements using geometric Brownian motion with random events
- **Math:** `S(t+dt) = S(t) * exp((mu - 0.5*sigma^2)*dt + sigma*sqrt(dt)*Z)` where Z is correlated normal
- **Correlation:** Tech and finance groups move together; TSLA independent; ~0.1% chance per tick of 2-5% shock

## Entry Points

- **Location:** `backend/app/__init__.py` (currently minimal)
- **Triggers:** `uvicorn app:app --host 0.0.0.0 --port 8000` (via Dockerfile)
- **Responsibilities:** Wire up market data source, SSE router, portfolio endpoints (when implemented), chat endpoint, serve static frontend files
- **Location:** Backend application initialization (planned in main app creation)
- **Triggers:** App startup
- **Responsibilities:** Create cache, create and start data source with default watchlist tickers
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

### Empty Placeholder Modules

### Market Data Only, No API Routes Yet

## Error Handling

- **Massive API failures** (`app/market/massive_client.py:102`) — Log error, continue polling; no automatic fallback to simulator (failover must be designed during portfolio phase)
- **Market data source stop** — Idempotent; safe to call multiple times
- **SSE client disconnect** — Detected via `request.is_disconnected()`; loop exits cleanly
- **Price cache access** — No exceptions; missing tickers return `None`

## Cross-Cutting Concerns

- Module-level loggers: `logger = logging.getLogger(__name__)` in each file
- Info level for startup/shutdown, debug for per-tick activity (e.g., random events)
- Client IP tracked in SSE connections
- Ticker normalization via `normalize_ticker()` — uppercase, trimmed (`app/market/interface.py:8`)
- Applied consistently in both data sources and cache
- `PriceCache` uses `Lock` for all access
- Massive REST client calls offloaded to thread pool

<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

| Skill | Description | Path |
|-------|-------------|------|
| cerebras-inference | Use this to write code to call an LLM using LiteLLM and OpenRouter with the Cerebras inference provider | `.claude/skills/cerebras/SKILL.md` |
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
