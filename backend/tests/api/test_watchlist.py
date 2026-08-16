"""Watchlist endpoints and their effect on the active ticker set."""

DEFAULT_TICKERS = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]


def tickers_of(response):
    return [item["ticker"] for item in response.json()]


def test_default_watchlist_is_seeded(client):
    response = client.get("/api/watchlist")
    assert response.status_code == 200
    assert sorted(tickers_of(response)) == sorted(DEFAULT_TICKERS)


def test_watchlist_includes_cached_prices(client):
    items = {item["ticker"]: item for item in client.get("/api/watchlist").json()}
    assert items["AAPL"]["price"] == 100.0
    assert items["AAPL"]["direction"] == "flat"
    assert items["NFLX"]["price"] is None


def test_add_ticker_starts_pricing_it(client, source):
    response = client.post("/api/watchlist", json={"ticker": "pypl"})
    assert response.status_code == 201
    assert "PYPL" in tickers_of(response)
    assert "PYPL" in source.get_tickers()


def test_add_duplicate_is_rejected(client):
    response = client.post("/api/watchlist", json={"ticker": "AAPL"})
    assert response.status_code == 409


def test_add_empty_ticker_is_rejected(client):
    assert client.post("/api/watchlist", json={"ticker": "  "}).status_code == 400


def test_remove_ticker_stops_pricing_it(client, source):
    response = client.delete("/api/watchlist/AAPL")
    assert response.status_code == 200
    assert "AAPL" not in tickers_of(response)
    assert "AAPL" not in source.get_tickers()


def test_remove_keeps_pricing_a_held_ticker(client, source):
    client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 2, "side": "buy"}
    )
    response = client.delete("/api/watchlist/AAPL")

    assert "AAPL" not in tickers_of(response)
    assert "AAPL" in source.get_tickers()


def test_remove_unknown_ticker_is_404(client):
    assert client.delete("/api/watchlist/ZZZZ").status_code == 404
