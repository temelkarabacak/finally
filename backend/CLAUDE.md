# Backend — Developer Guide

## Project Setup

```bash
cd backend
uv sync --extra dev   # Install all dependencies including test/lint tools
```

## Market Data API

The market data subsystem lives in `app/market/`. Use these imports:

```python
from app.market import PriceCache, PriceUpdate, MarketDataSource, create_market_data_source
```

### Core Types

- **`PriceUpdate`** — Immutable dataclass: `ticker`, `price`, `previous_price`, `timestamp`, plus properties `change`, `change_percent`, `direction` ("up"/"down"/"flat"), and `to_dict()` for JSON serialization.

- **`PriceCache`** — Thread-safe in-memory store. Key methods:
  - `update(ticker, price, timestamp=None) -> PriceUpdate`
  - `get(ticker) -> PriceUpdate | None`
  - `get_price(ticker) -> float | None`
  - `get_all() -> dict[str, PriceUpdate]`
  - `remove(ticker)`
  - `version` property — monotonic counter, increments on every update (for SSE change detection)

- **`MarketDataSource`** — Abstract interface implemented by `SimulatorDataSource` and `MassiveDataSource`. Lifecycle: `start(tickers)` -> `add_ticker()` / `remove_ticker()` -> `stop()`.

- **`create_market_data_source(cache)`** — Factory. Returns `MassiveDataSource` if `MASSIVE_API_KEY` is set, otherwise `SimulatorDataSource`.

### SSE Streaming

```python
from app.market import create_stream_router

router = create_stream_router(price_cache)  # Returns FastAPI APIRouter
# Endpoint: GET /api/stream/prices (text/event-stream)
```

### Seed Data

Default tickers: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX. Seed prices and per-ticker volatility/drift params are in `app/market/seed_prices.py`.

## Database API

The persistence layer lives in `app/db/` (Python) with the SQL source of truth in `backend/db/`
(`schema.sql`, `seed.sql`). Plain `sqlite3`, no ORM.

```python
from app.db import get_db, get_connection, list_positions, insert_trade  # etc.
```

### Connection and lazy init

- **`get_db()`** — FastAPI dependency yielding a per-request `sqlite3.Connection`
  (`row_factory=sqlite3.Row`). The request is one transaction: it commits when the handler
  returns and rolls back if it raises, so a trade touching cash, position and trade log is atomic.
  Query helpers never commit themselves.
  ```python
  @router.get("/api/portfolio")
  def portfolio(conn: sqlite3.Connection = Depends(get_db)): ...
  ```
- **`get_connection(path=None)`** — Opens a connection directly (background tasks, scripts).
  Caller must `commit()` and `close()`.
- Opening a connection creates any missing tables and seeds defaults if `users_profile` is empty.
  No migration step.
- **`database_path()`** — Defaults to `<project root>/db/finally.db` (the Docker volume mount
  target); override with the `FINALLY_DB_PATH` env var. Tests use a `tmp_path` file.

### Row types

Frozen dataclasses: `WatchlistEntry`, `Position`, `Trade`, `PortfolioSnapshot`, `ChatMessage`.
`ChatMessage.actions` is parsed from/serialised to JSON automatically.

### Query helpers

Every helper takes `conn` first and `user_id: str = DEFAULT_USER_ID` last. Tickers are
normalised to uppercase.

```python
get_cash_balance(conn, user_id=...) -> float                      # raises ValueError if no profile
update_cash_balance(conn, cash_balance, user_id=...) -> None      # absolute value, not a delta

list_watchlist(conn, user_id=...) -> list[WatchlistEntry]
add_watchlist_ticker(conn, ticker, user_id=...) -> bool           # False if already present
remove_watchlist_ticker(conn, ticker, user_id=...) -> bool        # False if not present

get_position(conn, ticker, user_id=...) -> Position | None
list_positions(conn, user_id=...) -> list[Position]               # sorted by ticker
upsert_position(conn, ticker, quantity, avg_cost, user_id=...) -> Position
delete_position(conn, ticker, user_id=...) -> bool                # use when fully sold

insert_trade(conn, ticker, side, quantity, price, user_id=...) -> Trade   # side: "buy" | "sell"
list_trades(conn, user_id=..., limit=None) -> list[Trade]         # newest first

insert_snapshot(conn, total_value, user_id=...) -> PortfolioSnapshot
list_snapshots(conn, user_id=..., limit=None) -> list[PortfolioSnapshot]  # oldest first

insert_chat_message(conn, role, content, actions=None, user_id=...) -> ChatMessage
list_recent_chat_messages(conn, limit=20, user_id=...) -> list[ChatMessage]  # oldest first
```

`side` and `role` are CHECK-constrained in the schema; invalid values raise
`sqlite3.IntegrityError`. Quantities are `REAL`, so fractional shares work.

## Application and REST API

`app/main.py` assembles the app. `create_app(price_cache=None)` builds it; the module-level
`app` is what uvicorn serves. The lifespan creates the market data source, starts it on the
active ticker set, and runs a 30s portfolio snapshot task. Routers are mounted in order and
the `static/` mount (the Next.js export, added by the Docker build) goes last because a `/`
mount shadows every route registered after it.

| Method | Path | Notes |
|---|---|---|
| GET | `/api/health` | `{"status": "ok"}` |
| GET | `/api/stream/prices` | SSE (from `app/market`) |
| GET | `/api/portfolio` | cash, positions marked to market, totals |
| POST | `/api/portfolio/trade` | `{ticker, quantity, side}` -> `{trade, portfolio}`; 400 on rejection |
| GET | `/api/portfolio/history` | snapshots, oldest first |
| GET/POST | `/api/watchlist` | POST `{ticker}` -> 201, 409 if already present |
| DELETE | `/api/watchlist/{ticker}` | 404 if not watched |

All mutating handlers call `conn.commit()` before returning. `get_db` also commits, but
FastAPI runs yield-dependency exit code *after* the response is sent, so a client refetching
immediately would otherwise read pre-write state.

### Reusable pieces

```python
from app.dependencies import get_market_source, get_price_cache  # app.state accessors
from app.portfolio import (
    TradeError,           # raised on a rejected trade; map to HTTP 400
    active_tickers,       # watchlist union open positions (PLAN.md section 6)
    build_portfolio,      # dict for GET /api/portfolio, also the LLM's portfolio context
    execute_trade,        # (conn, cache, ticker, side, quantity) -> Trade; snapshots too
    prune_ticker,         # await after a trade/removal: stops pricing an unheld, unwatched ticker
    total_portfolio_value,
)
```

`execute_trade` validates and never clamps: non-positive quantity, an unpriced ticker,
insufficient cash or insufficient shares all raise `TradeError` and leave the transaction
untouched. Chat-driven trades go through it too, so they get identical validation.

## Chat API

`app/llm/` owns the assistant. LiteLLM -> OpenRouter -> Cerebras
(`openrouter/openai/gpt-oss-120b`) with structured outputs and a 30s timeout.

| Method | Path | Notes |
|---|---|---|
| POST | `/api/chat` | `{message}` -> `{message, trades, watchlist_changes}`, always 200 |
| GET | `/api/chat/history` | last 20 messages, oldest first, for rehydrating the panel |

Each entry in `trades` is `{ticker, side, quantity, price?, status, error}` and each entry in
`watchlist_changes` is `{ticker, action, status, error}`, where `status` is `"executed"` or
`"rejected"`. A rejected action never aborts the turn: its reason is appended to `message`
after a `Not completed:` line and stored in `chat_messages.actions`.

Flow: portfolio context and history are read, the user message is persisted **and committed**
before the model call (so it survives a disconnect during the wait), then trades run through
`app.portfolio.execute_trade` and watchlist edits through `apply_watchlist_change`, which also
keeps the market data source in step. The assistant message is persisted only on success — a
timeout or LLM error returns `RETRY_MESSAGE` and writes nothing further.

### LLM_MOCK

`LLM_MOCK=true` (or `1`/`yes`) replaces the model with `app/llm/mock.py`: no network, no key,
fully deterministic. Rules match independently against the user's message; **tickers must be
UPPERCASE**.

| Input | Result |
|---|---|
| `buy 10 AAPL`, `sell 2.5 shares of TSLA` | one trade per match, decimals allowed |
| `add PYPL to the watchlist`, `remove NFLX from watchlist` | one watchlist change per match |
| contains `portfolio`, `position`, `p&l` or `pnl` | text summary of cash, total value and positions; no actions |
| anything else | fixed greeting (`app.llm.mock.GREETING`); no actions |

Trade and watchlist rules can fire in one message (`buy 3 AAPL and add PYPL to the watchlist`).
When either fires, the reply is `Understood. Executing: ...` and the summary rule is skipped.

## Running Tests

```bash
uv run --extra dev pytest -v              # All tests
uv run --extra dev pytest --cov=app       # With coverage
uv run --extra dev ruff check app/ tests/ # Lint
```

## Demo

```bash
uv run market_data_demo.py   # Live terminal dashboard with simulated prices
```
