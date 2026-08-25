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

from fastapi import APIRouter, Query

from app.market import MarketDataSource, PriceCache

from .client import get_chat_response
from .executor import execute_actions
from .mock import mock_chat_response
from .persistence import load_chat_history, load_recent_chat_messages, save_chat_message
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
) -> tuple[ChatResponse | None, dict | None]:
    """One /api/chat turn. Returns (None, None) on timeout/malformed output --
    the caller returns the generic retry message and persists nothing further.
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
        return None, None  # nothing further persisted (CHAT-05)

    # 4. Auto-execute through the EXISTING validated code paths -- the
    #    actions payload is built entirely from execute_actions()'s return
    #    value, never echoed from the model's own proposed action lists,
    #    per the execution-derived-action-reporting guardrail (T-03-11).
    actions = await execute_actions(conn, price_cache, market_source, parsed)

    # 5. Persist the assistant turn + actions only after successful
    #    generation (CHAT-04/05).
    save_chat_message(conn, role="assistant", content=parsed.message, actions=actions)

    n_trades = len(actions["trades"])
    n_rejected = sum(1 for entry in actions["trades"] if not entry["success"])
    n_watchlist = len(actions["watchlist_changes"])

    logger.info(
        "chat turn outcome=%s duration_ms=%d mock=%s trades=%d rejected=%d watchlist=%d",
        "ok",
        duration_ms,
        mock,
        n_trades,
        n_rejected,
        n_watchlist,
    )
    return parsed, actions


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

    @router.get("/history")
    async def get_history(limit: int = Query(default=50, ge=1, le=200)) -> list[dict]:
        """Return the persisted transcript, oldest first.

        200 with [] when nothing is persisted -- the same stance
        GET /api/portfolio/history already takes, since an empty transcript
        is a valid state rather than a missing resource.
        """
        conn = get_conn()
        return load_chat_history(conn, limit)

    @router.post("")
    async def post_chat(request: ChatRequest) -> dict:
        conn = get_conn()
        parsed, actions = await handle_chat_message(
            conn, market_source, price_cache, request.message, mock
        )
        if parsed is None:
            return {
                "message": GENERIC_RETRY_MESSAGE,
                "actions": {"trades": [], "watchlist_changes": []},
            }
        return {
            "message": parsed.message,
            "actions": actions,
        }

    return router
