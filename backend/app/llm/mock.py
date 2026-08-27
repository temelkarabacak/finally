"""LLM_MOCK=true deterministic pattern-matcher (decision D-11).

Matching is on lowercased, whitespace-stripped input so the same text always
yields the same object, applied in a fixed rule order: trade and watchlist
rules first (a sentence can carry either or both), falling back to the
commentary rules only when neither matched. A ticker or quantity is only
ever emitted when the input literally names it -- never rounded, padded, or
invented. The 12-scenario reference dataset this matcher must reproduce
lives in tests/llm/fixtures/chat_scenarios.py.
"""

from __future__ import annotations

import re

from .schemas import ChatResponse, TradeAction, WatchlistChange

_ANALYSIS_KEYWORDS = ("portfolio", "analy", "holding", "position")

# "buy 10 shares of aapl" / "sell 5 nvda" -- "shares of" is optional so both
# phrasings resolve to the same (side, quantity, ticker) triple.
_TRADE_RE = re.compile(
    r"\b(buy|sell)\b\s+(\d+(?:\.\d+)?)\s+(?:shares?\s+of\s+)?(?!shares?\b)([a-z]+)\b"
)

# "add pypl to my watchlist" / "remove jpm from my watchlist"
_WATCHLIST_RE = re.compile(
    r"\b(add|remove)\b\s+([a-z]+)\b\s+(?:to|from)\s+(?:my\s+)?watchlist"
)


def _trade_sentence(trade: TradeAction) -> str:
    return f"{trade.side.capitalize()}ing {trade.quantity:g} {trade.ticker}."


def _watchlist_sentence(change: WatchlistChange) -> str:
    verb = "Adding" if change.action == "add" else "Removing"
    preposition = "to" if change.action == "add" else "from"
    return f"{verb} {change.ticker} {preposition} your watchlist."


def mock_chat_response(user_text: str) -> ChatResponse:
    """Deterministic offline stand-in for get_chat_response()."""
    normalized = user_text.strip().lower()

    trades = [
        TradeAction(ticker=ticker, side=side, quantity=float(quantity))
        for side, quantity, ticker in _TRADE_RE.findall(normalized)
    ]
    watchlist_changes = [
        WatchlistChange(ticker=ticker, action=action)
        for action, ticker in _WATCHLIST_RE.findall(normalized)
    ]

    if trades or watchlist_changes:
        sentences = [_trade_sentence(trade) for trade in trades]
        sentences += [_watchlist_sentence(change) for change in watchlist_changes]
        message = " ".join(sentences)
    elif any(keyword in normalized for keyword in _ANALYSIS_KEYWORDS):
        message = (
            "Your portfolio is grounded in live cash and position data — "
            "ask me to buy, sell, or adjust the watchlist and I'll act on it."
        )
    else:
        message = "I'm ready to help — ask about your portfolio or tell me what to trade."

    return ChatResponse(message=message, trades=trades, watchlist_changes=watchlist_changes)
