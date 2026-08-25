"""HTTP-level and unit tests for POST /api/chat (CHAT-01, CHAT-04, CHAT-06, TEST-03)."""

from __future__ import annotations

import pytest

from app.llm.client import get_chat_response
from app.llm.persistence import load_recent_chat_messages, save_chat_message
from app.llm.prompt import build_messages, build_portfolio_context
from app.llm.schemas import ChatResponse
from app.market.cache import PriceCache


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
