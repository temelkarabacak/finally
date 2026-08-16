"""Deterministic stand-in for the real LLM, enabled with LLM_MOCK=true.

No network, no API key, same structured output shape as the real model. The rules
below are matched independently against the user's message, so one message can both
trade and edit the watchlist. Tickers must be written in UPPERCASE to be recognised.

    1. Trade      "buy 10 AAPL" / "sell 2.5 shares of TSLA"
                  -> one trade per match, any positive integer or decimal quantity
    2. Watchlist  "add PYPL to the watchlist" / "remove NFLX from watchlist"
                  -> one watchlist change per match
    3. Portfolio  message contains "portfolio", "position", "p&l" or "pnl"
                  -> text summary of cash, total value and open positions, no actions
    4. Fallback   anything else -> a fixed greeting, no actions

Rules 1 and 2 can fire together; when either fires the message describes the actions
and rule 3 is skipped.
"""

from __future__ import annotations

import re
from typing import Any

from .schema import LLMResponse, TradeInstruction, WatchlistChange

_TRADE = re.compile(r"\b([Bb]uy|[Ss]ell)\s+(\d+(?:\.\d+)?)\s+(?:[Ss]hares?\s+of\s+)?([A-Z]{1,5})\b")
_ADD = re.compile(r"\b[Aa]dd\s+([A-Z]{1,5})\s+to\s+(?:the\s+)?[Ww]atchlist\b")
_REMOVE = re.compile(r"\b[Rr]emove\s+([A-Z]{1,5})\s+from\s+(?:the\s+)?[Ww]atchlist\b")
_PORTFOLIO = re.compile(r"portfolio|position|p&l|pnl", re.I)

GREETING = (
    "Mock mode active. Ask me about your portfolio, or tell me to buy or sell shares "
    "(for example: buy 10 AAPL)."
)


def mock_response(message: str, context: dict[str, Any]) -> LLMResponse:
    """Produce the deterministic reply for a user message and portfolio context."""
    trades = [
        TradeInstruction(ticker=ticker.upper(), side=side.lower(), quantity=float(qty))
        for side, qty, ticker in _TRADE.findall(message)
    ]
    changes = [WatchlistChange(ticker=t, action="add") for t in _ADD.findall(message)]
    changes += [WatchlistChange(ticker=t, action="remove") for t in _REMOVE.findall(message)]

    if trades or changes:
        parts = [f"{t.side} {t.quantity:g} {t.ticker}" for t in trades]
        parts += [f"{c.action} {c.ticker} on the watchlist" for c in changes]
        return LLMResponse(
            message="Understood. Executing: " + ", ".join(parts) + ".",
            trades=trades,
            watchlist_changes=changes,
        )

    if _PORTFOLIO.search(message):
        return LLMResponse(message=_summary(context))

    return LLMResponse(message=GREETING)


def _summary(context: dict[str, Any]) -> str:
    positions = context.get("positions", [])
    header = (
        f"Cash {context.get('cash_balance', 0):.2f}, "
        f"total value {context.get('total_value', 0):.2f}, "
        f"{len(positions)} open position(s)."
    )
    if not positions:
        return header + " No holdings yet."
    lines = [
        f"{p['ticker']}: {p['quantity']:g} @ {p['avg_cost']:.2f} avg, P&L {p['unrealized_pnl']}"
        for p in positions
    ]
    return header + " " + "; ".join(lines)
