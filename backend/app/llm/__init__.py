"""LLM chat subsystem for FinAlly.

Public API:
    create_chat_router  - Factory returning the /api/chat APIRouter
    ChatResponse         - The structured-output response contract
    GENERIC_RETRY_MESSAGE - The one shared timeout/malformed-output copy string
    get_chat_response      - The LiteLLM/OpenRouter/Cerebras call, off the event loop
"""

from .client import get_chat_response
from .router import GENERIC_RETRY_MESSAGE, create_chat_router
from .schemas import ChatResponse

__all__ = [
    "create_chat_router",
    "ChatResponse",
    "GENERIC_RETRY_MESSAGE",
    "get_chat_response",
]
