"""Persistence-layer tests: the two-transaction write ordering and the
20-row model-context window boundary (CHAT-04/CHAT-05).
"""

from __future__ import annotations

from app.llm.persistence import load_chat_history, load_recent_chat_messages, save_chat_message


class TestLoadRecentChatMessagesWindow:
    """The model-context window is counted in rows, never characters."""

    def test_19_rows_returns_19(self, initialized_db):
        conn = initialized_db
        for i in range(19):
            save_chat_message(conn, role="user", content=f"msg {i}")

        rows = load_recent_chat_messages(conn, limit=20)

        assert len(rows) == 19
        assert rows[0]["content"] == "msg 0"
        assert rows[-1]["content"] == "msg 18"

    def test_20_rows_returns_20(self, initialized_db):
        conn = initialized_db
        for i in range(20):
            save_chat_message(conn, role="user", content=f"msg {i}")

        rows = load_recent_chat_messages(conn, limit=20)

        assert len(rows) == 20
        assert rows[0]["content"] == "msg 0"
        assert rows[-1]["content"] == "msg 19"

    def test_21_rows_returns_most_recent_20(self, initialized_db):
        conn = initialized_db
        for i in range(21):
            save_chat_message(conn, role="user", content=f"msg {i}")

        rows = load_recent_chat_messages(conn, limit=20)

        assert len(rows) == 20
        assert rows[0]["content"] == "msg 1"  # oldest row of the most-recent-20
        assert rows[-1]["content"] == "msg 20"

    def test_returned_dict_keys_are_exactly_role_and_content(self, initialized_db):
        conn = initialized_db
        save_chat_message(conn, role="user", content="hi", actions=None)
        save_chat_message(
            conn,
            role="assistant",
            content="hello",
            actions={"trades": [], "watchlist_changes": []},
        )

        rows = load_recent_chat_messages(conn, limit=20)

        assert all(set(row.keys()) == {"role", "content"} for row in rows)


class TestSaveChatMessageOrdering:
    def test_user_row_created_at_or_before_assistant_row(self, initialized_db):
        conn = initialized_db

        save_chat_message(conn, role="user", content="hello")
        save_chat_message(
            conn,
            role="assistant",
            content="hi there",
            actions={"trades": [], "watchlist_changes": []},
        )

        rows = conn.execute("SELECT role, created_at FROM chat_messages").fetchall()
        user_ts = next(ts for role, ts in rows if role == "user")
        assistant_ts = next(ts for role, ts in rows if role == "assistant")
        assert user_ts <= assistant_ts


class TestNoneLlmResultLeavesOnlyUserRow:
    """A turn whose LLM call returns None leaves exactly one user row and
    adds no trades row (CHAT-05)."""

    async def test_none_result_persists_one_user_row_and_zero_trades(
        self, initialized_db, monkeypatch
    ):
        from app.llm import router as router_module
        from app.market.cache import PriceCache
        from app.market.seed_prices import SEED_PRICES
        from tests.portfolio.test_trades import FakeMarketSource

        conn = initialized_db
        cache = PriceCache()
        for ticker, price in SEED_PRICES.items():
            cache.update(ticker, price)
        source = FakeMarketSource()

        async def _fake_get_chat_response(messages):
            return None

        monkeypatch.setattr(router_module, "get_chat_response", _fake_get_chat_response)

        parsed, actions = await router_module.handle_chat_message(
            conn, source, cache, "Buy 10 AAPL", mock=False
        )

        assert parsed is None
        assert actions is None

        role_rows = conn.execute("SELECT role FROM chat_messages").fetchall()
        assert [r[0] for r in role_rows] == ["user"]

        trades_count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        assert trades_count == 0


class TestLoadChatHistory:
    """load_chat_history() is the transcript reader for the UI -- distinct
    from load_recent_chat_messages(), the model-context reader, which never
    replays the `actions` column."""

    def test_empty_database_returns_empty_list(self, initialized_db):
        conn = initialized_db

        rows = load_chat_history(conn)

        assert rows == []

    def test_returns_role_content_actions_oldest_first(self, initialized_db):
        conn = initialized_db
        save_chat_message(conn, role="user", content="hi")
        save_chat_message(
            conn,
            role="assistant",
            content="hello",
            actions={"trades": [], "watchlist_changes": []},
        )

        rows = load_chat_history(conn)

        assert len(rows) == 2
        assert rows[0]["role"] == "user"
        assert rows[0]["content"] == "hi"
        assert rows[0]["actions"] is None
        assert rows[1]["role"] == "assistant"
        assert rows[1]["actions"] == {"trades": [], "watchlist_changes": []}

    def test_limit_returns_single_most_recent_message(self, initialized_db):
        conn = initialized_db
        save_chat_message(conn, role="user", content="first")
        save_chat_message(conn, role="user", content="second")

        rows = load_chat_history(conn, limit=1)

        assert len(rows) == 1
        assert rows[0]["content"] == "second"
