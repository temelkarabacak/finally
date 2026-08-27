"""Portfolio subsystem for FinAlly.

Public API:
    create_portfolio_router - Factory returning the /api/portfolio APIRouter
    execute_trade           - Validate and execute a market order
    TradeError               - Raised when a trade is rejected outright
    portfolio_view           - GET /api/portfolio response body
    compute_total_value      - Cash balance plus market value of open positions
    position_views            - One dict per open position, valued against the price cache
    record_snapshot            - Insert one portfolio_snapshots row
    get_snapshot_history        - Return recorded snapshots, oldest first
    start_snapshot_task          - Start the always-on 30s snapshot recorder
    stop_snapshot_task            - Cancel and await the snapshot recorder
    SNAPSHOT_INTERVAL_SECONDS      - Recorder cadence in seconds
"""

from .router import TradeRequest, create_portfolio_router
from .snapshots import (
    SNAPSHOT_INTERVAL_SECONDS,
    get_snapshot_history,
    record_snapshot,
    start_snapshot_task,
    stop_snapshot_task,
)
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
    "get_snapshot_history",
    "start_snapshot_task",
    "stop_snapshot_task",
    "SNAPSHOT_INTERVAL_SECONDS",
]
