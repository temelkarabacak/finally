"""Chat REST endpoints backed by the LLM."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.db import ChatMessage, get_db, insert_chat_message, list_recent_chat_messages
from app.dependencies import get_market_source, get_price_cache
from app.market import MarketDataSource, PriceCache

from .client import generate_response
from .context import build_portfolio_context
from .executor import apply_watchlist_change, execute_trade

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 20
RETRY_MESSAGE = "Sorry, I could not complete that request. Please try again."

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


class ChatMessageOut(BaseModel):
    id: str
    role: str
    content: str
    actions: Any | None
    created_at: str


class ChatReply(BaseModel):
    """What the frontend renders: the assistant's text plus the outcome of each action."""

    message: str
    trades: list[dict[str, Any]] = Field(default_factory=list)
    watchlist_changes: list[dict[str, Any]] = Field(default_factory=list)


@router.get("/history", response_model=list[ChatMessageOut])
def read_history(conn: sqlite3.Connection = Depends(get_db)) -> list[ChatMessage]:
    """The recent conversation, oldest first, for rehydrating the chat panel."""
    return list_recent_chat_messages(conn, limit=HISTORY_LIMIT)


@router.post("", response_model=ChatReply)
async def chat(
    request: ChatRequest,
    conn: sqlite3.Connection = Depends(get_db),
    cache: PriceCache = Depends(get_price_cache),
    source: MarketDataSource = Depends(get_market_source),
) -> ChatReply:
    """Answer a user message, auto-executing any trades and watchlist edits it implies."""
    context = build_portfolio_context(conn, cache)
    history = list_recent_chat_messages(conn, limit=HISTORY_LIMIT)

    # Committed before the call so the message survives a client disconnect during
    # the up-to-30s wait, which would otherwise roll the request transaction back.
    insert_chat_message(conn, "user", request.message)
    conn.commit()

    try:
        response = await generate_response(request.message, context, history)
    except TimeoutError:
        logger.warning("LLM request timed out")
        return ChatReply(message=RETRY_MESSAGE)
    except Exception:
        logger.exception("LLM request failed")
        return ChatReply(message=RETRY_MESSAGE)

    trades = [execute_trade(conn, cache, t) for t in response.trades]
    changes = [await apply_watchlist_change(conn, source, c) for c in response.watchlist_changes]

    message = _with_rejections(response.message, trades, changes)
    actions = {"trades": trades, "watchlist_changes": changes} if trades or changes else None
    insert_chat_message(conn, "assistant", message, actions=actions)
    conn.commit()

    return ChatReply(message=message, trades=trades, watchlist_changes=changes)


def _with_rejections(
    message: str, trades: list[dict[str, Any]], changes: list[dict[str, Any]]
) -> str:
    """Append any rejection reasons so the user sees why an action did not happen."""
    errors = [a["error"] for a in trades + changes if a["status"] == "rejected"]
    if not errors:
        return message
    return message + "\n\nNot completed: " + "; ".join(errors)
