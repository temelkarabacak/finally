# Market Data Backend — Code Review

**Date:** 2026-08-12
**Scope:** `backend/app/market/` (9 files) and `backend/tests/market/` (6 test files)
**Reviewer context:** Full read of `planning/PLAN.md`, `MARKET_INTERFACE.md`, `MARKET_SIMULATOR.md`,
`MASSIVE_API.md`, `MARKET_DATA_DESIGN.md`, `MARKET_DATA_SUMMARY.md`, and the prior
`planning/archive/MARKET_DATA_REVIEW.md` (2026-02-10), followed by a line-by-line read of every
source and test file and a live test/lint/coverage run.

---

## 1. Test Results

**73 tests collected, 73 passed, 0 failed.** (`uv run --extra dev pytest -v`)

This is an improvement over the prior review's snapshot (68/73 passing, 5 failing due to a
`massive`-package environment issue) — that issue is gone because `massive` is now a real,
installed core dependency rather than a lazily-imported one.

**Lint (ruff):** `uv run --extra dev ruff check app/ tests/` → **all checks passed**, zero
warnings. The unused-import findings from the prior review are gone.

**Coverage:** 91% overall (`uv run --extra dev pytest --cov=app --cov-report=term-missing`).

| Module | Coverage | Notes |
|---|---|---|
| `models.py` | 100% | |
| `cache.py` | 100% | |
| `interface.py` | 100% | |
| `seed_prices.py` | 100% | |
| `factory.py` | 100% | |
| `__init__.py` | 100% | |
| `simulator.py` | 98% | Uncovered: duplicate-add guard (`_add_ticker_internal` early return), exception-log line in `_run_loop` |
| `massive_client.py` | 94% | Uncovered: `_poll_loop`'s sleep/retry line, `_fetch_snapshots` body (never runs unmocked — expected, per design) |
| `stream.py` | 33% | **No dedicated tests.** Only import-time module code executes; the SSE generator itself (`_generate_events`) has zero test coverage. Same gap flagged in the prior review (was 31%), still unaddressed. |

One thing worth being precise about: `MARKET_DATA_SUMMARY.md` states "73 tests, all passing... 84%
coverage." The test count and pass rate match exactly; the 84%→91% coverage delta isn't a
regression story, it's almost certainly a different total-statement denominator (this run
includes `massive_client.py` at 94% rather than the 56% the summary cites, which tracks with
`massive` now being a real installed dependency instead of mocked-out-of-existence). Not a
concern, just a note for anyone diffing the numbers.

---

## 2. Architecture Assessment

The subsystem is a clean strategy pattern, exactly as designed:

```
MarketDataSource (ABC)
├── SimulatorDataSource  (GBM simulator)
└── MassiveDataSource    (Polygon.io/Massive REST poller)
        │
        ▼
   PriceCache (shared, thread-safe)
        │
        ▼
   SSE stream → Frontend (not yet built)
```

I diffed every code block embedded in `MARKET_DATA_DESIGN.md` §3–§9 against the actual files in
`backend/app/market/` — they match exactly, statement for statement. The design doc's claim that
those sections are "the actual, current source, not a proposal" is accurate. §10–§12 (FastAPI
lifespan wiring, permanent Massive failover orchestration, watchlist coordination) are correctly
marked as not-yet-implemented — `backend/app/main.py` does not exist, confirmed by directory
listing. This review scopes itself to what's actually built (§1–§9), same as the design doc does.

**Strengths, confirmed by reading and exercising the code:**

- Clear single-responsibility modules; `app/market/__init__.py` re-exports a clean public surface.
- `massive` as a real top-level dependency (not lazy-imported) removes an entire class of test
  fragility the prior review documented — confirmed by the clean test run above.
- `PriceCache` as the sole producer/consumer seam is well-executed: no downstream code branches on
  which source is active.
- The GBM math is correct — verified the Itô-corrected drift term and ran `GBMSimulator` with the
  full 10-ticker default watchlist for several steps; the Cholesky decomposition succeeds and
  prices stay sane (no NaN/negative values, no exceptions). The prior review's suggested-but-never-added
  test ("no test for `GBMSimulator` with all 10 default tickers") is still genuinely missing from
  the suite, though I confirmed by hand that it works.
- Background tasks (`SimulatorDataSource`, `MassiveDataSource`) are cancellable and idempotent on
  `stop()` — both guard on `self._task and not self._task.done()`, and the test suite exercises
  double-`stop()` for both.
- The version-counter change-detection pattern in `PriceCache`/`stream.py` is the right call: an
  int comparison instead of a dict diff on every 500ms SSE tick.

---

## 3. Status of the Prior Review's Findings

The prior review (`planning/archive/MARKET_DATA_REVIEW.md`, 2026-02-10) listed 7 issues.
`MARKET_DATA_SUMMARY.md` claims all 7 were resolved. I verified each individually against current
source:

| # | Prior finding | Status |
|---|---|---|
| 3.1 | Missing `[tool.hatch.build.targets.wheel]` in `pyproject.toml` | **Fixed** — present, `uv sync` succeeds |
| 3.2 | Massive tests fragile without `massive` installed (lazy import) | **Fixed** — `massive` is a core dependency, imported at module level, all 13 `test_massive.py` tests pass |
| 3.3 | `_generate_events` return type is `-> None` instead of `AsyncGenerator[str, None]` | **Fixed** — correctly annotated |
| 3.4 | `PriceCache.version` property reads `self._version` without the lock | **Not fixed** — still unguarded (see §4.5 below; still low severity) |
| 3.5 | `SimulatorDataSource.get_tickers()` reached into `GBMSimulator._tickers` (private) | **Fixed** — `GBMSimulator.get_tickers()` is now public and used |
| 3.6 | Module-level `router` in `stream.py`; calling `create_stream_router()` twice double-registers `/prices` | **Not fixed** — still present (see §4.4 below) |
| 3.7 | Unused imports in 4 test files (`pytest`, `math`, `asyncio`) | **Fixed** — ruff is clean |
| — | `DEFAULT_CORR` defined but unused, confusing vs. `CROSS_GROUP_CORR` | **Fixed** — removed, `seed_prices.py` now only has `CROSS_GROUP_CORR` |
| — | No SSE integration test ("nice to have") | **Not fixed** — `stream.py` still has no dedicated test file |

5 of 7 numbered issues are genuinely fixed, plus the `DEFAULT_CORR` cleanup. The two "not fixed"
items were both flagged Low/"nice to have" in the prior review, so `MARKET_DATA_SUMMARY.md`'s "all
issues resolved" isn't materially wrong — but the SSE test gap in particular is worth re-raising
now that it's the *only* module still without any dedicated tests, not just one of several.

---

## 4. New Findings

### 4.1 Ticker normalization is inconsistent between the two `MarketDataSource` implementations (Medium)

`MassiveDataSource.add_ticker` / `.remove_ticker` normalize the ticker (`ticker.upper().strip()`)
before touching internal state:

```python
# massive_client.py
async def add_ticker(self, ticker: str) -> None:
    ticker = ticker.upper().strip()
    if ticker not in self._tickers:
        self._tickers.append(ticker)
```

`SimulatorDataSource.add_ticker` / `.remove_ticker` (and the `GBMSimulator` methods they call) do
not — the ticker is used exactly as given. I reproduced this directly:

```python
source = SimulatorDataSource(price_cache=cache, update_interval=10)
await source.start(["AAPL"])
await source.add_ticker("  tsla  ")
source.get_tickers()        # ['AAPL', '  tsla  ']
cache.get_all().keys()      # ['AAPL', '  tsla  ']
```

vs. the identical call against `MassiveDataSource`, which would normalize to `'TSLA'`.

This breaks the "one abstract contract, source-agnostic downstream code" premise both
`MARKET_INTERFACE.md` and `MARKET_DATA_DESIGN.md` state explicitly as the reason this interface
exists. It's currently masked because the one call site sketched in `MARKET_DATA_DESIGN.md` §12
normalizes the ticker *before* calling `source.add_ticker()` — but that's a convention living in
not-yet-written route-handler code, not something the interface itself guarantees, and nothing
stops a future caller (e.g., the LLM chat's `watchlist_changes` handler) from calling
`add_ticker()` directly with an unnormalized string. If that happens while running the simulator,
the ticker ends up in the cache under a different, non-canonical key than the one the watchlist/
positions/portfolio code will look it up under.

**Suggested fix:** normalize in exactly one place — either push `.upper().strip()` into
`SimulatorDataSource.add_ticker`/`remove_ticker` to match Massive, or (cleaner) do it once in a
shared helper both implementations call, so the `MarketDataSource` contract itself guarantees
normalized tickers regardless of which source is active.

### 4.2 `PriceCache.update()` silently discards an explicit `timestamp=0.0` (Low)

```python
ts = timestamp or time.time()
```

`0 or x` evaluates to `x` in Python — a caller that explicitly passes `timestamp=0.0` (Unix epoch)
gets the current wall-clock time instead, silently. In practice nothing in the current codebase
calls `update()` with `timestamp=0.0`, so this is latent rather than active, but it's a real
falsy-zero bug, not a hypothetical one — worth a one-line fix before it becomes a confusing test
failure for whoever eventually writes a "timestamp defaults correctly" test:

```python
ts = timestamp if timestamp is not None else time.time()
```

### 4.3 `stream.py` (SSE endpoint) is effectively untested (Medium, carried over)

33% coverage, and the 33% that *is* covered is import-time module setup, not the generator's
actual behavior. There is no test exercising:
- that a `retry: 1000\n\n` frame is sent first,
- that a `data:` frame is only emitted when `price_cache.version` changes (the whole point of the
  version-counter design),
- that the loop actually stops when `request.is_disconnected()` returns `True`,
- that an empty cache produces no `data:` frames rather than an empty-object frame.

This is the one piece of the built subsystem with a real behavioral gap, not just a nice-to-have.
It's also the most naturally testable of the remaining gaps — `_generate_events()` takes a
`PriceCache` and a `Request` directly and is a plain async generator, so it doesn't need a running
ASGI server or `TestClient`; a fake/mock `Request` whose `is_disconnected()` returns `True` after N
calls is enough to drive it through several iterations and assert on the yielded strings.

### 4.4 Module-level `router` singleton in `stream.py` (Low, carried over)

```python
router = APIRouter(prefix="/api/stream", tags=["streaming"])

def create_stream_router(price_cache: PriceCache) -> APIRouter:
    @router.get("/prices")
    async def stream_prices(...): ...
    return router
```

`create_stream_router()` registers a new route closure onto the *same* module-level `router`
object every time it's called, rather than constructing a fresh `APIRouter` per call. A second
call (e.g., two tests in the same process each building their own `PriceCache` and expecting an
isolated router, or a future hot-reload/multi-app scenario) would leave two competing `/prices`
routes registered on one shared router instance. Doesn't matter for a single `main.py` calling this
once at startup, which is presumably why it wasn't prioritized — but it will bite the first test
suite that calls `create_stream_router()` more than once in-process (which §13 of
`MARKET_DATA_DESIGN.md` implicitly calls for, to test the SSE endpoint per §4.3 above). Trivial
fix: move `router = APIRouter(...)` inside the factory function.

### 4.5 `PriceCache.version` read without the lock (Low, carried over, still acceptable)

Unchanged from the prior review. Reading a single `int` attribute is atomic under CPython's GIL,
so this is not an active bug. Restating only because it's still inconsistent with the rest of the
class's locking discipline, and because `MARKET_DATA_DESIGN.md` doesn't mention it as a known,
accepted tradeoff anywhere (unlike, say, the "no order book" and "no market-hours gating"
decisions, which are explicitly called out as deliberate). Low priority; a one-line fix if anyone
touches this method again.

### 4.6 `conftest.py`'s `event_loop_policy` fixture produces a warning on every async test (Trivial)

```python
@pytest.fixture
def event_loop_policy():
    import asyncio
    return asyncio.DefaultEventLoopPolicy()
```

This fires a `DeprecationWarning` (`asyncio.DefaultEventLoopPolicy` is slated for removal in
Python 3.16) on all 73 test collections that touch async fixtures — the full test run currently
prints 73 warnings, all this same line. `pytest-asyncio`'s `asyncio_mode = "auto"` (already set in
`pyproject.toml`) doesn't require overriding this fixture; nothing in the suite appears to depend
on the override actually being `DefaultEventLoopPolicy` specifically. Deleting the fixture
entirely would likely clear all 73 warnings with no behavior change — worth a quick try, though I
did not modify test files as part of this review.

---

## 5. Design Observations

- **GBM parameter tuning is sound.** TSLA at `sigma=0.50` vs. V at `0.17` reflects real relative
  volatility; the ~0.1%-per-tick shock event (verified against the stated "~every 50 seconds with
  10 tickers" claim: 10 tickers × 2 ticks/sec × 0.001 ≈ 0.02 events/sec ≈ one every 50s — the math
  checks out) adds visible drama without destabilizing the underlying random walk.
- **Cholesky-based correlation is the correct tool** and, per §2 above, holds up numerically for
  the full default 10-ticker watchlist, not just the 1–2-ticker cases the test suite exercises.
- **Exception handling in both background loops is appropriately broad-but-logged** — `_run_loop`
  and `_poll_once` both catch and log rather than letting one bad tick or one dropped HTTP call
  kill the whole feed, which is the right shape for a long-running task.
- **The Massive free-tier reality check (`MASSIVE_API.md`) is well-reasoned** and correctly reflected
  in code: `poll_interval=15.0` default, one call covers the whole watchlist via `get_snapshot_all`.
- **§10–§12 of `MARKET_DATA_DESIGN.md` (lifespan wiring, permanent failover, watchlist
  coordination) remain design-only**, as documented — no code review findings apply to them since
  there's no code yet. Worth flagging as the natural next slice of backend work, since the market
  data layer itself (§1–§9) is now in good enough shape to build on.

---

## 6. Verdict

The market data backend is solid, matches its design docs exactly, and the full test suite passes
cleanly with no lint issues. It's a good foundation for the FastAPI lifespan/failover/watchlist
work in §10–§12.

**Should fix before building on top of this layer:**
1. Ticker normalization inconsistency between `SimulatorDataSource` and `MassiveDataSource`
   (§4.1) — fix now, while there's only one call site (`market_data_demo.py`) and no watchlist API
   yet depending on either behavior.
2. `PriceCache.update()`'s falsy-zero timestamp bug (§4.2) — one-line fix.

**Should fix soon:**
3. Add SSE (`stream.py`) tests (§4.3) — the only module with a real coverage gap, not just a
   style nit; the version-diffing behavior it's supposed to guarantee is currently unverified.
4. Move `router = APIRouter(...)` inside `create_stream_router()` (§4.4) — needed before #3 can
   safely call the factory more than once per test session.

**Nice to have:**
5. Guard `PriceCache.version` under the lock for consistency (§4.5).
6. Remove or fix the `event_loop_policy` fixture in `conftest.py` to silence the 73 deprecation
   warnings (§4.6).
7. Add the "full 10-ticker default watchlist" `GBMSimulator` test the prior review suggested —
   confirmed by hand in this review (§2) but still not codified in the suite.
