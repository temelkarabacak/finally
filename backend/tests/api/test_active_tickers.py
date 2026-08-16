"""The active ticker set is the watchlist union open positions."""

from app.db import remove_watchlist_ticker, upsert_position
from app.portfolio import active_tickers


def test_union_of_watchlist_and_positions(conn):
    upsert_position(conn, "SPY", quantity=3, avg_cost=500.0)
    remove_watchlist_ticker(conn, "AAPL")
    upsert_position(conn, "GOOGL", quantity=1, avg_cost=200.0)

    tickers = active_tickers(conn)

    assert "SPY" in tickers, "positions off the watchlist stay tracked"
    assert "AAPL" not in tickers
    assert tickers.count("GOOGL") == 1, "watched and held tickers appear once"
