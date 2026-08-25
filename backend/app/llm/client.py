"""LiteLLM -> OpenRouter -> Cerebras completion call.

Follows .claude/skills/cerebras/SKILL.md exactly. completion() is
synchronous, so every call is wrapped in asyncio.to_thread() -- the same
idiom app/market/massive_client.py already uses for its synchronous SDK
call -- to avoid blocking the single event loop for up to TIMEOUT_S.
"""

from __future__ import annotations

import asyncio
import logging

import litellm
from openai import APIError, APITimeoutError
from pydantic import ValidationError

from .schemas import ChatResponse

MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}
MAX_TOKENS = 1024
TIMEOUT_S = 30

logger = logging.getLogger(__name__)


def _call_llm_sync(messages: list[dict]) -> str:
    """Blocking call -- must only ever run inside asyncio.to_thread()."""
    response = litellm.completion(
        model=MODEL,
        messages=messages,
        response_format=ChatResponse,
        reasoning_effort="low",
        extra_body=EXTRA_BODY,
        max_tokens=MAX_TOKENS,
        timeout=TIMEOUT_S,
    )
    return response.choices[0].message.content


async def get_chat_response(messages: list[dict]) -> ChatResponse | None:
    """Run one chat completion off the event loop and validate its output.

    Returns None on timeout or malformed structured output -- the caller
    shows the generic retry message and persists nothing further (CHAT-05).
    Deliberately no additional outer timeout wrapper here: timeout=TIMEOUT_S
    on completion() is the only timeout, since a second one would orphan
    the still-running thread-pool call with no handle to cancel it.
    """
    try:
        raw = await asyncio.to_thread(_call_llm_sync, messages)
        return ChatResponse.model_validate_json(raw)
    except APITimeoutError:
        logger.warning("LLM call timed out after %ss", TIMEOUT_S)
        return None
    except APIError as e:
        # Rate limits, auth failures, connection drops, 5xx from the
        # provider -- any of these must degrade the same way a timeout
        # does rather than propagate into an unhandled 500 on /api/chat.
        logger.warning("LLM call failed: %s", e)
        return None
    except ValidationError as e:
        # gpt-oss-120b occasionally ignores response_format and returns
        # free-form text instead of JSON -- treat identically to a timeout.
        # pydantic v2's model_validate_json always raises ValidationError
        # (never a raw json.JSONDecodeError) for invalid JSON syntax too.
        logger.warning("LLM returned malformed structured output: %s (raw: %.500s)", e, raw)
        return None
