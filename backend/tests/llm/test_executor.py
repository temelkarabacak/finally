"""Trade execution and watchlist mutation triggered by the assistant."""

from app.db import get_cash_balance, get_position, list_trades, list_watchlist
from app.llm.executor import apply_watchlist_change, execute_trade
from app.llm.schema import TradeInstruction, WatchlistChange


def buy(conn, cache, ticker="AAPL", quantity=10.0):
    return execute_trade(conn, cache, TradeInstruction(ticker=ticker, side="buy", quantity=quantity))


def test_buy_updates_cash_position_and_log(conn, price_cache):
    result = buy(conn, price_cache)

    assert result == {
        "ticker": "AAPL",
        "side": "buy",
        "quantity": 10.0,
        "price": 190.0,
        "status": "executed",
        "error": None,
    }
    assert get_cash_balance(conn) == 10000.0 - 1900.0
    position = get_position(conn, "AAPL")
    assert position.quantity == 10.0
    assert position.avg_cost == 190.0
    assert len(list_trades(conn)) == 1


def test_second_buy_averages_cost(conn, price_cache):
    buy(conn, price_cache, quantity=10)
    price_cache.update("AAPL", 210.0)
    buy(conn, price_cache, quantity=10)

    position = get_position(conn, "AAPL")
    assert position.quantity == 20.0
    assert position.avg_cost == 200.0


def test_buy_rejected_when_cash_insufficient(conn, price_cache):
    result = buy(conn, price_cache, quantity=1000)

    assert result["status"] == "rejected"
    assert "Insufficient cash" in result["error"]
    assert get_cash_balance(conn) == 10000.0
    assert get_position(conn, "AAPL") is None
    assert list_trades(conn) == []


def test_buy_is_never_clamped_to_available_cash(conn, price_cache):
    buy(conn, price_cache, quantity=60)  # 11400 > 10000
    assert get_position(conn, "AAPL") is None


def test_sell_reduces_position_and_returns_cash(conn, price_cache):
    buy(conn, price_cache, quantity=10)
    result = execute_trade(
        conn, price_cache, TradeInstruction(ticker="AAPL", side="sell", quantity=4)
    )

    assert result["status"] == "executed"
    assert get_position(conn, "AAPL").quantity == 6.0
    assert get_cash_balance(conn) == 10000.0 - 1900.0 + 760.0


def test_full_sell_deletes_position(conn, price_cache):
    buy(conn, price_cache, quantity=10)
    execute_trade(conn, price_cache, TradeInstruction(ticker="AAPL", side="sell", quantity=10))

    assert get_position(conn, "AAPL") is None
    assert get_cash_balance(conn) == 10000.0


def test_sell_more_than_held_is_rejected(conn, price_cache):
    buy(conn, price_cache, quantity=5)
    result = execute_trade(
        conn, price_cache, TradeInstruction(ticker="AAPL", side="sell", quantity=8)
    )

    assert result["status"] == "rejected"
    assert "Insufficient shares" in result["error"]
    assert get_position(conn, "AAPL").quantity == 5.0


def test_sell_with_no_position_is_rejected(conn, price_cache):
    result = execute_trade(
        conn, price_cache, TradeInstruction(ticker="MSFT", side="sell", quantity=1)
    )
    assert result["status"] == "rejected"


def test_fractional_quantities_supported(conn, price_cache):
    result = buy(conn, price_cache, ticker="TSLA", quantity=2.5)
    assert result["status"] == "executed"
    assert get_position(conn, "TSLA").quantity == 2.5


def test_unknown_ticker_rejected(conn, price_cache):
    result = buy(conn, price_cache, ticker="ZZZZ")
    assert result["status"] == "rejected"
    assert "No live price" in result["error"]


def test_non_positive_quantity_rejected(conn, price_cache):
    assert buy(conn, price_cache, quantity=0)["status"] == "rejected"
    assert buy(conn, price_cache, quantity=-5)["status"] == "rejected"


def test_ticker_is_normalised(conn, price_cache):
    result = buy(conn, price_cache, ticker=" aapl ")
    assert result["ticker"] == "AAPL"
    assert get_position(conn, "AAPL").quantity == 10.0


async def test_watchlist_add_and_remove(conn, source):
    added = await apply_watchlist_change(conn, source, WatchlistChange(ticker="PYPL", action="add"))
    assert added["status"] == "executed"
    assert "PYPL" in [e.ticker for e in list_watchlist(conn)]
    assert source.added == ["PYPL"]

    removed = await apply_watchlist_change(conn, source, WatchlistChange(ticker="PYPL", action="remove"))
    assert removed["status"] == "executed"
    assert "PYPL" not in [e.ticker for e in list_watchlist(conn)]
    assert source.removed == ["PYPL"]


async def test_removal_keeps_pricing_a_held_ticker(conn, price_cache, source):
    buy(conn, price_cache, ticker="AAPL", quantity=1)
    await apply_watchlist_change(conn, source, WatchlistChange(ticker="AAPL", action="remove"))
    assert source.removed == []


async def test_watchlist_duplicate_add_rejected(conn, source):
    result = await apply_watchlist_change(conn, source, WatchlistChange(ticker="AAPL", action="add"))
    assert result["status"] == "rejected"
    assert "already on the watchlist" in result["error"]


async def test_watchlist_remove_missing_rejected(conn, source):
    result = await apply_watchlist_change(conn, source, WatchlistChange(ticker="ZZZZ", action="remove"))
    assert result["status"] == "rejected"
