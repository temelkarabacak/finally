# Technology Stack

**Analysis Date:** 2026-08-22

## Languages

**Primary:**
- Python 3.12+ - Backend API, market data simulation, database logic

**Secondary:**
- TypeScript/JavaScript - Frontend (Next.js project in `frontend/`, currently not implemented)

## Runtime

**Environment:**
- Python 3.12+ (defined in `backend/pyproject.toml`)

**Package Manager:**
- uv (modern Python project manager; replaces pip)
- Lockfile: `backend/uv.lock` (present)

## Frameworks

**Core:**
- FastAPI 0.115.0+ - API framework for HTTP endpoints and SSE streaming (`backend/app/`)
- Uvicorn 0.32.0+ - ASGI server for running FastAPI application

**Testing:**
- pytest 8.3.0+ - Test runner
- pytest-asyncio 0.24.0+ - Async test support (FastAPI and async market data source)
- pytest-cov 5.0.0+ - Code coverage measurement
- Configuration: `backend/pyproject.toml` (lines 30-36)

**Build/Dev:**
- ruff 0.7.0+ - Linting (line length 100, Python 3.12 target) — see `backend/pyproject.toml` (lines 38-43)
- hatchling - Build backend for wheel packaging

## Key Dependencies

**Critical:**
- `numpy 2.0.0+` - Geometric Brownian Motion (GBM) calculations in market simulator; used for correlated random number generation
- `massive 1.0.0+` - Polygon.io REST API client for real-time market data; provides `RESTClient` and `SnapshotMarketType` models (see `backend/app/market/massive_client.py`, line 8-9)
- `rich 13.0.0+` - Rich text and formatting for TUI; used in market data demo dashboard (`backend/market_data_demo.py`, line 15-20); Console, Layout, Live, Panel, Table components

**Infrastructure:**
- None currently (SQLite database planned but not yet integrated; LiteLLM for LLM planned but not yet integrated)

## Configuration

**Environment:**
Environment variables control behavior (defined in project PLAN.md):
- `OPENROUTER_API_KEY` - LLM integration (not yet implemented)
- `MASSIVE_API_KEY` - Switches market data source to Polygon.io; if absent or empty, uses built-in simulator (see `backend/app/market/factory.py`)
- `LLM_MOCK` - Set to "true" for deterministic mock responses in tests (not yet implemented)

**Build:**
- `backend/pyproject.toml` - Python project metadata and dependencies
- `backend/uv.lock` - Dependency lockfile for reproducible builds
- Wheel package configuration: `backend/pyproject.toml` (lines 27-28) — packages the `app` module

## Platform Requirements

**Development:**
- Python 3.12+
- uv package manager
- `pytest` and development dependencies installed via `uv sync --extra dev`

**Production:**
- Single Docker container (planned; not yet implemented)
- Port 8000 (specified in PLAN.md)
- SQLite database volume mount at `/app/db/` (planned)

## Versioning Notes

- **Python**: 3.12 minimum (ensures compatibility with latest async/await patterns and type hints)
- **FastAPI**: 0.115.0+ (ensures support for modern async patterns, structured outputs, and SSE)
- **Uvicorn**: 0.32.0+ with standard extras (includes libuv for async I/O)
- **NumPy**: 2.0.0+ (major version for modern array operations)
- **Ruff**: 0.7.0+ (modern Python linter, single binary, fast)

---

*Stack analysis: 2026-08-22*
