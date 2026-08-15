# Massive API Reference (formerly Polygon.io)

Research reference for the Massive REST API as used in FinAlly to fetch live and end-of-day
prices for multiple tickers. Sourced from the official `massive` Python client (v1.x,
`/massive-com/client-python`) and the Massive docs site, via context7, 2026-08-09.

## Overview

- **Company**: Massive (rebrand of Polygon.io — the API, package, and endpoints all carry the
  new name; `api.polygon.io` still works as a legacy alias)
- **Base URL**: `https://api.massive.com`
- **Python package**: `massive` (install via `uv add massive`)
- **Auth**: API key, either passed to `RESTClient(api_key=...)` or read automatically from the
  `MASSIVE_API_KEY` environment variable
- **Response shape**: the client parses JSON into typed dataclasses (`@modelclass`) by default;
  pass `raw=True` to any call to get the underlying `urllib3.HTTPResponse` instead

## Client Initialization

```python
from massive import RESTClient

client = RESTClient()             # reads MASSIVE_API_KEY from the environment
client = RESTClient("api_key")    # or pass the key explicitly

# Debugging: log request/response headers
client = RESTClient(trace=True, verbose=True)
```

## Plans and Rate Limits — read this before designing a polling loop

This is the detail that most shapes FinAlly's design: **the free plan does not return live
intraday prices.**

| Plan | Price | API calls | Data timeliness | WebSocket |
|---|---|---|---|---|
| Stocks Basic | $0/mo | 5 calls/minute | **End-of-day only** (previous session's close) | No |
| Stocks Starter | $29/mo | Unlimited | 15-minute delayed | Minute aggregates, snapshot |
| Stocks Developer | $79/mo | Unlimited | 15-minute delayed | + second aggregates, trades, quotes |
| Stocks Advanced | $199/mo | Unlimited | **Real-time** | Full real-time trades/quotes/aggregates |

Implication for FinAlly: with no key or a free-tier key, `last_trade.price` from the snapshot
endpoint reflects the *last close*, not a moving intraday price — polling it every 15 seconds
during market hours will return the same number until the next session. A "live" experience
against Massive requires at least the Starter plan (15-minute-delayed, still not tick-by-tick)
or Advanced (true real-time). This is exactly why the project defaults to the built-in simulator
(see `MARKET_SIMULATOR.md`) and treats Massive as an optional, better-if-you-pay-for-it data
source — see `MARKET_INTERFACE.md` for the selection logic.

Poll cadence used in FinAlly, independent of data freshness:
- Free tier: poll every 15s (5 calls/min budget, one call covers all tickers)
- Paid tiers: poll every 2–5s is reasonable since calls are unlimited

## Endpoints Used in FinAlly

### 1. Full Market Snapshot, filtered to specific tickers (primary endpoint)

Gets current data for multiple tickers in **one API call** — this is what makes it viable to
poll a whole watchlist within the free tier's 5-calls/minute budget.

**REST**: `GET /v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,GOOGL,MSFT&apiKey=...`

The `tickers` query parameter is an optional, case-sensitive, comma-separated list. Omitting it
returns a snapshot for *every* US ticker (large payload — always pass the list explicitly).

**Python client**:
```python
from massive import RESTClient
from massive.rest.models import SnapshotMarketType

client = RESTClient()

snapshots = client.get_snapshot_all(
    market_type=SnapshotMarketType.STOCKS,
    tickers=["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"],
)

for snap in snapshots:
    print(f"{snap.ticker}: ${snap.last_trade.price}")
    print(f"  Today's change: {snap.todays_change_percent:.2f}%")
    print(f"  Day OHLC: O={snap.day.open} H={snap.day.high} L={snap.day.low} C={snap.day.close}")
    print(f"  Prev close: {snap.prev_day.close}")
```

**Response model** — `TickerSnapshot` (from `massive.rest.models.snapshot`):

```python
@modelclass
class TickerSnapshot:
    day: Optional[Agg] = None                    # today's OHLCV bar (o/h/l/c/v/vw)
    last_quote: Optional[LastQuote] = None        # bid/ask
    last_trade: Optional[LastTrade] = None        # price, size, exchange, timestamp
    min: Optional[MinuteSnapshot] = None          # most recent minute bar
    prev_day: Optional[Agg] = None                # previous session's OHLCV bar
    ticker: Optional[str] = None
    todays_change: Optional[float] = None         # absolute change vs prev close
    todays_change_percent: Optional[float] = None # percent change vs prev close
    updated: Optional[int] = None                 # nanosecond epoch timestamp
    fair_market_value: Optional[float] = None      # Business-plan only
```

Note: the day-change fields live at the top level (`snap.todays_change_percent`), not nested
under `day` — a common mistake when reading the raw JSON, where the equivalent keys are
`todaysChange` / `todaysChangePerc` at the top of each ticker object.

**Raw JSON response** (per ticker, camelCase over the wire):
```json
{
  "ticker": "AAPL",
  "day": { "o": 190.12, "h": 191.40, "l": 189.80, "c": 190.55, "v": 42113400, "vw": 190.61 },
  "lastTrade": { "p": 190.55, "s": 100, "x": 4, "t": 1754770799000000000, "i": "71675577320245", "c": [14, 41] },
  "lastQuote": { "P": 190.56, "S": 200, "p": 190.54, "s": 150, "t": 1754770799994246100 },
  "min": { "o": 190.50, "h": 190.60, "l": 190.48, "c": 190.55, "v": 5000, "vw": 190.53, "t": 1754770740000 },
  "prevDay": { "o": 188.90, "h": 190.10, "l": 188.50, "c": 189.61, "v": 51200300, "vw": 189.42 },
  "todaysChange": 0.94,
  "todaysChangePerc": 0.496,
  "updated": 1754770799994246100
}
```

**Key fields FinAlly extracts**:
- `last_trade.price` — the price written to the shared price cache
- `last_trade.timestamp` — Unix **nanoseconds** in the raw wire format; the Python client's
  `LastTrade.timestamp` returns Unix **milliseconds** (client-side conversion) — divide by
  1000 to get seconds, as the current `massive_client.py` does
- `todays_change_percent` — usable directly for a "day change %" display if not computing it
  client-side from `previous_price` in the cache

### 2. Single Ticker Snapshot

Same `TickerSnapshot` shape, for one symbol — useful for a detail view if a ticker isn't already
in the polled set.

```python
snapshot = client.get_snapshot_ticker(
    market_type=SnapshotMarketType.STOCKS,
    ticker="AAPL",
)
print(f"Price: ${snapshot.last_trade.price}")
print(f"Bid/Ask: ${snapshot.last_quote.bid_price} / ${snapshot.last_quote.ask_price}")
```

**REST**: `GET /v2/snapshot/locale/us/markets/stocks/tickers/AAPL?apiKey=...`

### 3. Aggregates (Bars) — for seed prices and historical charts

Not used in the live poll loop, but relevant for seeding realistic starting prices or adding a
historical chart later.

```python
# Non-paginated convenience method
aggs = client.get_aggs("AAPL", 1, "day", "2024-01-01", "2024-01-31")

# Paginated iterator (auto-follows next_url), for large ranges
for a in client.list_aggs(
    ticker="AAPL",
    multiplier=1,
    timespan="day",
    from_="2024-01-01",
    to="2024-01-31",
    limit=50000,
):
    print(f"{a.timestamp}: O={a.open} H={a.high} L={a.low} C={a.close} V={a.volume}")
```

**REST**: `GET /v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}`

### 4. Last Trade / Last Quote

Individual single-value lookups; superseded by the snapshot endpoint for FinAlly's polling loop
since one snapshot call already returns both per ticker, but useful for spot checks.

```python
trade = client.get_last_trade(ticker="AAPL")
print(f"Last trade: ${trade.price} x {trade.size}")

quote = client.get_last_quote(ticker="AAPL")
print(f"Bid: ${quote.bid_price} x {quote.bid_size}  Ask: ${quote.ask_price} x {quote.ask_size}")
```

## WebSocket (not used, noted for completeness)

Massive offers real-time push via WebSocket (`wss://socket.massive.com/stocks`, or
`wss://delayed.massive.com/stocks` on plans below Advanced). Subscribing is a two-step
JSON handshake:

```json
{"action": "auth", "params": "YOUR_API_KEY"}
{"action": "subscribe", "params": "T.AAPL,T.MSFT"}
```

FinAlly does not use this: PLAN.md commits to REST polling for the Massive integration, matching
the simplicity of the simulator's own poll-and-push loop and avoiding a second connection
protocol on the backend. It stays a documented option if a future iteration needs tick-level data.

## Error Handling

The client raises exceptions on HTTP errors; `RESTClient` retries transient failures internally
(3 retries by default). FinAlly's `MassiveDataSource._poll_once()` wraps each poll in a broad
`try/except` and logs rather than raising, since a single failed poll should not crash the
background task — see `MARKET_INTERFACE.md` for the permanent-failover behavior on repeated
failures.

| Status | Meaning | FinAlly's handling |
|---|---|---|
| 401 | Invalid API key | Logged, triggers permanent failover to simulator |
| 403 | Endpoint not included in plan | Logged, triggers permanent failover to simulator |
| 429 | Rate limit exceeded | Logged, triggers permanent failover to simulator |
| 5xx | Massive service error | Logged, triggers permanent failover to simulator |
| Network error | Timeout, DNS, connection refused | Logged, triggers permanent failover to simulator |

Per PLAN.md §5/§6, *any* of these failure classes — at startup or during later polling —
permanently switches the app to the simulator for the remainder of the run; it never attempts to
reconnect to Massive.

## Notes

- The snapshot-all endpoint returning **all requested tickers in one call** is what keeps the
  free tier's 5-calls/minute budget viable for a 10+ ticker watchlist
- Timestamps in the raw JSON are Unix nanoseconds for trades/quotes, milliseconds for aggregate
  bars — the Python client normalizes `LastTrade.timestamp` to milliseconds
- During non-market hours (or on the free plan, always), `last_trade` reflects the last trade of
  the most recent session, not a synthetic "closed market" value
- `client.get_snapshot_all` accepts a `tickers` list positionally consistent with the union of
  watchlist + open positions that FinAlly tracks (see `MARKET_INTERFACE.md`, "Shared Price
  Cache" / active ticker set)
