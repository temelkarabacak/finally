"""Portfolio subsystem for FinAlly.

Public API:
    create_portfolio_router - Factory returning the /api/portfolio APIRouter
    execute_trade           - Validate and execute a market order
    TradeError               - Raised when a trade is rejected outright
    portfolio_view           - GET /api/portfolio response body
    compute_total_value      - Cash balance plus market value of open positions
    position_views            - One dict per open position, valued against the price cache
    record_snapshot            - Insert one portfolio_snapshots row
"""

from .router import TradeRequest, create_portfolio_router
from .snapshots import record_snapshot
from .trades import TradeError, execute_trade
from .valuation import compute_total_value, portfolio_view, position_views

__all__ = [
    "create_portfolio_router",
    "TradeRequest",
    "execute_trade",
    "TradeError",
    "portfolio_view",
    "compute_total_value",
    "position_views",
    "record_snapshot",
]
