# Testing Patterns

**Analysis Date:** 2026-08-22

## Test Framework

**Runner:**
- Framework: pytest 8.3.0+
- Configuration: `pyproject.toml` in `backend/`
  - Test paths: `testpaths = ["tests"]`
  - Python files: `python_files = ["test_*.py"]`
  - Test classes: `python_classes = ["Test*"]`
  - Test functions: `python_functions = ["test_*"]`
- Async support: `pytest-asyncio` 0.24.0+
  - Mode: `asyncio_mode = "auto"` (automatically marks async tests)
  - Scope: `asyncio_default_fixture_loop_scope = "function"` (fresh loop per test)

**Assertion Library:**
- Built-in `assert` statements (pytest style)
- Example: `assert update.ticker == "AAPL"`

**Run Commands:**
```bash
uv run --extra dev pytest -v              # Run all tests with verbose output
uv run --extra dev pytest --cov=app       # Run with coverage report
uv run --extra dev pytest tests/market/   # Run specific test directory
uv run --extra dev pytest -k test_cache   # Run tests matching pattern
uv run --extra dev ruff check app/ tests/ # Lint check
```

## Test File Organization

**Location:**
- Backend tests live in `backend/tests/` (mirroring `backend/app/` structure)
- Test files are co-located by module: `tests/market/test_cache.py` mirrors `app/market/cache.py`
- Frontend tests (to be created): `frontend/` project will follow Next.js/React conventions
- E2E tests (to be created): `test/` directory at repo root for Playwright tests

**Naming:**
- Test files: `test_<module_name>.py`
- Test classes: `Test<ComponentName>` (e.g., `TestPriceCache`, `TestSimulatorDataSource`)
- Test methods: `test_<scenario_description>` (e.g., `test_update_and_get`, `test_version_increments`)
- Descriptive names over abbreviated (prefer `test_cache_size_increments_on_update` over `test_inc`)

**Structure:**
```
backend/
├── app/
│   └── market/
│       ├── cache.py
│       ├── models.py
│       ├── simulator.py
│       └── ...
└── tests/
    ├── conftest.py           # Pytest configuration and shared fixtures
    └── market/
        ├── test_cache.py
        ├── test_models.py
        ├── test_simulator.py
        ├── test_simulator_source.py
        ├── test_stream.py
        ├── test_factory.py
        ├── test_massive.py
        └── __init__.py
```

## Test Structure

**Suite Organization:**
```python
class TestPriceUpdate:
    """Unit tests for the PriceUpdate model."""

    def test_price_update_creation(self):
        """Test basic PriceUpdate creation."""
        update = PriceUpdate(ticker="AAPL", price=190.50, previous_price=190.00, timestamp=1234567890.0)
        assert update.ticker == "AAPL"
        assert update.price == 190.50
```

**Patterns:**
- Test classes group related tests (one class per main component/module)
- Each test method has a single responsibility (one assertion scenario per method, or closely related assertions)
- Docstrings on every test method explain what is being tested
- Arrange-Act-Assert (AAA) pattern within each test:
  ```python
  def test_direction_up(self):
      # Arrange
      cache = PriceCache()
      cache.update("AAPL", 190.00)
      # Act
      update = cache.update("AAPL", 191.00)
      # Assert
      assert update.direction == "up"
  ```

**Naming Pattern Example (from test_models.py):**
```python
class TestPriceUpdate:
    def test_price_update_creation(self):
    def test_change_calculation(self):
    def test_change_negative(self):
    def test_change_percent_up(self):
    def test_change_percent_down(self):
    def test_change_percent_zero_previous(self):
    def test_direction_up(self):
    def test_direction_down(self):
    def test_direction_flat(self):
    def test_to_dict(self):
    def test_immutability(self):
```

## Mocking

**Framework:** Python `unittest.mock` (standard library)

**Patterns:**
- Environment variable mocking with `patch.dict(os.environ, {...})`:
  ```python
  from unittest.mock import patch
  
  def test_creates_simulator_when_api_key_empty(self):
      cache = PriceCache()
      with patch.dict(os.environ, {"MASSIVE_API_KEY": ""}, clear=True):
          source = create_market_data_source(cache)
      assert isinstance(source, SimulatorDataSource)
  ```
- Fake objects for simple contracts (e.g., FakeRequest in stream tests):
  ```python
  class FakeRequest:
      def __init__(self, disconnect_after: int | None = None) -> None:
          self._calls = 0
          self._disconnect_after = disconnect_after
          self.client = SimpleNamespace(host="127.0.0.1")
  
      async def is_disconnected(self) -> bool:
          self._calls += 1
          if self._disconnect_after is not None and self._calls > self._disconnect_after:
              return True
          return False
  ```

**What to Mock:**
- External services: Massive API, environment variables, file I/O
- Request/response objects for testing endpoints
- Dependencies passed to classes (prefer injection)

**What NOT to Mock:**
- Internal state (cache, simulator state) — test real objects
- Pure functions (GBM math, direction calculation, serialization)
- The component under test itself
- Dataclasses (use real instances)

## Fixtures and Factories

**Test Data:**
- Seed data for simulators: `SEED_PRICES` from `app/market/seed_prices.py`
- Hard-coded prices in test setup:
  ```python
  def test_change_calculation(self):
      update = PriceUpdate(ticker="AAPL", price=190.50, previous_price=190.00, timestamp=1234567890.0)
      assert update.change == 0.50
  ```
- Factory functions tested separately (test_factory.py verifies factory behavior)

**Location:**
- Fixtures not yet formalized in conftest.py (only contains minimal setup)
- Test fixtures created inline within test methods (simple, explicit)
- Reusable setup patterns: Each test class creates its own `PriceCache()` or `GBMSimulator()`
  - This keeps tests isolated and readable; no shared state across tests

## Coverage

**Requirements:** None enforced in CI (no coverage threshold configured in pyproject.toml)

**View Coverage:**
```bash
uv run --extra dev pytest --cov=app --cov-report=html
# Opens htmlcov/index.html
```

**Configuration (pyproject.toml):**
```toml
[tool.coverage.run]
source = ["app"]
omit = ["tests/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
]
```

## Test Types

**Unit Tests:**
- Scope: Single class or function in isolation
- Examples:
  - `TestPriceUpdate` — dataclass field calculations, serialization
  - `TestPriceCache` — thread-safe cache get/set/remove
  - `TestGBMSimulator` — price generation, ticker management
  - `TestFactory` — correct source selection based on env vars
- Approach: Arrange simple inputs, call method, assert outputs
- No async (unless testing an async method directly)

**Integration Tests:**
- Scope: Component working with its dependencies (cache, background tasks, etc.)
- Examples:
  - `TestSimulatorDataSource` — start/stop lifecycle, add/remove ticker, version increments
  - `TestGenerateEvents` — SSE event generation, client disconnection, version changes
  - `TestMassiveDataSource` — API polling, error recovery (if testing real API)
- Approach: Set up component with real dependencies, run async task, verify side effects
- Async tests marked with `@pytest.mark.asyncio`:
  ```python
  @pytest.mark.asyncio
  class TestSimulatorDataSource:
      async def test_start_populates_cache(self):
          cache = PriceCache()
          source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
          await source.start(["AAPL", "GOOGL"])
          assert cache.get("AAPL") is not None
          await source.stop()
  ```

**E2E Tests:**
- Framework: Playwright (to be implemented in `test/` directory)
- Not yet created; will test full flow: UI → API → Backend → Database
- Expected coverage: user workflows (buy/sell, add ticker, chat, view positions)

## Common Patterns

**Async Testing:**
```python
@pytest.mark.asyncio
async def test_prices_update_over_time(self):
    """Async test with explicit setup/teardown."""
    cache = PriceCache()
    source = SimulatorDataSource(price_cache=cache, update_interval=0.05)
    await source.start(["AAPL"])
    
    initial_version = cache.version
    await asyncio.sleep(0.3)  # Let updates happen
    
    assert cache.version > initial_version
    
    await source.stop()
```

**Testing Background Task Termination:**
```python
async def test_stop_is_clean(self):
    """Verify stop() is idempotent."""
    cache = PriceCache()
    source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
    await source.start(["AAPL"])
    await source.stop()
    # Double stop should not raise
    await source.stop()
```

**Error Testing:**
```python
def test_immutability(self):
    """Test that PriceUpdate is immutable."""
    update = PriceUpdate(ticker="AAPL", price=190.50, previous_price=190.00, timestamp=1234567890.0)
    with pytest.raises(AttributeError):
        update.price = 200.00  # Should raise error
```

**Testing Edge Cases:**
```python
def test_change_percent_zero_previous(self):
    """Test percentage change with zero previous price."""
    update = PriceUpdate(ticker="AAPL", price=100.00, previous_price=0.00, timestamp=1234567890.0)
    assert update.change_percent == 0.0
```

**Testing Async Event Generator:**
```python
async def test_data_frame_emitted_once_when_version_unchanged(self):
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    request = FakeRequest(disconnect_after=3)
    
    events = [event async for event in _generate_events(cache, request, interval=0.01)]
    
    data_events = [e for e in events if e.startswith("data:")]
    assert len(data_events) == 1
    payload = _parse_data_frame(data_events[0])
    assert payload["AAPL"]["price"] == 190.0
```

**Testing Cancellation Resilience:**
```python
async def test_cancellation_is_handled_cleanly(self):
    cache = PriceCache()
    request = FakeRequest(disconnect_after=None)
    gen = _generate_events(cache, request, interval=10)
    
    async def consume():
        async for _ in gen:
            pass
    
    task = asyncio.create_task(consume())
    await asyncio.sleep(0.05)  # let it enter the sleep between ticks
    task.cancel()
    
    await asyncio.wait_for(task, timeout=1.0)
    assert not task.cancelled()
```

## Test Statistics

**Current Coverage (as of 2026-08-22):**
- Total test methods: ~40+ across market data module
- Test files: 8 files in `backend/tests/market/`
- Code files tested: `cache.py`, `models.py`, `simulator.py`, `factory.py`, `stream.py`, `massive_client.py`, `interface.py`
- Async tests: ~15+ using `@pytest.mark.asyncio`

**Test Distribution:**
- Unit tests (synchronous): ~25 methods in `test_models.py`, `test_cache.py`, `test_factory.py`
- Integration tests (async): ~15 methods in `test_simulator_source.py`, `test_stream.py`
- Simulator math tests: ~5 methods verifying GBM correctness

## Conftest

**File:** `backend/tests/conftest.py` (currently minimal, may be expanded)

**Purpose:** Shared pytest configuration and reusable fixtures (currently empty but available for future use)

**Example Future Use:**
```python
@pytest.fixture
def price_cache():
    """Fresh PriceCache for each test."""
    return PriceCache()

@pytest.fixture
def simulator(price_cache):
    """SimulatorDataSource with minimal config."""
    return SimulatorDataSource(price_cache=price_cache, update_interval=0.01)
```

---

*Testing analysis: 2026-08-22*
