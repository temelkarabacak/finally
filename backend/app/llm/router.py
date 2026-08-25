"""REST router for the chat turn: POST /api/chat.

Implements AI-SPEC §4's core pattern: persist the user message before the
(awaited) LLM call, build fresh context and history as read-only work
outside any transaction, call the model (or the mock matcher), and
persist the assistant reply only after a successful, validated response.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from collections.abc import Callable

from fastapi import APIRouter

from app.market import MarketDataSource, PriceCache

from .client import get_chat_response
from .mock import mock_chat_response
from .persistence import load_recent_chat_messages, save_chat_message
from .prompt import SYSTEM_PROMPT, build_messages, build_portfolio_context
from .schemas import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

GENERIC_RETRY_MESSAGE = "Something went wrong — please try again."


async def handle_chat_message(
    conn: sqlite3.Connection,
    market_source: MarketDataSource,
    price_cache: PriceCache,
    user_text: str,
    mock: bool,
) -> ChatResponse | None:
    """One /api/chat turn. Returns None on timeout/malformed output -- the
    caller returns the generic retry message and persists nothing further.
    """
    start = time.monotonic()

    # 1. Persist the user's message BEFORE calling the LLM (CHAT-04) so it
    #    survives a subsequent timeout/error.
    save_chat_message(conn, role="user", content=user_text)

    # 2. Build fresh context every turn -- reads only, no open transaction.
    portfolio_ctx = build_portfolio_context(conn, price_cache)
    history = load_recent_chat_messages(conn, limit=20)
    messages = build_messages(SYSTEM_PROMPT, portfolio_ctx, history, user_text)

    # 3. Call the LLM. The mock branch never touches the network.
    if mock:
        parsed = mock_chat_response(user_text)
    else:
        parsed = await get_chat_response(messages)

    duration_ms = int((time.monotonic() - start) * 1000)

    if parsed is None:
        logger.info(
            "chat turn outcome=%s duration_ms=%d mock=%s trades=0 rejected=0 watchlist=0",
            "timeout_or_malformed",
            duration_ms,
            mock,
        )
        return None  # nothing further persisted (CHAT-05)

    # 4. No executor yet in this task (plan 03-02 adds trade/watchlist
    #    auto-execution) -- the actions payload is always empty here, and
    #    it is built from execution results, never from parsed.trades, per
    #    the execution-derived-action-reporting guardrail.
    actions = {"trades": [], "watchlist_changes": []}

    # 5. Persist the assistant turn + actions only after successful
    #    generation (CHAT-04/05).
    save_chat_message(conn, role="assistant", content=parsed.message, actions=actions)

    logger.info(
        "chat turn outcome=%s duration_ms=%d mock=%s trades=0 rejected=0 watchlist=0",
        "ok",
        duration_ms,
        mock,
    )
    return parsed


def create_chat_router(
    get_conn: Callable[[], sqlite3.Connection],
    market_source: MarketDataSource,
    price_cache: PriceCache,
    mock: bool = False,
) -> APIRouter:
    """Create the chat router with injected DB connection, source, cache, and mode.

    Factory pattern (mirrors create_portfolio_router/create_watchlist_router):
    returns a fresh APIRouter per call so tests can build it repeatedly.
    """
    router = APIRouter(prefix="/api/chat", tags=["chat"])

    @router.post("")
    async def post_chat(request: ChatRequest) -> dict:
        conn = get_conn()
        result = await handle_chat_message(
            conn, market_source, price_cache, request.message, mock
        )
        if result is None:
            return {
                "message": GENERIC_RETRY_MESSAGE,
                "actions": {"trades": [], "watchlist_changes": []},
            }
        return {
            "message": result.message,
            "actions": {"trades": [], "watchlist_changes": []},
        }

    return router
