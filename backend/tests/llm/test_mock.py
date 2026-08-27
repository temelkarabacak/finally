"""Tests for the LLM_MOCK deterministic pattern-matcher (decision D-11).

Parametrized over the ten text-driven scenarios in CHAT_SCENARIOS; scenarios
11-12 carry no user_text and are excluded (they are raw-payload / timeout
fixtures for a later plan's router tests, not matcher inputs).
"""

from __future__ import annotations

import pytest

from app.llm.mock import mock_chat_response
from tests.llm.fixtures.chat_scenarios import CHAT_SCENARIOS

_TEXT_DRIVEN_SCENARIOS = [s for s in CHAT_SCENARIOS if s["user_text"] is not None]


@pytest.mark.parametrize(
    "scenario",
    _TEXT_DRIVEN_SCENARIOS,
    ids=[s["name"] for s in _TEXT_DRIVEN_SCENARIOS],
)
def test_mock_chat_response_matches_scenario(scenario):
    response = mock_chat_response(scenario["user_text"])
    expected = scenario["expected"]

    assert response.message == expected["message"]
    assert [trade.model_dump() for trade in response.trades] == expected["trades"]
    assert [
        change.model_dump() for change in response.watchlist_changes
    ] == expected["watchlist_changes"]


def test_fractional_quantity_preserved_not_rounded():
    response = mock_chat_response("Buy 2.5 shares of GOOGL")

    assert len(response.trades) == 1
    assert response.trades[0].quantity == 2.5


def test_advice_question_returns_no_actions():
    response = mock_chat_response("What should I buy?")

    assert response.trades == []
    assert response.watchlist_changes == []


def test_mock_chat_response_is_deterministic():
    text = "Buy 10 shares of AAPL"

    first = mock_chat_response(text)
    second = mock_chat_response(text)

    assert first == second
