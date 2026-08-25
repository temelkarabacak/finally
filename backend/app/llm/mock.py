"""LLM_MOCK=true deterministic pattern-matcher (decision D-11).

This task installs the commentary rules only: text matching
portfolio/analysis/holding/position keywords returns a data-driven
analysis sentence, everything else returns a neutral fallback -- both
with empty trades/watchlist_changes lists. Trade and watchlist rules, and
the shared 12-scenario table they are checked against, are added in plan
03-02. Matching is on lowercased, whitespace-stripped input so the same
text always yields the same object.
"""

from __future__ import annotations

from .schemas import ChatResponse

_ANALYSIS_KEYWORDS = ("portfolio", "analy", "holding", "position")


def mock_chat_response(user_text: str) -> ChatResponse:
    """Deterministic offline stand-in for get_chat_response()."""
    normalized = user_text.strip().lower()

    if any(keyword in normalized for keyword in _ANALYSIS_KEYWORDS):
        message = (
            "Your portfolio is grounded in live cash and position data — "
            "ask me to buy, sell, or adjust the watchlist and I'll act on it."
        )
    else:
        message = "I'm ready to help — ask about your portfolio or tell me what to trade."

    return ChatResponse(message=message, trades=[], watchlist_changes=[])
