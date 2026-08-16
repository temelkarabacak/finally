"""Structured output schema for the chat LLM, plus tolerant parsing of its raw reply."""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


class TradeInstruction(BaseModel):
    """A market order the assistant wants executed."""

    ticker: str
    side: Literal["buy", "sell"]
    quantity: float


class WatchlistChange(BaseModel):
    """A watchlist mutation the assistant wants applied."""

    ticker: str
    action: Literal["add", "remove"]


class LLMResponse(BaseModel):
    """The structured output the model is asked to produce."""

    message: str
    trades: list[TradeInstruction] = Field(default_factory=list)
    watchlist_changes: list[WatchlistChange] = Field(default_factory=list)


def parse_llm_response(raw: str | None) -> LLMResponse:
    """Parse the model's reply into an LLMResponse, salvaging what is usable.

    Tolerates markdown code fences, extra keys, and individually malformed trade or
    watchlist entries (those are dropped rather than failing the whole turn). A reply
    that is not JSON at all is treated as a plain conversational message with no actions.
    Raises ValueError only when there is no usable text.
    """
    if not raw or not raw.strip():
        raise ValueError("Empty LLM response")

    text = raw.strip()
    fenced = _FENCE.match(text)
    if fenced:
        text = fenced.group(1)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return LLMResponse(message=raw.strip())

    if not isinstance(data, dict):
        return LLMResponse(message=raw.strip())

    message = data.get("message")
    if not isinstance(message, str) or not message.strip():
        raise ValueError("LLM response JSON has no usable 'message' field")

    return LLMResponse(
        message=message.strip(),
        trades=_coerce(data.get("trades"), TradeInstruction),
        watchlist_changes=_coerce(data.get("watchlist_changes"), WatchlistChange),
    )


def _coerce(items: Any, model: type[BaseModel]) -> list[Any]:
    """Validate each entry independently, discarding the ones that do not fit."""
    if not isinstance(items, list):
        return []
    valid = []
    for item in items:
        try:
            valid.append(model.model_validate(item))
        except Exception:
            continue
    return valid
