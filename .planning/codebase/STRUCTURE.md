# Codebase Structure

**Analysis Date:** 2026-08-22

## Directory Layout

```
finally/
├── backend/                      # FastAPI Python backend (uv project)
│   ├── app/                      # Application package
│   │   ├── __init__.py           # Currently minimal
│   │   ├── market/               # Market data subsystem (COMPLETE)
│   │   │   ├── __init__.py       # Public API exports
│   │   │   ├── models.py         # PriceUpdate dataclass
│   │   │   ├── cache.py          # Thread-safe PriceCache
│   │   │   ├── interface.py      # MarketDataSource abstract interface
│   │   │   ├── factory.py        # Data source factory
│   │   │   ├── simulator.py      # GBM simulator + SimulatorDataSource
│   │   │   ├── massive_client.py # Massive API client
│   │   │   ├── seed_prices.py    # Seed data + correlation params
│   │   │   └── stream.py         # SSE streaming endpoint factory
│   │   ├── db/                   # Database layer (PLACEHOLDER)
│   │   │   └── __pycache__/
│   │   ├── llm/                  # LLM chat integration (PLACEHOLDER)
│   │   │   └── __pycache__/
│   │   ├── portfolio/            # Portfolio & trading (PLACEHOLDER)
│   │   │   └── __pycache__/
│   │   └── watchlist/            # Watchlist management (PLACEHOLDER)
│   │       └── __pycache__/
│   ├── tests/                    # Pytest unit tests
│   │   ├── __init__.py
│   │   ├── conftest.py           # pytest fixtures
│   │   ├── market/               # Market subsystem tests
│   │   │   ├── __init__.py
│   │   │   ├── test_cache.py
│   │   │   ├── test_models.py
│   │   │   ├── test_factory.py
│   │   │   ├── test_simulator.py
│   │   │   ├── test_simulator_source.py
│   │   │   ├── test_massive.py
│   │   │   └── test_stream.py
│   │   ├── db/                   # Database tests (future)
│   │   ├── llm/                  # LLM tests (future)
│   │   └── api/                  # API endpoint tests (future)
│   ├── pyproject.toml            # Python dependencies (uv)
│   ├── market_data_demo.py       # Standalone demo script
│   └── CLAUDE.md                 # Backend developer guide
├── frontend/                     # Next.js static export (EMPTY - future)
│   └── (no files yet)
├── planning/                     # Project documentation
│   ├── PLAN.md                   # Complete project specification
│   ├── MARKET_DATA_SUMMARY.md    # Market data completion summary
│   └── archive/                  # Previous phase docs
├── .planning/                    # GSD-generated codebase maps (this directory)
│   └── codebase/                 # Maps and analysis documents
│       ├── ARCHITECTURE.md       # (you are here)
│       └── STRUCTURE.md          # (this file)
├── test/                         # E2E tests with Playwright (EMPTY)
│   ├── node_modules/
│   └── playwright-report/
├── db/                           # SQLite volume mount (empty at repo time)
│   └── .gitkeep
├── scripts/                      # Start/stop helper scripts (EMPTY - future)
├── Dockerfile                    # Multi-stage build (planned)
├── docker-compose.yml            # Optional Docker Compose (planned)
├── .env                          # Environment variables (gitignored)
├── .env.example                  # Environment template (committed)
├── .gitignore                    # Git ignore rules
├── CLAUDE.md                     # Project instructions
├── README.md                     # Project overview
└── LICENSE                       # License file
```

## Directory Purposes

**`backend/`:**
- Purpose: Python/uv FastAPI application
- Contains: Market data subsystem (complete), placeholder directories for portfolio/llm/db/watchlist layers
- Entry point: `uvicorn app:app` (app object to be created; currently not defined)

**`backend/app/`:**
- Purpose: Main application package
- Contains: Subsystem modules organized by concern (market, db, llm, portfolio, watchlist)
- Public API: Defined by `__init__.py` (currently minimal; to be expanded)

**`backend/app/market/`:**
- Purpose: Market data subsystem — price simulation, real API client, SSE streaming
- Complete: Yes
- Contains: Abstract interface, two implementations, price cache, streaming endpoint
- Key pattern: Pluggable via factory; both implementations conform to `MarketDataSource` interface

**`backend/tests/market/`:**
- Purpose: Unit and integration tests for market subsystem
- Test count: 7 files covering models, cache, factory, simulator, Massive client, and streaming
- Pattern: One test class per component; async tests with `pytest.mark.asyncio`

**`frontend/`:**
- Purpose: Next.js static export (TypeScript + Tailwind)
- Status: Empty directory; to be created by frontend phases
- Expectation: Structure is up to frontend engineer; must produce static export via `npm run build`

**`planning/`:**
- Purpose: Project-wide documentation consumed by agents
- Key: `PLAN.md` is the master specification; updated as phases complete
- Subdirectories: `archive/` for retired docs from earlier phases

**`.planning/codebase/`:**
- Purpose: Machine-readable codebase maps for GSD orchestrator
- Generated by `/gsd-map-codebase` with focus areas: tech, arch, quality, concerns
- Updated after major phases complete

**`test/`:**
- Purpose: Playwright E2E tests (currently empty; will be added during testing phases)
- Expectation: `docker-compose.test.yml` spins up app + Playwright; runs scenarios like "buy shares", "chat with AI", etc.

**`db/`:**
- Purpose: Docker volume mount target for SQLite database
- Status: Contains only `.gitkeep` at repo time
- Runtime: `finally.db` created here by backend on first run

**`scripts/`:**
- Purpose: Platform-specific start/stop scripts
- Expected: `start_mac.sh`, `stop_mac.sh`, `start_windows.ps1`, `stop_windows.ps1`
- Currently: Empty; to be created during deployment phase

## Key File Locations

**Entry Points:**
- `backend/app/__init__.py` — Currently empty; will need to define FastAPI app object
- `backend/market_data_demo.py` — Standalone script: `uv run market_data_demo.py`
- `backend/pyproject.toml:34` — `[tool.hatch.build.targets.wheel]` defines entry point (future)

**Configuration:**
- `backend/pyproject.toml` — Python dependencies, pytest config, ruff linting rules, coverage settings
- `.env` (gitignored) — Runtime environment: `OPENROUTER_API_KEY`, `MASSIVE_API_KEY`, `LLM_MOCK`
- `.env.example` — Template for users (committed)

**Core Logic — Market Data (Complete):**
- `backend/app/market/interface.py:17` — `MarketDataSource` abstract class
- `backend/app/market/factory.py:16` — `create_market_data_source()` factory function
- `backend/app/market/simulator.py:200` — `SimulatorDataSource` implementation
- `backend/app/market/massive_client.py:17` — `MassiveDataSource` implementation
- `backend/app/market/cache.py:11` — `PriceCache` thread-safe store
- `backend/app/market/models.py:9` — `PriceUpdate` dataclass

**Streaming:**
- `backend/app/market/stream.py:17` — `create_stream_router()` SSE endpoint factory

**Testing:**
- `backend/tests/conftest.py` — Pytest fixtures (to be expanded)
- `backend/tests/market/test_simulator_source.py` — Integration tests for SimulatorDataSource
- `backend/tests/market/test_cache.py` — Unit tests for PriceCache

**Documentation:**
- `planning/PLAN.md` — Complete specification (25K, authoritative)
- `planning/MARKET_DATA_SUMMARY.md` — Market subsystem completion summary
- `backend/CLAUDE.md` — Backend developer guide (usage, API, running tests/demo)
- `CLAUDE.md` — Top-level project instructions
- `README.md` — Public overview

## Naming Conventions

**Files:**
- Python modules: `lowercase_with_underscores.py` (e.g., `market_data_demo.py`, `simulator.py`)
- Test files: `test_<component>.py` (e.g., `test_cache.py`, `test_simulator.py`)
- Config files: `.env`, `pyproject.toml`, `.gitignore`

**Directories:**
- Application packages: `lowercase` single-word or `lowercase_with_underscores` (e.g., `app/`, `app/market/`, `backend/`)
- Test directories: Mirror app structure under `tests/` (e.g., `tests/market/` mirrors `app/market/`)

**Python Naming:**
- Classes: `PascalCase` (e.g., `PriceCache`, `MarketDataSource`, `SimulatorDataSource`)
- Functions: `lowercase_with_underscores` (e.g., `create_market_data_source`, `normalize_ticker`)
- Methods: `lowercase_with_underscores` (e.g., `update()`, `get_tickers()`)
- Constants: `UPPERCASE` (e.g., `DEFAULT_DT`, `TRADING_SECONDS_PER_YEAR`)
- Private methods/attrs: Leading underscore (e.g., `_poll_once()`, `_tickers`)

**Dataclass/Type Naming:**
- Immutable models: Suffixed `Update` or `Snapshot` (e.g., `PriceUpdate`)
- Source implementations: Suffixed `DataSource` (e.g., `SimulatorDataSource`, `MassiveDataSource`)

## Where to Add New Code

**New Feature (e.g., "Add position averaging cost calculation"):**
- Primary code: `backend/app/portfolio/` (to be created by portfolio phase)
- Tests: `backend/tests/portfolio/` (mirror structure)
- Example: `backend/app/portfolio/positions.py` for position logic; `backend/tests/portfolio/test_positions.py` for tests

**New Component/Module (e.g., "Add risk analyzer"):**
- Implementation: Create new directory in `backend/app/` (e.g., `app/risk_analysis/`)
- Public API: Export from `app/risk_analysis/__init__.py`
- Tests: `backend/tests/risk_analysis/`
- Example structure:
  ```
  backend/app/risk_analysis/
  ├── __init__.py
  ├── analyzer.py
  ├── models.py
  └── calculations.py
  
  backend/tests/risk_analysis/
  ├── __init__.py
  ├── test_analyzer.py
  └── test_calculations.py
  ```

**Utilities (e.g., "Add date/time formatting helper"):**
- Shared helpers: `backend/app/utils/` or similar (create if not exists)
- Example: `backend/app/utils/time.py` for time utilities
- Tests: `backend/tests/utils/test_time.py`

**API Endpoints:**
- When FastAPI app is created in `backend/app/__init__.py` or `backend/app/main.py`, import routers from subsystem modules
- Example pattern (not yet implemented):
  ```python
  # backend/app/__init__.py
  from fastapi import FastAPI
  from app.market import create_stream_router
  from app.portfolio import create_portfolio_router
  from app.llm import create_chat_router
  
  app = FastAPI()
  app.include_router(create_stream_router(price_cache))
  app.include_router(create_portfolio_router(db))
  app.include_router(create_chat_router(llm_client, portfolio))
  ```

**Database Schema/Migrations:**
- Location: `backend/app/db/`
- Schema SQL: `backend/app/db/schema.sql` (or one file per table)
- Seed data: `backend/app/db/seed.sql`
- Initialization: `backend/app/db/init.py` (lazy init on first request)

**Frontend Code:**
- Location: `frontend/` (structure up to frontend engineer)
- Must produce static export to `frontend/out/` via `npm run build` with `output: 'export'` in `next.config.js`
- Static files served by FastAPI at `/` with fallback to `index.html` for SPA routing

## Special Directories

**`backend/.venv/`:**
- Purpose: Python virtual environment (created by `uv sync`)
- Generated: Yes
- Committed: No (in `.gitignore`)
- Action: Never commit; created fresh per machine

**`backend/.pytest_cache/`:**
- Purpose: Pytest caching
- Generated: Yes
- Committed: No (in `.gitignore`)
- Action: Safe to delete; regenerated on next test run

**`backend/.ruff_cache/`:**
- Purpose: Ruff linter caching
- Generated: Yes
- Committed: No (in `.gitignore`)
- Action: Safe to delete; regenerated on next lint run

**`test/node_modules/`:**
- Purpose: Playwright dependencies
- Generated: Yes (via `npm install` in `test/`)
- Committed: No (in `.gitignore`)
- Action: Recreate with `npm install` if missing

**`db/`:**
- Purpose: Docker volume mount for SQLite
- Generated: Yes (at runtime, by backend on first request)
- Committed: `.gitkeep` only; actual `finally.db` gitignored
- Action: Never committed; data persists across container restarts via volume

**`.planning/codebase/`:**
- Purpose: GSD-generated codebase analysis documents
- Generated: Yes (by `/gsd-map-codebase`)
- Committed: Yes (so agents can reference during execution)
- Action: Regenerate when codebase structure changes significantly

---

*Structure analysis: 2026-08-22*
