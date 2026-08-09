# Market Interface Design

Design of FinAlly's unified Python interface for retrieving stock prices — a single API that
uses the Massive API when `MASSIVE_API_KEY` is set, and falls back to an in-process simulator
otherwise. Implemented in `backend/app/market/`. See `MASSIVE_API.md` for the Massive research
this design is built on, and `MARKET_SIMULATOR.md` for the simulator's own internals.

## Why a Unified Interface

Every other part of the backend — SSE streaming, portfolio valuation, trade execution — needs
"the current price of ticker X" and nothing else about where it came from. Coupling that code to
either Massive's REST client or a simulator's internal state would mean two code paths
everywhere prices are read. Instead:

- One abstract contract (`MarketDataSource`) that both a simulator and a Massive poller implement
- One shared, thread-safe cache (`PriceCache`) that all downstream code reads from
- One factory function that picks the implementation based on environment, so nothing else in
  the codebase branches on "are we using Massive or the simulator?"

```
                    MarketDataSource (ABC)
                   /                      \
       SimulatorDataSource          MassiveDataSource
       (GBM, in-process)            (REST poll, Polygon/Massive)
                   \                      /
                    v                    v
                       PriceCache
                    (thread-safe, in-memory)
                    /        |         \
                   v         v          v
          SSE stream   Portfolio    Trade execution
          endpoint     valuation
```

## Core Types

### `PriceUpdate` (`models.py`)

An immutable snapshot of one ticker's price at a point in time. Frozen dataclass, not a mutable
object being updated in place — every price change produces a new instance.

```python
@dataclass(frozen=True, slots=True)
class PriceUpdate:
    ticker: str
    price: float
    previous_price: float
    timestamp: float = field(default_factory=time.time)  # Unix seconds

    @property
    def change(self) -> float: ...          # price - previous_price, rounded
    @property
    def change_percent(self) -> float: ...  # % change, 0.0 if previous_price is 0
    @property
    def direction(self) -> str: ...          # "up" / "down" / "flat"

    def to_dict(self) -> dict: ...           # JSON-serializable, used directly for SSE payloads
```

Computing `change`/`change_percent`/`direction` as properties (rather than storing them) means
there's exactly one place that defines what "up" means, and no risk of a writer forgetting to
set them.

### `MarketDataSource` (`interface.py`)

The abstract base class both implementations satisfy:

```python
class MarketDataSource(ABC):
    async def start(self, tickers: list[str]) -> None: ...
    async def stop(self) -> None: ...
    async def add_ticker(self, ticker: str) -> None: ...
    async def remove_ticker(self, ticker: str) -> None: ...
    def get_tickers(self) -> list[str]: ...
```

Lifecycle contract: `start()` is called exactly once at app startup with the initial active
ticker set; `add_ticker`/`remove_ticker` handle watchlist and position changes while running;
`stop()` is called once at shutdown and must be safe to call more than once (idempotent).
Neither method returns prices — implementations push into the shared `PriceCache` on their own
schedule, and callers read from the cache, never from the source directly.

### `PriceCache` (`cache.py`)

Thread-safe (`threading.Lock`) in-memory store, keyed by ticker. One writer at a time (whichever
`MarketDataSource` is active), multiple readers (SSE endpoint, portfolio math, trade execution).

```python
class PriceCache:
    def update(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate: ...
    def get(self, ticker: str) -> PriceUpdate | None: ...
    def get_all(self) -> dict[str, PriceUpdate]: ...
    def get_price(self, ticker: str) -> float | None: ...
    def remove(self, ticker: str) -> None: ...

    @property
    def version(self) -> int: ...  # increments on every update() call
```

`update()` looks up the ticker's existing entry to compute `previous_price` — callers only ever
supply the new price, never the delta. The first update for a ticker sets `previous_price ==
price` (direction reports "flat" rather than a misleading up/down on the very first tick).

The `version` counter exists purely so the SSE endpoint can detect "has anything changed since I
last checked" without diffing the whole price dict — see `stream.py`, which polls
`price_cache.version` every 500ms and only serializes + sends when it has moved.

### `create_market_data_source()` (`factory.py`)

```python
def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if api_key:
        return MassiveDataSource(api_key=api_key, price_cache=price_cache)
    return SimulatorDataSource(price_cache=price_cache)
```

This is the entire selection logic PLAN.md §5 describes: non-empty `MASSIVE_API_KEY` → Massive,
otherwise → simulator. The factory returns an *unstarted* source; the caller is responsible for
`await source.start(tickers)`. Nothing else in the codebase reads `MASSIVE_API_KEY` directly.

## The Two Implementations

### `SimulatorDataSource` (`simulator.py`)

Runs an `asyncio.Task` loop that calls `GBMSimulator.step()` every 500ms and writes every
resulting price into the cache. No network calls, no external dependency, always available. Full
design in `MARKET_SIMULATOR.md`.

### `MassiveDataSource` (`massive_client.py`)

Runs an `asyncio.Task` loop that calls the Massive REST client's `get_snapshot_all()` on an
interval (15s default — sized for the free tier's 5-calls/minute limit; see `MASSIVE_API.md` for
why paid tiers can safely poll faster). The synchronous `massive` client call is wrapped in
`asyncio.to_thread()` so it doesn't block the event loop.

```python
async def _poll_once(self) -> None:
    try:
        snapshots = await asyncio.to_thread(self._fetch_snapshots)
        for snap in snapshots:
            self._cache.update(
                ticker=snap.ticker,
                price=snap.last_trade.price,
                timestamp=snap.last_trade.timestamp / 1000.0,  # ms -> s
            )
    except Exception as e:
        logger.error("Massive poll failed: %s", e)
        # no re-raise; the loop retries on the next interval
```

**Permanent failover** (PLAN.md §5/§6): a poll failure — auth error, rate limit, network error,
service error, at startup or mid-run — is logged and the loop simply continues to the next
interval on its own. The *permanent* switch to the simulator (stopping the Massive task,
transferring its tracked tickers to a freshly started `SimulatorDataSource`) is orchestrated one
level up, in the app's startup/lifespan code that owns the active `MarketDataSource` reference —
not inside `MassiveDataSource` itself, which only knows how to poll and log. This keeps the
failover policy in one place rather than duplicated inside both source implementations.

## Shared Price Cache and the Active Ticker Set

Per PLAN.md §6, the set of tickers actively tracked (and thus present in the cache and streamed
over SSE) is the **union of the watchlist and any tickers with open positions** — defined
identically regardless of which `MarketDataSource` is active. Removing a ticker from the
watchlist calls `remove_ticker()`, but the source only actually drops it from the cache when no
open position still references it; the API layer (not `MarketDataSource`) is what checks
positions before deciding whether a `remove_ticker()` call is safe to issue, since the source
itself has no knowledge of the portfolio.

This is why `PriceCache` is a separate object from either source: a future multi-user version
could keep one cache per user session while still sharing a single upstream poller, without
changing this interface.

## SSE Streaming (`stream.py`)

`create_stream_router(price_cache)` returns a FastAPI `APIRouter` exposing
`GET /api/stream/prices`. The generator polls `price_cache.version` every 500ms; when it has
changed since the last send, it serializes `price_cache.get_all()` (every tracked ticker, not
just the one that changed — simplest correct behavior, and the payload is small) and yields one
SSE `data:` frame. A `retry: 1000` directive is sent once at connection open so `EventSource`'s
built-in reconnect logic retries after 1s on drop. The loop exits when
`request.is_disconnected()` reports true, so a stale generator doesn't keep running against a
closed connection.

## Usage for Downstream Code

```python
from app.market import PriceCache, create_market_data_source

# Startup
cache = PriceCache()
source = create_market_data_source(cache)  # reads MASSIVE_API_KEY
await source.start(["AAPL", "GOOGL", "MSFT", ...])

# Reading prices — identical regardless of which source is active
update = cache.get("AAPL")          # PriceUpdate | None
price = cache.get_price("AAPL")     # float | None
all_prices = cache.get_all()        # dict[str, PriceUpdate]

# Watchlist / position changes
await source.add_ticker("TSLA")
await source.remove_ticker("GOOGL")

# Shutdown
await source.stop()
```
