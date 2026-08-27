"""The 12-scenario reference dataset behind decision D-11 (03-CONTEXT.md).

One artifact, three jobs (03-AI-SPEC.md Section 5): the LLM_MOCK pattern-rule
table CHAT-06 requires, the parametrization source for test_mock.py, and the
eval reference set for EV-1/EV-2/EV-5. Scenarios are transcribed verbatim in
intent from 03-AI-SPEC.md's Reference Dataset table.

`expected` is a plain dict shaped like ChatResponse.model_dump() -- not a
ChatResponse instance -- so this module has no import cycle with app.llm.mock.
Scenarios 11 and 12 carry no `user_text`: they are raw-payload / failure-mode
fixtures consumed by plan 03-04's malformed-output/timeout router tests, not
inputs to the mock matcher. Their `expected` is None and `expected_outcome`
is the outcome-state label from the spec, verbatim: "generic retry message,
0 trades, 0 assistant rows".
"""

from __future__ import annotations

CHAT_SCENARIOS: list[dict] = [
    {
        "id": 1,
        "name": "buy_sufficient_cash",
        "user_text": "Buy 10 shares of AAPL",
        "expected": {
            "message": "Buying 10 AAPL.",
            "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10.0}],
            "watchlist_changes": [],
        },
        "expected_outcome": "one filled trade: buy 10 AAPL (sufficient cash)",
    },
    {
        "id": 2,
        "name": "sell_position_held",
        "user_text": "Sell 5 NVDA",
        "expected": {
            "message": "Selling 5 NVDA.",
            "trades": [{"ticker": "NVDA", "side": "sell", "quantity": 5.0}],
            "watchlist_changes": [],
        },
        "expected_outcome": "one filled trade: sell 5 NVDA (position held)",
    },
    {
        "id": 3,
        "name": "buy_insufficient_cash",
        "user_text": "Buy 10000 shares of TSLA",
        "expected": {
            "message": "Buying 10000 TSLA.",
            "trades": [{"ticker": "TSLA", "side": "buy", "quantity": 10000.0}],
            "watchlist_changes": [],
        },
        "expected_outcome": "one rejected trade: buy 10000 TSLA (insufficient cash)",
    },
    {
        "id": 4,
        "name": "sell_exceeds_holding",
        "user_text": "Sell 50 META",
        "expected": {
            "message": "Selling 50 META.",
            "trades": [{"ticker": "META", "side": "sell", "quantity": 50.0}],
            "watchlist_changes": [],
        },
        "expected_outcome": "one rejected trade: sell 50 META (holds fewer or none)",
    },
    {
        "id": 5,
        "name": "watchlist_add",
        "user_text": "Add PYPL to my watchlist",
        "expected": {
            "message": "Adding PYPL to your watchlist.",
            "trades": [],
            "watchlist_changes": [{"ticker": "PYPL", "action": "add"}],
        },
        "expected_outcome": "one watchlist add: PYPL",
    },
    {
        "id": 6,
        "name": "watchlist_remove",
        "user_text": "Remove JPM from my watchlist",
        "expected": {
            "message": "Removing JPM from your watchlist.",
            "trades": [],
            "watchlist_changes": [{"ticker": "JPM", "action": "remove"}],
        },
        "expected_outcome": "one watchlist remove: JPM",
    },
    {
        "id": 7,
        "name": "analysis_commentary_only",
        "user_text": "Analyze my portfolio",
        "expected": {
            "message": (
                "Your portfolio is grounded in live cash and position data — "
                "ask me to buy, sell, or adjust the watchlist and I'll act on it."
            ),
            "trades": [],
            "watchlist_changes": [],
        },
        "expected_outcome": "commentary only, both action lists empty",
    },
    {
        "id": 8,
        "name": "advice_no_auto_execution",
        "user_text": "What should I buy?",
        "expected": {
            "message": "I'm ready to help — ask about your portfolio or tell me what to trade.",
            "trades": [],
            "watchlist_changes": [],
        },
        "expected_outcome": "advice only, both action lists empty, no action invented from a question",
    },
    {
        "id": 9,
        "name": "buy_fractional_quantity",
        "user_text": "Buy 2.5 shares of GOOGL",
        "expected": {
            "message": "Buying 2.5 GOOGL.",
            "trades": [{"ticker": "GOOGL", "side": "buy", "quantity": 2.5}],
            "watchlist_changes": [],
        },
        "expected_outcome": "one filled fractional trade: buy 2.5 GOOGL",
    },
    {
        "id": 10,
        "name": "buy_plus_watchlist_add",
        "user_text": "Buy 10 shares of AAPL and add PYPL to my watchlist",
        "expected": {
            "message": "Buying 10 AAPL. Adding PYPL to your watchlist.",
            "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10.0}],
            "watchlist_changes": [{"ticker": "PYPL", "action": "add"}],
        },
        "expected_outcome": "one filled trade and one watchlist add, in a single turn",
    },
    {
        "id": 11,
        "name": "malformed_structured_output",
        "user_text": None,
        "expected": None,
        "expected_outcome": "generic retry message, 0 trades, 0 assistant rows",
    },
    {
        "id": 12,
        "name": "llm_call_timeout",
        "user_text": None,
        "expected": None,
        "expected_outcome": "generic retry message, 0 trades, 0 assistant rows",
    },
]
