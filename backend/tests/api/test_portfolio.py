"""Portfolio endpoints: valuation, trade execution and validation."""

from app.db import get_cash_balance, get_connection, get_position


def buy(client, ticker, quantity):
    return client.post(
        "/api/portfolio/trade", json={"ticker": ticker, "quantity": quantity, "side": "buy"}
    )


def sell(client, ticker, quantity):
    return client.post(
        "/api/portfolio/trade", json={"ticker": ticker, "quantity": quantity, "side": "sell"}
    )


def test_fresh_portfolio(client):
    body = client.get("/api/portfolio").json()
    assert body["cash_balance"] == 10000.0
    assert body["positions"] == []
    assert body["total_value"] == 10000.0
    assert body["unrealized_pnl"] == 0.0


def test_buy_updates_cash_and_position(client):
    response = buy(client, "AAPL", 10)
    assert response.status_code == 200

    body = response.json()
    assert body["trade"] == {
        "ticker": "AAPL",
        "side": "buy",
        "quantity": 10.0,
        "price": 100.0,
        "executed_at": body["trade"]["executed_at"],
    }

    portfolio = body["portfolio"]
    assert portfolio["cash_balance"] == 9000.0
    assert portfolio["total_value"] == 10000.0
    position = portfolio["positions"][0]
    assert position["ticker"] == "AAPL"
    assert position["quantity"] == 10.0
    assert position["avg_cost"] == 100.0
    assert position["unrealized_pnl"] == 0.0


def test_buy_is_case_insensitive(client, conn):
    assert buy(client, "aapl", 1).status_code == 200
    assert get_position(conn, "AAPL").quantity == 1.0


def test_fractional_buy(client):
    portfolio = buy(client, "MSFT", 0.25).json()["portfolio"]
    assert portfolio["cash_balance"] == 9900.0
    assert portfolio["positions"][0]["quantity"] == 0.25


def test_unrealized_pnl_tracks_price(client, cache):
    buy(client, "AAPL", 10)
    cache.update("AAPL", 110.0)

    position = client.get("/api/portfolio").json()["positions"][0]
    assert position["current_price"] == 110.0
    assert position["unrealized_pnl"] == 100.0
    assert position["pct_change"] == 10.0


def test_avg_cost_is_a_weighted_average(client, cache):
    buy(client, "AAPL", 10)
    cache.update("AAPL", 200.0)
    buy(client, "AAPL", 10)

    position = client.get("/api/portfolio").json()["positions"][0]
    assert position["quantity"] == 20.0
    assert position["avg_cost"] == 150.0


def test_partial_sell_keeps_avg_cost(client, cache):
    buy(client, "AAPL", 10)
    cache.update("AAPL", 150.0)
    portfolio = sell(client, "AAPL", 4).json()["portfolio"]

    position = portfolio["positions"][0]
    assert position["quantity"] == 6.0
    assert position["avg_cost"] == 100.0
    assert portfolio["cash_balance"] == 9600.0


def test_full_sell_deletes_the_position(client, conn):
    buy(client, "AAPL", 10)
    portfolio = sell(client, "AAPL", 10).json()["portfolio"]

    assert portfolio["positions"] == []
    assert portfolio["cash_balance"] == 10000.0
    assert get_position(conn, "AAPL") is None


def test_insufficient_cash_is_rejected(client, conn):
    response = buy(client, "AAPL", 1000)
    assert response.status_code == 400
    assert "Insufficient cash" in response.json()["detail"]
    assert get_cash_balance(conn) == 10000.0
    assert get_position(conn, "AAPL") is None


def test_insufficient_shares_is_rejected(client, conn):
    buy(client, "AAPL", 5)
    response = sell(client, "AAPL", 6)

    assert response.status_code == 400
    assert "Insufficient shares" in response.json()["detail"]
    assert get_position(conn, "AAPL").quantity == 5.0
    assert get_cash_balance(conn) == 9500.0


def test_non_positive_quantity_is_rejected(client):
    assert buy(client, "AAPL", 0).status_code == 400
    assert buy(client, "AAPL", -5).status_code == 400


def test_unpriced_ticker_is_rejected(client):
    response = buy(client, "ZZZZ", 1)
    assert response.status_code == 400
    assert "No live price" in response.json()["detail"]


def test_unknown_side_is_rejected(client):
    response = client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 1, "side": "hold"}
    )
    assert response.status_code == 422


def test_trade_records_a_snapshot(client):
    assert client.get("/api/portfolio/history").json() == []

    buy(client, "AAPL", 10)
    history = client.get("/api/portfolio/history").json()

    assert len(history) == 1
    assert history[0]["total_value"] == 10000.0

    sell(client, "AAPL", 5)
    assert len(client.get("/api/portfolio/history").json()) == 2


def test_rejected_trade_records_no_snapshot(client):
    buy(client, "AAPL", 1000)
    assert client.get("/api/portfolio/history").json() == []


def test_selling_a_position_off_the_watchlist_stops_pricing_it(client, source, conn):
    buy(client, "AAPL", 5)
    client.delete("/api/watchlist/AAPL")
    assert "AAPL" in source.get_tickers()

    sell(client, "AAPL", 5)
    assert "AAPL" not in source.get_tickers()


def test_trade_is_committed_before_responding(client, db_path):
    """A client refetching immediately after a trade must see it.

    get_db commits after the response is sent (FastAPI runs yield-dependency
    exit code post-response), so the handler commits itself.
    """
    buy(client, "AAPL", 3)

    reader = get_connection(db_path)
    try:
        assert reader.execute("SELECT cash_balance FROM users_profile").fetchone()[0] == 9700.0
    finally:
        reader.close()
