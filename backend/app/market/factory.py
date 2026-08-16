"""Factory for creating market data sources."""

from __future__ import annotations

import logging
import os

from .cache import PriceCache
from .interface import MarketDataSource
from .massive_client import MassiveDataSource, OnPermanentFailure
from .simulator import SimulatorDataSource

logger = logging.getLogger(__name__)


def create_market_data_source(
    price_cache: PriceCache,
    on_permanent_failure: OnPermanentFailure | None = None,
) -> MarketDataSource:
    """Create the appropriate market data source based on environment variables.

    - MASSIVE_API_KEY set and non-empty → MassiveDataSource (real market data)
    - Otherwise → SimulatorDataSource (GBM simulation)

    ``on_permanent_failure`` is only used by MassiveDataSource: it is awaited
    once, with the tickers it was tracking, the first time a poll fails (auth,
    rate limit, network, or service error — see PLAN.md section 6). The caller
    is expected to start a SimulatorDataSource with those tickers and take
    over as the app's active source; Massive is never retried after that.

    Returns an unstarted source. Caller must await source.start(tickers).
    """
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()

    if api_key:
        logger.info("Market data source: Massive API (real data)")
        return MassiveDataSource(
            api_key=api_key,
            price_cache=price_cache,
            on_permanent_failure=on_permanent_failure,
        )
    else:
        logger.info("Market data source: GBM Simulator")
        return SimulatorDataSource(price_cache=price_cache)
