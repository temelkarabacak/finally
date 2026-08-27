"""Tests for LLM-proposed trade/watchlist auto-execution (CHAT-02/CHAT-03).

Real temp DB (initialized_db), a real PriceCache seeded from SEED_PRICES,
and FakeMarketSource (imported from tests.portfolio.test_trades) stand in
for the manual endpoints' own fixtures -- the executor must behave
identically to those endpoints since it calls the same functions.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime

import pytest

from app.llm.executor import apply_watchlist_change, execute_actions
from app.llm.persistence import save_chat_message
from app.llm.schemas import ChatResponse, TradeAction, WatchlistChange
from app.market.cache import PriceCache
from app.market.seed_prices import SEED_PRICES
from tests.portfolio.test_trades import FakeMarketSource


def _insert_position(
    conn: sqlite3.Connection, ticker: str, quantity: float, avg_cost: float
) -> None:
    conn.execute(
        "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
        "VALUES (?, 'default', ?, ?, ?, ?)",
        (uuid.uuid4().hex, ticker, quantity, avg_cost, datetime.now(UTC).isoformat()),
    )


@pytest.fixture
def seeded_cache() -> PriceCache:
    cache = PriceCache()
    for ticker, price in SEED_PRICES.items():
        cache.update(ticker, price)
    return cache


@pytest.fixture
def market_source() -> FakeMarketSource:
    return FakeMarketSource()


class TestExecuteActionsTrades:
    """CHAT-02: trades auto-execute through execute_trade(), never clamped."""

    async def test_affordable_buy_returns_success_with_fill_price(
        self, initialized_db, seeded_cache, market_source
    ):
        parsed = ChatResponse(
            message="ok", trades=[TradeAction(ticker="AAPL", side="buy", quantity=1.0)]
        )

        actions = await execute_actions(initialized_db, seeded_cache, market_source, parsed)

        assert len(actions["trades"]) == 1
        entry = actions["trades"][0]
        assert entry["success"] is True
        assert entry["ticker"] == "AAPL"
        assert entry["side"] == "buy"
        assert entry["quantity"] == 1.0
        assert entry["price"] == SEED_PRICES["AAPL"]

    async def test_over_cash_buy_rejected_with_reason_and_no_trade_row(
        self, initialized_db, seeded_cache, market_source
    ):
        parsed = ChatResponse(
            message="ok", trades=[TradeAction(ticker="TSLA", side="buy", quantity=10000.0)]
        )

        actions = await execute_actions(initialized_db, seeded_cache, market_source, parsed)

        entry = actions["trades"][0]
        assert entry["success"] is False
        assert entry["reason"]
        assert initialized_db.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0

    async def test_over_holding_sell_rejected_and_position_unchanged(
        self, initialized_db, seeded_cache, market_source
    ):
        _insert_position(initialized_db, "META", 1.0, 400.0)
        parsed = ChatResponse(
            message="ok", trades=[TradeAction(ticker="META", side="sell", quantity=50.0)]
        )

        actions = await execute_actions(initialized_db, seeded_cache, market_source, parsed)

        entry = actions["trades"][0]
        assert entry["success"] is False
        qty = initialized_db.execute(
            "SELECT quantity FROM positions WHERE ticker = 'META'"
        ).fetchone()[0]
        assert qty == 1.0

    async def test_successful_buy_of_unwatched_ticker_calls_add_ticker(
        self, initialized_db, seeded_cache, market_source
    ):
        seeded_cache.update("PYPL", 50.0)
        parsed = ChatResponse(
            message="ok", trades=[TradeAction(ticker="PYPL", side="buy", quantity=1.0)]
        )

        await execute_actions(initialized_db, seeded_cache, market_source, parsed)

        assert "PYPL" in market_source.add_calls


class TestApplyWatchlistChange:
    """CHAT-03: watchlist changes mirror watchlist/router.py's own rules exactly."""

    async def test_add_already_present_rejected_without_source_call(
        self, initialized_db, market_source
    ):
        # AAPL is already on the seeded default watchlist (app/db/seed.py).
        result = await apply_watchlist_change(
            initialized_db, market_source, WatchlistChange(ticker="AAPL", action="add")
        )

        assert result["success"] is False
        assert result["reason"]
        assert market_source.add_calls == []

    async def test_remove_not_present_rejected(self, initialized_db, market_source):
        result = await apply_watchlist_change(
            initialized_db, market_source, WatchlistChange(ticker="ZZZZ", action="remove")
        )

        assert result["success"] is False
        assert result["reason"]

    async def test_remove_with_open_position_succeeds_without_removing_from_source(
        self, initialized_db, market_source
    ):
        # META is already on the seeded default watchlist (app/db/seed.py).
        _insert_position(initialized_db, "META", 1.0, 400.0)

        result = await apply_watchlist_change(
            initialized_db, market_source, WatchlistChange(ticker="META", action="remove")
        )

        assert result["success"] is True
        assert market_source.remove_calls == []


class TestExecuteActionsMultiAction:
    """A multi-action turn writes all actions as one unit -- no nested BEGIN."""

    async def test_two_trades_plus_watchlist_change_returns_three_entries(
        self, initialized_db, seeded_cache, market_source
    ):
        seeded_cache.update("PYPL", 50.0)
        parsed = ChatResponse(
            message="ok",
            trades=[
                TradeAction(ticker="AAPL", side="buy", quantity=1.0),
                TradeAction(ticker="MSFT", side="buy", quantity=1.0),
            ],
            watchlist_changes=[WatchlistChange(ticker="PYPL", action="add")],
        )

        actions = await execute_actions(initialized_db, seeded_cache, market_source, parsed)

        assert len(actions["trades"]) + len(actions["watchlist_changes"]) == 3


class TestExecutionDerivedPersistence:
    """The persisted chat_messages.actions JSON reflects executor output, not the model's ask."""

    async def test_rejected_trade_persists_success_false_and_reason(
        self, initialized_db, seeded_cache, market_source
    ):
        parsed = ChatResponse(
            message="ok", trades=[TradeAction(ticker="TSLA", side="buy", quantity=10000.0)]
        )

        actions = await execute_actions(initialized_db, seeded_cache, market_source, parsed)
        save_chat_message(initialized_db, role="assistant", content="ok", actions=actions)

        row = initialized_db.execute(
            "SELECT actions FROM chat_messages WHERE role = 'assistant'"
        ).fetchone()
        stored = json.loads(row[0])

        assert stored["trades"][0]["success"] is False
        assert stored["trades"][0]["reason"]
