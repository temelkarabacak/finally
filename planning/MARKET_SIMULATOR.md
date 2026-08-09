# Market Simulator Design

Design of FinAlly's built-in price simulator — the default market data source, used whenever
`MASSIVE_API_KEY` is not set (see `MARKET_INTERFACE.md` for how it plugs into the shared
interface). Implemented in `backend/app/market/simulator.py` and `seed_prices.py`.

## Why Simulate Rather Than Always Call Massive

Per `MASSIVE_API.md`, Massive's free tier only returns end-of-day prices, and even the cheapest
plan with any live-ish data (Starter, $29/mo) is 15-minute delayed. A course project that most
students run without paying for a market data subscription needs a default that actually looks
alive — smoothly ticking, correlated, occasionally dramatic — without any external dependency or
API key. The simulator is that default; Massive is the opt-in upgrade for real data.

## Model: Geometric Brownian Motion

Each ticker's price evolves independently (before correlation is layered in) under GBM, the
standard continuous-time model for a randomly walking asset price:

```
S(t+dt) = S(t) * exp((mu - sigma^2/2) * dt + sigma * sqrt(dt) * Z)
```

- `S(t)` — current price
- `mu` — annualized drift (expected return)
- `sigma` — annualized volatility
- `dt` — time step, expressed as a fraction of a trading year
- `Z` — a standard normal random draw (correlated across tickers — see below)

The `-sigma^2/2` term is the standard Itô correction that keeps the *expected* price growth at
`mu` despite compounding a lognormal process — without it, volatility would bias the price
upward over time as an artifact of the model, not because `mu` actually increased.

### Choosing `dt`

Prices update every 500ms. `dt` is that tick expressed as a fraction of a trading year:

```python
TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600  # 5,896,800 (252 trading days, 6.5h sessions)
DEFAULT_DT = 0.5 / TRADING_SECONDS_PER_YEAR   # ~8.48e-8
```

At this scale `dt` is tiny, so each individual tick's drift and diffusion terms are sub-cent —
prices move naturally and continuously tick-to-tick rather than jumping, and the *annualized*
`sigma`/`mu` still produce realistic day-over-day and week-over-week price ranges when
compounded across thousands of ticks.

## Correlated Moves

Real markets don't move ticker-by-ticker independently — tech stocks tend to rise and fall
together, financials move together, and some names (Tesla) mostly do their own thing regardless
of sector. The simulator reproduces this by drawing correlated, not independent, random shocks
each tick.

1. Build an `n x n` correlation matrix from sector groupings (`seed_prices.py`):
   - Same tech-sector pair → `0.6`
   - Same finance-sector pair → `0.5`
   - Any pair involving TSLA → `0.3` (TSLA behaves independently of everything, including other
     tech names)
   - Everything else (cross-sector, unknown tickers) → `0.3`
2. Cholesky-decompose that correlation matrix once per ticker-set change (add/remove), not per
   tick — it's `O(n^2)`, cheap enough to rebuild on membership changes but wasteful to redo on
   every 500ms step
3. Each tick: draw `n` independent standard normals, then multiply by the Cholesky factor to get
   `n` correlated standard normals — one of numerical linear algebra's standard tricks for
   turning independent noise into noise with a target covariance structure

```python
z_independent = np.random.standard_normal(n)
z_correlated = self._cholesky @ z_independent   # shape (n,), correlated per the matrix above
```

With `n < 50` tickers this whole step — matrix rebuild included — is fast enough to run inline
in the same coroutine as the price update; there's no need to offload it to a thread or process.

## Random Shock Events

A small per-tick, per-ticker chance (`event_probability = 0.001`, i.e. 0.1%) of an additional
sudden 2–5% move, sign chosen at random:

```python
if random.random() < self._event_prob:
    shock_magnitude = random.uniform(0.02, 0.05)
    shock_sign = random.choice([-1, 1])
    self._prices[ticker] *= 1 + shock_magnitude * shock_sign
```

With 10 tickers at 2 ticks/second, that works out to roughly one shock event somewhere in the
watchlist every ~50 seconds — enough to periodically flash a big red or green move for demo
purposes without every session looking scripted or, conversely, without moves being so rare a
short demo never sees one.

## Seed Data (`seed_prices.py`)

Starting prices and per-ticker GBM parameters for the default watchlist, chosen to look like
realistic 2024-era prices and volatility profiles rather than arbitrary round numbers:

| Ticker | Seed price | sigma (volatility) | mu (drift) | Notes |
|---|---|---|---|---|
| AAPL | $190.00 | 0.22 | 0.05 | |
| GOOGL | $175.00 | 0.25 | 0.05 | |
| MSFT | $420.00 | 0.20 | 0.05 | |
| AMZN | $185.00 | 0.28 | 0.05 | |
| TSLA | $250.00 | 0.50 | 0.03 | High volatility |
| NVDA | $800.00 | 0.40 | 0.08 | High volatility, strong drift |
| META | $500.00 | 0.30 | 0.05 | |
| JPM | $195.00 | 0.18 | 0.04 | Low volatility (bank) |
| V | $280.00 | 0.17 | 0.04 | Low volatility (payments) |
| NFLX | $600.00 | 0.35 | 0.05 | |

Tickers added dynamically (via watchlist add or AI chat) that aren't in this table fall back to
`DEFAULT_PARAMS = {"sigma": 0.25, "mu": 0.05}` and a random seed price in `[$50, $300]` — plausible
enough for a ticker the simulator has no real data for, without needing a lookup to an external
source just to pick a starting point.

## Code Structure

```
seed_prices.py
    SEED_PRICES        dict[ticker, float]           starting prices
    TICKER_PARAMS       dict[ticker, {sigma, mu}]      per-ticker GBM params
    DEFAULT_PARAMS       {sigma, mu}                    fallback for unknown tickers
    CORRELATION_GROUPS   {"tech": {...}, "finance": {...}}
    INTRA_TECH_CORR, INTRA_FINANCE_CORR, CROSS_GROUP_CORR, TSLA_CORR   correlation coefficients

simulator.py
    GBMSimulator          pure math/state — no asyncio, no cache, independently testable
        step() -> dict[ticker, price]      advance one tick, the hot path
        add_ticker() / remove_ticker()     mutate tracked set, rebuild Cholesky
        get_price() / get_tickers()

    SimulatorDataSource(MarketDataSource)   asyncio wrapper implementing the shared interface
        start(tickers)   creates GBMSimulator, seeds the cache immediately, launches the loop
        _run_loop()      calls step() every update_interval (0.5s), writes each price to PriceCache
        add_ticker() / remove_ticker() / stop()
```

Splitting `GBMSimulator` (pure computation) from `SimulatorDataSource` (asyncio lifecycle +
`PriceCache` writes) means the math — the part worth unit-testing precisely (drift/diffusion
correctness, correlation structure, event frequency) — has no dependency on asyncio or the cache,
and can be tested by calling `step()` directly and inspecting the returned prices.

## Startup Behavior

`start()` seeds the cache with each ticker's initial price *before* launching the background
loop, so the very first SSE payload after a client connects already has data — there's no
"blank until the first tick" gap. The same applies to `add_ticker()`: a newly added ticker gets
an immediate cache entry rather than waiting up to 500ms for the next loop iteration.

## What This Design Deliberately Skips

- **No order book / bid-ask spread simulation** — FinAlly only needs a single tradable price per
  tick (market orders only, per PLAN.md §4); modeling a spread would add complexity nothing
  downstream consumes
- **No market-hours gating** — the simulator runs continuously regardless of real market hours,
  since a course demo shouldn't go quiet because it's 9pm; this is the opposite tradeoff from
  Massive, where the real market genuinely does close
- **No persistence of simulator state across restarts** — prices reseed from `SEED_PRICES` on
  every process start; there's no requirement for simulated history to survive a restart, unlike
  the SQLite-backed portfolio data
