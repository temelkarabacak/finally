"""LLM chat subsystem for FinAlly.

Public API:
    router              - FastAPI router for /api/chat
    LLMResponse         - Structured output schema the model must produce
    parse_llm_response  - Tolerant parser for the model's raw reply
    mock_enabled        - True when LLM_MOCK selects the deterministic mock
"""

from .client import mock_enabled
from .router import router
from .schema import LLMResponse, TradeInstruction, WatchlistChange, parse_llm_response

__all__ = [
    "LLMResponse",
    "TradeInstruction",
    "WatchlistChange",
    "mock_enabled",
    "parse_llm_response",
    "router",
]
