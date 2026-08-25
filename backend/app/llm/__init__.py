"""LLM chat subsystem for FinAlly.

Public API:
    create_chat_router  - Factory returning the /api/chat APIRouter
    ChatResponse         - The structured-output response contract
    GENERIC_RETRY_MESSAGE - The one shared timeout/malformed-output copy string
    get_chat_response      - The LiteLLM/OpenRouter/Cerebras call, off the event loop
    execute_actions          - Auto-executes parsed.trades/watchlist_changes, execution-derived
    apply_watchlist_change    - One LLM-proposed watchlist add/remove, mirrors watchlist/router.py
"""

from .client import get_chat_response
from .executor import apply_watchlist_change, execute_actions
from .router import GENERIC_RETRY_MESSAGE, create_chat_router
from .schemas import ChatResponse

__all__ = [
    "create_chat_router",
    "ChatResponse",
    "GENERIC_RETRY_MESSAGE",
    "get_chat_response",
    "execute_actions",
    "apply_watchlist_change",
]
