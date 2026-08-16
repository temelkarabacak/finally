"""Mock-mode switching, prompt assembly and the 30s timeout wiring."""

import time
from unittest.mock import patch

import pytest

from app.db import ChatMessage
from app.llm import client as llm_client

CONTEXT = {"cash_balance": 10000.0, "total_value": 10000.0, "positions": [], "watchlist": []}


def message(role, content):
    return ChatMessage(id="1", user_id="default", role=role, content=content, actions=None,
                       created_at="2026-01-01T00:00:00Z")


@pytest.mark.parametrize("value,expected", [("true", True), ("True", True), ("1", True),
                                            ("yes", True), ("false", False), ("", False)])
def test_mock_enabled(monkeypatch, value, expected):
    monkeypatch.setenv("LLM_MOCK", value)
    assert llm_client.mock_enabled() is expected


def test_mock_enabled_defaults_off(monkeypatch):
    monkeypatch.delenv("LLM_MOCK", raising=False)
    assert llm_client.mock_enabled() is False


async def test_mock_mode_skips_the_network(monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    with patch.object(llm_client, "_completion", side_effect=AssertionError("network called")):
        result = await llm_client.generate_response("buy 10 AAPL", CONTEXT, [])
    assert result.trades[0].ticker == "AAPL"


async def test_real_mode_parses_the_completion(monkeypatch):
    monkeypatch.delenv("LLM_MOCK", raising=False)
    with patch.object(llm_client, "_completion", return_value='{"message": "hi"}'):
        result = await llm_client.generate_response("hello", CONTEXT, [])
    assert result.message == "hi"


async def test_slow_completion_times_out(monkeypatch):
    monkeypatch.delenv("LLM_MOCK", raising=False)
    monkeypatch.setattr(llm_client, "TIMEOUT_SECONDS", 0.05)
    with patch.object(llm_client, "_completion", side_effect=lambda m: time.sleep(1)):
        with pytest.raises(TimeoutError):
            await llm_client.generate_response("hello", CONTEXT, [])


def test_build_messages_ordering():
    messages = llm_client.build_messages(
        "new question", CONTEXT, [message("user", "old"), message("assistant", "reply")]
    )
    assert [m["role"] for m in messages] == ["system", "system", "user", "assistant", "user"]
    assert "FinAlly" in messages[0]["content"]
    assert "cash_balance" in messages[1]["content"]
    assert messages[-1]["content"] == "new question"
