"""LLM invocation: LiteLLM -> OpenRouter -> Cerebras, with a mock mode for tests."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from app.db import ChatMessage

from .mock import mock_response
from .schema import LLMResponse, parse_llm_response

logger = logging.getLogger(__name__)

MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}
TIMEOUT_SECONDS = 30.0

SYSTEM_PROMPT = """You are FinAlly, an AI trading assistant embedded in a simulated \
trading workstation. The user trades a virtual portfolio with fake money.

Your job:
- Analyse portfolio composition, risk concentration and P&L.
- Suggest trades with clear, data-driven reasoning.
- Execute trades when the user asks for them or agrees to a suggestion.
- Manage the watchlist proactively when a ticker becomes relevant to the conversation.
- Be concise. Reference concrete numbers from the portfolio context.

Rules:
- Only market orders. Fractional quantities are allowed.
- Buys need sufficient cash and sells need sufficient held shares; a trade that fails \
validation is rejected outright, never reduced to fit.
- Only place a trade in the "trades" array when you actually intend it to execute \
immediately. Leave the array empty when you are only discussing an idea.
- Always respond with valid JSON matching the required schema."""


def mock_enabled() -> bool:
    """True when LLM_MOCK is set to a truthy value."""
    return os.getenv("LLM_MOCK", "").strip().lower() in {"1", "true", "yes"}


def build_messages(
    user_message: str, context: dict[str, Any], history: list[ChatMessage]
) -> list[dict[str, str]]:
    """System prompt, live portfolio context, recent history, then the new message."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "system",
            "content": "Current portfolio context:\n" + json.dumps(context, indent=2),
        },
    ]
    messages += [{"role": m.role, "content": m.content} for m in history]
    messages.append({"role": "user", "content": user_message})
    return messages


async def generate_response(
    user_message: str, context: dict[str, Any], history: list[ChatMessage]
) -> LLMResponse:
    """Get a structured response from the LLM (or the mock).

    Raises TimeoutError if the model does not answer within TIMEOUT_SECONDS, and
    ValueError if the reply cannot be parsed into the expected shape.
    """
    if mock_enabled():
        return mock_response(user_message, context)

    messages = build_messages(user_message, context, history)
    raw = await asyncio.wait_for(asyncio.to_thread(_completion, messages), TIMEOUT_SECONDS)
    return parse_llm_response(raw)


def _completion(messages: list[dict[str, str]]) -> str | None:
    from litellm import completion

    response = completion(
        model=MODEL,
        messages=messages,
        response_format=LLMResponse,
        reasoning_effort="low",
        extra_body=EXTRA_BODY,
        timeout=TIMEOUT_SECONDS,
    )
    return response.choices[0].message.content
