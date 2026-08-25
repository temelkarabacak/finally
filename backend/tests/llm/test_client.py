"""get_chat_response() degradation coverage: timeout and malformed structured
output both return None and log at warning, never error/critical (TEST-02,
EV-2, EV-3, EV-6).

Patches the module attribute app.llm.client.completion (as imported by
client.py), never the litellm.completion attribute the autouse
block_real_llm_calls hermeticity guard owns in conftest.py -- so that guard
stays armed for every other test in this suite.
"""

from __future__ import annotations

import logging

import pytest
from openai import APITimeoutError

from app.llm import client as client_module

MALFORMED_PAYLOADS = [
    pytest.param("Sure, I'll analyze your portfolio now.", id="free_form_prose"),
    pytest.param('{"message": "Buying 10 AAPL", "trad', id="truncated_json"),
    pytest.param('{"trades": []}', id="missing_message_field"),
    pytest.param(
        '{"message": "hi", "trades": [{"ticker": "AAPL", "side": "buy", "quantity": "ten"}]}',
        id="wrong_typed_quantity",
    ),
]


def _make_timeout_completion():
    def _raise(*args, **kwargs):
        raise APITimeoutError(request=None)

    return _raise


def _make_content_completion(content: str):
    class _Message:
        def __init__(self, content: str) -> None:
            self.content = content

    class _Choice:
        def __init__(self, content: str) -> None:
            self.message = _Message(content)

    class _Response:
        def __init__(self, content: str) -> None:
            self.choices = [_Choice(content)]

    def _completion(*args, **kwargs):
        return _Response(content)

    return _completion


class TestTimeoutDegradation:
    async def test_timeout_returns_none(self, monkeypatch):
        monkeypatch.setattr(client_module.litellm, "completion", _make_timeout_completion())

        result = await client_module.get_chat_response([{"role": "user", "content": "hi"}])

        assert result is None

    async def test_timeout_logs_warning_not_error(self, monkeypatch, caplog):
        monkeypatch.setattr(client_module.litellm, "completion", _make_timeout_completion())

        with caplog.at_level(logging.WARNING, logger="app.llm.client"):
            await client_module.get_chat_response([{"role": "user", "content": "hi"}])

        assert any(record.levelno == logging.WARNING for record in caplog.records)
        assert not any(record.levelno >= logging.ERROR for record in caplog.records)


class TestMalformedOutputDegradation:
    @pytest.mark.parametrize("payload", MALFORMED_PAYLOADS)
    async def test_malformed_payload_returns_none(self, monkeypatch, payload):
        monkeypatch.setattr(client_module.litellm, "completion", _make_content_completion(payload))

        result = await client_module.get_chat_response([{"role": "user", "content": "hi"}])

        assert result is None

    @pytest.mark.parametrize("payload", MALFORMED_PAYLOADS)
    async def test_malformed_payload_logs_warning_not_error(self, monkeypatch, caplog, payload):
        monkeypatch.setattr(client_module.litellm, "completion", _make_content_completion(payload))

        with caplog.at_level(logging.WARNING, logger="app.llm.client"):
            await client_module.get_chat_response([{"role": "user", "content": "hi"}])

        assert any(record.levelno == logging.WARNING for record in caplog.records)
        assert not any(record.levelno >= logging.ERROR for record in caplog.records)
