"""Parsing of the model's structured output, including malformed replies."""

import json

import pytest

from app.llm.schema import LLMResponse, parse_llm_response


def test_message_only():
    result = parse_llm_response('{"message": "Hello"}')
    assert result.message == "Hello"
    assert result.trades == []
    assert result.watchlist_changes == []


def test_full_schema():
    raw = json.dumps(
        {
            "message": "Buying AAPL and watching PYPL",
            "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}],
            "watchlist_changes": [{"ticker": "PYPL", "action": "add"}],
        }
    )
    result = parse_llm_response(raw)
    assert result.trades[0].ticker == "AAPL"
    assert result.trades[0].side == "buy"
    assert result.trades[0].quantity == 10
    assert result.watchlist_changes[0].action == "add"


def test_trades_without_watchlist_changes():
    raw = '{"message": "ok", "trades": [{"ticker": "TSLA", "side": "sell", "quantity": 2.5}]}'
    result = parse_llm_response(raw)
    assert result.trades[0].quantity == 2.5
    assert result.watchlist_changes == []


def test_watchlist_changes_without_trades():
    raw = '{"message": "ok", "watchlist_changes": [{"ticker": "NFLX", "action": "remove"}]}'
    result = parse_llm_response(raw)
    assert result.trades == []
    assert result.watchlist_changes[0].action == "remove"


def test_explicit_nulls_are_tolerated():
    result = parse_llm_response('{"message": "ok", "trades": null, "watchlist_changes": null}')
    assert result.trades == []
    assert result.watchlist_changes == []


def test_code_fence_is_stripped():
    result = parse_llm_response('```json\n{"message": "fenced"}\n```')
    assert result.message == "fenced"


def test_unknown_keys_ignored():
    result = parse_llm_response('{"message": "ok", "confidence": 0.9}')
    assert result.message == "ok"


def test_non_json_becomes_plain_message():
    result = parse_llm_response("Your portfolio looks concentrated in tech.")
    assert result.message == "Your portfolio looks concentrated in tech."
    assert result.trades == []


def test_json_array_becomes_plain_message():
    result = parse_llm_response('["not", "an", "object"]')
    assert result.message == '["not", "an", "object"]'


def test_invalid_trade_entries_are_dropped():
    raw = json.dumps(
        {
            "message": "partial",
            "trades": [
                {"ticker": "AAPL", "side": "buy", "quantity": 1},
                {"ticker": "GOOGL"},
                {"ticker": "MSFT", "side": "hold", "quantity": 1},
                "garbage",
            ],
        }
    )
    result = parse_llm_response(raw)
    assert [t.ticker for t in result.trades] == ["AAPL"]


def test_invalid_watchlist_entries_are_dropped():
    raw = '{"message": "x", "watchlist_changes": [{"ticker": "A", "action": "flip"}]}'
    assert parse_llm_response(raw).watchlist_changes == []


def test_trades_not_a_list_is_dropped():
    assert parse_llm_response('{"message": "x", "trades": "buy AAPL"}').trades == []


@pytest.mark.parametrize("raw", ["", "   ", None])
def test_empty_response_raises(raw):
    with pytest.raises(ValueError):
        parse_llm_response(raw)


@pytest.mark.parametrize("raw", ['{"trades": []}', '{"message": ""}', '{"message": 42}'])
def test_missing_message_raises(raw):
    with pytest.raises(ValueError):
        parse_llm_response(raw)


def test_schema_defaults():
    assert LLMResponse(message="hi").trades == []
