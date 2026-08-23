"""Database subsystem for FinAlly.

Public API:
    init_db              - Lazily create schema and seed default data
    get_db                - Return the module-level singleton connection
    get_active_tickers    - watchlist UNION open positions for a user
    get_watchlist_tickers - watchlist tickers for a user, ordered by added_at
    resolve_db_path        - Resolve the SQLite file path (env var or default)
    seed_defaults          - Insert default user profile + watchlist rows
    DEFAULT_USER_ID         - Hardcoded single-user id ("default")
    DEFAULT_CASH_BALANCE    - Starting cash balance for a new user
    DEFAULT_WATCHLIST       - The ten default watchlist tickers
"""

from .connection import (
    get_active_tickers,
    get_db,
    get_watchlist_tickers,
    init_db,
    resolve_db_path,
)
from .seed import DEFAULT_CASH_BALANCE, DEFAULT_USER_ID, DEFAULT_WATCHLIST, seed_defaults

__all__ = [
    "init_db",
    "get_db",
    "get_active_tickers",
    "get_watchlist_tickers",
    "resolve_db_path",
    "seed_defaults",
    "DEFAULT_USER_ID",
    "DEFAULT_CASH_BALANCE",
    "DEFAULT_WATCHLIST",
]
