"""The POST /api/chat flow: context, persistence ordering, execution and failure paths."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.db import get_cash_balance, get_position, list_recent_chat_messages, list_snapshots
from app.llm.router import RETRY_MESSAGE
from app.llm.schema import LLMResponse, TradeInstruction, WatchlistChange


@pytest.fixture
def live_client(app, monkeypatch):
    """Client with mock mode OFF so app.llm.router.generate_response can be patched."""
    monkeypatch.delenv("LLM_MOCK", raising=False)
    with TestClient(app) as test_client:
        yield test_client


def send(client, message):
    response = client.post("/api/chat", json={"message": message})
    assert response.status_code == 200
    return response.json()


# --- mock mode ------------------------------------------------------------


def test_greeting_persists_both_messages(client, conn):
    body = send(client, "hello")

    assert body["trades"] == []
    messages = list_recent_chat_messages(conn)
    assert [(m.role, m.content) for m in messages] == [
        ("user", "hello"),
        ("assistant", body["message"]),
    ]
    assert messages[1].actions is None


def test_mock_mode_is_deterministic(client):
    assert send(client, "hello")["message"] == send(client, "hello")["message"]


def test_buy_executes_and_records_action(client, conn):
    body = send(client, "buy 10 AAPL")

    assert body["trades"] == [
        {
            "ticker": "AAPL",
            "side": "buy",
            "quantity": 10.0,
            "price": 190.0,
            "status": "executed",
            "error": None,
        }
    ]
    assert get_position(conn, "AAPL").quantity == 10.0
    assert get_cash_balance(conn) == 8100.0

    assistant = list_recent_chat_messages(conn)[-1]
    assert assistant.actions["trades"][0]["status"] == "executed"


def test_executed_trade_records_a_snapshot(client, conn):
    send(client, "buy 10 AAPL")
    assert [s.total_value for s in list_snapshots(conn)] == [10000.0]


def test_rejected_trade_records_no_snapshot(client, conn):
    send(client, "buy 1000 AAPL")
    assert list_snapshots(conn) == []


def test_watchlist_change_applied(client, conn):
    body = send(client, "add PYPL to the watchlist")
    assert body["watchlist_changes"][0]["status"] == "executed"


def test_history_endpoint_returns_conversation(client):
    send(client, "hello")
    history = client.get("/api/chat/history").json()
    assert [m["role"] for m in history] == ["user", "assistant"]


def test_empty_message_rejected(client):
    assert client.post("/api/chat", json={"message": ""}).status_code == 422


# --- action failures ------------------------------------------------------


def test_insufficient_cash_reported_not_crashed(live_client, conn):
    response = LLMResponse(
        message="Buying AAPL.",
        trades=[TradeInstruction(ticker="AAPL", side="buy", quantity=1000)],
    )
    with patch("app.llm.router.generate_response", return_value=response):
        body = send(live_client, "buy 1000 AAPL")

    assert body["trades"][0]["status"] == "rejected"
    assert "Insufficient cash" in body["trades"][0]["error"]
    assert "Not completed" in body["message"]
    assert get_cash_balance(conn) == 10000.0


def test_insufficient_shares_reported_not_crashed(live_client, conn):
    response = LLMResponse(
        message="Selling AAPL.",
        trades=[TradeInstruction(ticker="AAPL", side="sell", quantity=5)],
    )
    with patch("app.llm.router.generate_response", return_value=response):
        body = send(live_client, "sell 5 AAPL")

    assert "Insufficient shares" in body["trades"][0]["error"]


def test_mixed_success_and_failure(live_client, conn):
    response = LLMResponse(
        message="Rebalancing.",
        trades=[
            TradeInstruction(ticker="AAPL", side="buy", quantity=1),
            TradeInstruction(ticker="ZZZZ", side="buy", quantity=1),
        ],
        watchlist_changes=[WatchlistChange(ticker="PYPL", action="add")],
    )
    with patch("app.llm.router.generate_response", return_value=response):
        body = send(live_client, "rebalance")

    assert [t["status"] for t in body["trades"]] == ["executed", "rejected"]
    assert body["watchlist_changes"][0]["status"] == "executed"
    assert get_position(conn, "AAPL").quantity == 1.0


# --- failure paths --------------------------------------------------------


def test_timeout_keeps_user_message_and_persists_nothing_else(live_client, conn):
    with patch("app.llm.router.generate_response", side_effect=TimeoutError):
        body = send(live_client, "analyse my portfolio")

    assert body == {"message": RETRY_MESSAGE, "trades": [], "watchlist_changes": []}
    messages = list_recent_chat_messages(conn)
    assert [(m.role, m.content) for m in messages] == [("user", "analyse my portfolio")]


def test_llm_error_keeps_user_message_and_persists_nothing_else(live_client, conn):
    with patch("app.llm.router.generate_response", side_effect=RuntimeError("boom")):
        body = send(live_client, "hi")

    assert body["message"] == RETRY_MESSAGE
    assert [m.role for m in list_recent_chat_messages(conn)] == ["user"]


def test_user_message_persisted_before_the_llm_call(live_client, conn):
    seen = []

    def capture(*args, **kwargs):
        seen.append([(m.role, m.content) for m in list_recent_chat_messages(conn)])
        return LLMResponse(message="ok")

    with patch("app.llm.router.generate_response", side_effect=capture):
        send(live_client, "first question")

    assert seen == [[("user", "first question")]]


def test_history_excludes_the_new_message(live_client, conn):
    seen = []

    def capture(user_message, context, history):
        seen.append([(m.role, m.content) for m in history])
        return LLMResponse(message="ok")

    with patch("app.llm.router.generate_response", side_effect=capture):
        send(live_client, "one")
        send(live_client, "two")

    assert seen[0] == []
    assert seen[1] == [("user", "one"), ("assistant", "ok")]


def test_portfolio_context_reaches_the_llm(live_client, conn, price_cache):
    seen = {}

    def capture(user_message, context, history):
        seen.update(context)
        return LLMResponse(message="ok")

    with patch("app.llm.router.generate_response", side_effect=capture):
        send(live_client, "status")

    assert seen["cash_balance"] == 10000.0
    assert seen["total_value"] == 10000.0
    assert {w["ticker"] for w in seen["watchlist"]} >= {"AAPL", "GOOGL"}
    assert seen["positions"] == []
