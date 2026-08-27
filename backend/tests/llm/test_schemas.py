"""ChatResponse structured-output validation gate (TEST-02, EV-2).

gpt-oss-120b has a documented tendency to ignore `response_format` and
return prose instead of JSON; these are the malformed-payload classes that
tendency stands in for, plus the default-empty-list and field-level
TradeAction validation cases.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.llm.schemas import ChatResponse, TradeAction

MALFORMED_PAYLOADS = [
    pytest.param("Sure, I'll analyze your portfolio now.", id="free_form_prose"),
    pytest.param('{"message": "Buying 10 AAPL", "trad', id="truncated_json"),
    pytest.param('{"trades": []}', id="missing_message_field"),
    pytest.param(
        '{"message": "hi", "trades": [{"ticker": "AAPL", "side": "buy", "quantity": "ten"}]}',
        id="wrong_typed_quantity",
    ),
]


class TestChatResponseMalformedPayloads:
    @pytest.mark.parametrize("payload", MALFORMED_PAYLOADS)
    def test_malformed_payload_raises(self, payload):
        with pytest.raises((ValidationError, json.JSONDecodeError)):
            ChatResponse.model_validate_json(payload)


class TestChatResponseDefaults:
    def test_omitted_action_lists_default_to_empty_never_null(self):
        parsed = ChatResponse.model_validate_json('{"message": "hi"}')

        assert parsed.trades == []
        assert parsed.watchlist_changes == []


class TestTradeActionValidation:
    def test_rejects_ticker_containing_a_digit(self):
        with pytest.raises(ValidationError):
            TradeAction(ticker="AAP1", side="buy", quantity=1)

    def test_rejects_ticker_containing_a_space(self):
        with pytest.raises(ValidationError):
            TradeAction(ticker="AA PL", side="buy", quantity=1)

    def test_rejects_zero_quantity(self):
        with pytest.raises(ValidationError):
            TradeAction(ticker="AAPL", side="buy", quantity=0)

    def test_rejects_negative_quantity(self):
        with pytest.raises(ValidationError):
            TradeAction(ticker="AAPL", side="buy", quantity=-5)
