"""Deterministic LLM_MOCK responder rules."""

from app.llm.mock import GREETING, mock_response

CONTEXT = {"cash_balance": 10000.0, "total_value": 10000.0, "positions": []}


def test_buy_instruction():
    result = mock_response("buy 10 AAPL", CONTEXT)
    assert [(t.ticker, t.side, t.quantity) for t in result.trades] == [("AAPL", "buy", 10.0)]
    assert "AAPL" in result.message


def test_sell_with_shares_of_phrasing_and_fraction():
    result = mock_response("sell 2.5 shares of TSLA", CONTEXT)
    assert [(t.ticker, t.side, t.quantity) for t in result.trades] == [("TSLA", "sell", 2.5)]


def test_multiple_trades_in_one_message():
    result = mock_response("buy 5 AAPL and sell 1 MSFT", CONTEXT)
    assert [t.ticker for t in result.trades] == ["AAPL", "MSFT"]


def test_watchlist_add_and_remove():
    added = mock_response("add PYPL to the watchlist", CONTEXT)
    assert [(c.ticker, c.action) for c in added.watchlist_changes] == [("PYPL", "add")]

    removed = mock_response("remove NFLX from watchlist", CONTEXT)
    assert [(c.ticker, c.action) for c in removed.watchlist_changes] == [("NFLX", "remove")]


def test_trade_and_watchlist_together():
    result = mock_response("buy 3 AAPL and add PYPL to the watchlist", CONTEXT)
    assert len(result.trades) == 1
    assert len(result.watchlist_changes) == 1


def test_portfolio_summary_has_no_actions():
    result = mock_response("how is my portfolio doing?", CONTEXT)
    assert result.trades == []
    assert "10000.00" in result.message


def test_portfolio_summary_lists_positions():
    context = {
        "cash_balance": 8100.0,
        "total_value": 10000.0,
        "positions": [
            {"ticker": "AAPL", "quantity": 10, "avg_cost": 190.0, "unrealized_pnl": 100.0}
        ],
    }
    assert "AAPL" in mock_response("show my positions", context).message


def test_fallback_greeting():
    result = mock_response("hello there", CONTEXT)
    assert result.message == GREETING
    assert result.trades == []


def test_lowercase_ticker_not_treated_as_a_trade():
    assert mock_response("buy 10 apples", CONTEXT).trades == []


def test_deterministic_across_calls():
    first = mock_response("buy 10 AAPL", CONTEXT)
    second = mock_response("buy 10 AAPL", CONTEXT)
    assert first.model_dump() == second.model_dump()
