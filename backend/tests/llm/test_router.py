"""HTTP-level and unit tests for POST /api/chat (CHAT-01, CHAT-04, CHAT-06, TEST-03)."""

from __future__ import annotations

import pytest

from app.llm import client as client_module
from app.llm.client import get_chat_response
from app.llm.persistence import load_recent_chat_messages, save_chat_message
from app.llm.prompt import build_messages, build_portfolio_context
from app.llm.router import GENERIC_RETRY_MESSAGE
from app.llm.schemas import ChatResponse
from app.market.cache import PriceCache


@pytest.fixture
def live_chat_client(initialized_db):
    """Like chat_client, but mock=False -- routes through the real
    get_chat_response()/litellm.completion() call chain so tests can patch
    litellm.completion directly to simulate timeout/malformed-output."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.llm import create_chat_router
    from app.market.seed_prices import SEED_PRICES
    from tests.portfolio.test_trades import FakeMarketSource

    conn = initialized_db
    source = FakeMarketSource()
    cache = PriceCache()
    for ticker, price in SEED_PRICES.items():
        cache.update(ticker, price)

    app = FastAPI()
    app.include_router(create_chat_router(lambda: conn, source, cache, mock=False))

    with TestClient(app) as client:
        yield client, conn


class TestPostChatValidation:
    def test_empty_message_returns_422_and_persists_nothing(self, chat_client):
        client, conn, _source, _cache = chat_client

        response = client.post("/api/chat", json={"message": ""})

        assert response.status_code == 422
        count = conn.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0]
        assert count == 0

    def test_missing_message_returns_422_and_persists_nothing(self, chat_client):
        client, conn, _source, _cache = chat_client

        response = client.post("/api/chat", json={})

        assert response.status_code == 422
        count = conn.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0]
        assert count == 0


class TestPostChatSuccess:
    def test_happy_path_returns_message_and_empty_actions(self, chat_client):
        client, _conn, _source, _cache = chat_client

        response = client.post("/api/chat", json={"message": "Analyze my portfolio"})

        assert response.status_code == 200
        body = response.json()
        assert set(body.keys()) == {"message", "actions"}
        assert set(body["actions"].keys()) == {"trades", "watchlist_changes"}
        assert isinstance(body["message"], str) and body["message"]
        assert body["actions"] == {"trades": [], "watchlist_changes": []}

    def test_successful_turn_persists_user_then_assistant_row(self, chat_client):
        client, conn, _source, _cache = chat_client

        response = client.post("/api/chat", json={"message": "Analyze my portfolio"})

        assert response.status_code == 200
        roles = [
            row[0]
            for row in conn.execute("SELECT role FROM chat_messages ORDER BY created_at").fetchall()
        ]
        assert roles == ["user", "assistant"]

    def test_non_ascii_message_round_trips_exactly(self, chat_client):
        client, conn, _source, _cache = chat_client
        text = "Analyze é 🚀 中"

        response = client.post("/api/chat", json={"message": text})

        assert response.status_code == 200
        row = conn.execute(
            "SELECT content FROM chat_messages WHERE role = 'user'"
        ).fetchone()
        assert row[0] == text


class TestBuildMessagesGrounding:
    """EV-4: the prompt sent to the model carries this turn's live figures."""

    def test_build_messages_contains_live_cash_and_positions(self, initialized_db):
        conn = initialized_db
        cache = PriceCache()
        cache.update("AAPL", 190.0)

        conn.execute(
            "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
            "VALUES ('pos1', 'default', 'AAPL', 10, 150.0, '2026-01-01T00:00:00Z')"
        )

        portfolio_ctx = build_portfolio_context(conn, cache)
        history = [{"role": "user", "content": "prior turn"}]
        messages = build_messages("SYSTEM", portfolio_ctx, history, "Analyze my portfolio")

        serialized = str(messages)
        assert "10000.0" in serialized or "10000" in serialized
        assert "AAPL" in serialized
        assert "400.0" in serialized or "400" in serialized  # unrealized P&L: (190-150)*10


class TestLoadRecentChatMessages:
    def test_returns_at_most_limit_rows_oldest_first_role_content_only(self, initialized_db):
        conn = initialized_db
        for i in range(25):
            save_chat_message(conn, role="user", content=f"msg {i}")

        rows = load_recent_chat_messages(conn, limit=20)

        assert len(rows) == 20
        assert all(set(row.keys()) == {"role", "content"} for row in rows)
        assert rows[-1]["content"] == "msg 24"


class TestChatResponseDefaults:
    def test_omitted_lists_parse_to_empty_never_null(self):
        parsed = ChatResponse.model_validate_json('{"message":"hi"}')

        assert parsed.trades == []
        assert parsed.watchlist_changes == []


class TestHermeticityGuard:
    async def test_live_path_hits_blocked_litellm_completion(self):
        with pytest.raises(RuntimeError, match="litellm.completion"):
            await get_chat_response([{"role": "user", "content": "hi"}])


class TestGetChatHistory:
    """GET /api/chat/history: the transcript reader for the drawer (CHAT-04/05)."""

    def test_empty_database_returns_200_and_empty_list(self, chat_client):
        client, _conn, _source, _cache = chat_client

        response = client.get("/api/chat/history")

        assert response.status_code == 200
        assert response.json() == []

    def test_two_turns_returns_four_entries_oldest_first_with_actions(self, chat_client):
        client, _conn, _source, _cache = chat_client

        client.post("/api/chat", json={"message": "Analyze my portfolio"})
        client.post("/api/chat", json={"message": "Buy 10 shares of AAPL"})

        response = client.get("/api/chat/history")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 4
        assert [entry["role"] for entry in body] == ["user", "assistant", "user", "assistant"]
        for entry in body:
            assert set(entry.keys()) == {"role", "content", "actions"}
        assert body[0]["actions"] is None  # user row
        assert body[1]["actions"] == {"trades": [], "watchlist_changes": []}  # assistant row

    def test_limit_1_returns_single_most_recent_message(self, chat_client):
        client, _conn, _source, _cache = chat_client

        client.post("/api/chat", json={"message": "Analyze my portfolio"})

        response = client.get("/api/chat/history", params={"limit": 1})

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["role"] == "assistant"

    @pytest.mark.parametrize("limit", [0, -1, 500])
    def test_out_of_range_limit_returns_422(self, chat_client, limit):
        client, _conn, _source, _cache = chat_client

        response = client.get("/api/chat/history", params={"limit": limit})

        assert response.status_code == 422


class TestChatDegradation:
    """HTTP-level TEST-02/CHAT-05: timeout and malformed output both degrade
    to the identical shared GENERIC_RETRY_MESSAGE body, executing nothing
    and persisting no assistant row."""

    def test_timeout_returns_200_generic_message_and_empty_actions(
        self, live_chat_client, monkeypatch
    ):
        from openai import APITimeoutError

        def _raise(*args, **kwargs):
            raise APITimeoutError(request=None)

        monkeypatch.setattr(client_module.litellm, "completion", _raise)
        client, _conn = live_chat_client

        response = client.post("/api/chat", json={"message": "Analyze my portfolio"})

        assert response.status_code == 200
        body = response.json()
        assert body["message"] == GENERIC_RETRY_MESSAGE
        assert body["actions"] == {"trades": [], "watchlist_changes": []}

    def test_malformed_output_returns_identical_body_to_timeout(
        self, live_chat_client, monkeypatch
    ):
        def _prose_completion(*args, **kwargs):
            class _Message:
                content = "Sure, here's my analysis in plain prose, not JSON."

            class _Choice:
                message = _Message()

            class _Response:
                choices = [_Choice()]

            return _Response()

        monkeypatch.setattr(client_module.litellm, "completion", _prose_completion)
        client, _conn = live_chat_client

        response = client.post("/api/chat", json={"message": "Analyze my portfolio"})

        assert response.status_code == 200
        body = response.json()
        assert body["message"] == GENERIC_RETRY_MESSAGE
        assert body["actions"] == {"trades": [], "watchlist_changes": []}

    def test_resending_after_timeout_produces_two_user_rows_zero_assistant_rows(
        self, live_chat_client, monkeypatch
    ):
        from openai import APITimeoutError

        def _raise(*args, **kwargs):
            raise APITimeoutError(request=None)

        monkeypatch.setattr(client_module.litellm, "completion", _raise)
        client, conn = live_chat_client

        client.post("/api/chat", json={"message": "Buy 10 AAPL"})
        client.post("/api/chat", json={"message": "Buy 10 AAPL"})

        roles = [
            row[0]
            for row in conn.execute("SELECT role FROM chat_messages ORDER BY created_at").fetchall()
        ]
        assert roles == ["user", "user"]


class TestChatHistoryDeduplication:
    """CR-01 regression: the message list sent to the model must never carry
    the current turn's user_text twice -- once as the just-persisted last
    history row, once as build_messages' explicit final turn."""

    def test_second_turn_does_not_duplicate_current_message_in_llm_context(
        self, live_chat_client, monkeypatch
    ):
        captured_messages: list[list[dict]] = []

        def _capture_completion(*args, **kwargs):
            captured_messages.append(kwargs["messages"])

            class _Message:
                content = '{"message": "ok", "trades": [], "watchlist_changes": []}'

            class _Choice:
                message = _Message()

            class _Response:
                choices = [_Choice()]

            return _Response()

        monkeypatch.setattr(client_module.litellm, "completion", _capture_completion)
        client, _conn = live_chat_client

        client.post("/api/chat", json={"message": "First turn message"})
        client.post("/api/chat", json={"message": "Second turn message"})

        assert len(captured_messages) == 2
        second_turn_messages = captured_messages[1]
        user_texts = [m["content"] for m in second_turn_messages if m["role"] == "user"]
        occurrences = user_texts.count("Second turn message")
        assert occurrences == 1, (
            f"'Second turn message' appeared {occurrences} times in the model context "
            f"(expected exactly 1): {user_texts}"
        )
