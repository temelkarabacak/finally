"""Portfolio value snapshot writes and reads, plus the always-on recorder loop.

record_snapshot has no transaction control of its own: Plan 02-01 calls it
from inside an already-open trade transaction (backend/app/portfolio/trades.py)
and the background loop below calls it standalone every 30 seconds. It is a
bare conn.execute so both callers control the surrounding transaction
themselves.

The loop starts unconditionally at app startup (D-04) -- it is never gated on
a first trade -- so the P&L chart's empty state resolves within about a
minute even for a user who has never traded.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from app.db import DEFAULT_USER_ID
from app.market import PriceCache

from .valuation import compute_total_value

logger = logging.getLogger(__name__)

SNAPSHOT_INTERVAL_SECONDS = 30.0
HISTORY_LIMIT = 2000


def record_snapshot(
    conn: sqlite3.Connection,
    total_value: float,
    user_id: str = DEFAULT_USER_ID,
    recorded_at: str | None = None,
) -> None:
    """Insert one portfolio_snapshots row.

    No BEGIN/COMMIT here by design -- see module docstring. Callers that need
    this write as part of a larger unit (e.g. a trade) must already have an
    open transaction; callers writing a standalone snapshot (the 30s loop)
    rely on autocommit=True to commit this single statement on its own.
    """
    conn.execute(
        "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
        "VALUES (?, ?, ?, ?)",
        (uuid.uuid4().hex, user_id, total_value, recorded_at or datetime.now(UTC).isoformat()),
    )


def get_snapshot_history(
    conn: sqlite3.Connection,
    user_id: str = DEFAULT_USER_ID,
    limit: int = HISTORY_LIMIT,
) -> list[dict]:
    """Return the most recent `limit` snapshots, oldest first.

    Ordering is total: recorded_at ascending with id as a deterministic
    tie-break, so two snapshots written in the same instant (a 30s tick
    landing on a trade) always come back in the same relative order across
    repeated calls, rather than whatever order SQLite happens to return.
    """
    rows = conn.execute(
        "SELECT total_value, recorded_at, id FROM ("
        "  SELECT total_value, recorded_at, id FROM portfolio_snapshots"
        "  WHERE user_id = ?"
        "  ORDER BY recorded_at DESC, id DESC"
        "  LIMIT ?"
        ") ORDER BY recorded_at ASC, id ASC",
        (user_id, limit),
    ).fetchall()
    return [
        {
            "time": int(datetime.fromisoformat(recorded_at).timestamp()),
            "value": total_value,
            "recorded_at": recorded_at,
        }
        for total_value, recorded_at, _id in rows
    ]


async def _snapshot_loop(
    get_conn: Callable[[], sqlite3.Connection],
    cache: PriceCache,
    interval: float = SNAPSHOT_INTERVAL_SECONDS,
) -> None:
    """Sleep, then record, forever. Sleeping first avoids doubling up with a
    snapshot a trade writes in the first instants after startup.

    A failure in one iteration is logged and the loop continues to the next
    interval -- one bad iteration must not silently kill the recorder for
    the rest of the run, the same convention the market data polling loops
    already follow.
    """
    while True:
        try:
            await asyncio.sleep(interval)
            conn = get_conn()
            record_snapshot(conn, compute_total_value(conn, cache))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Portfolio snapshot loop iteration failed")


def start_snapshot_task(
    get_conn: Callable[[], sqlite3.Connection],
    cache: PriceCache,
    interval: float = SNAPSHOT_INTERVAL_SECONDS,
) -> asyncio.Task:
    """Start the always-on 30-second snapshot recorder (D-04)."""
    return asyncio.create_task(
        _snapshot_loop(get_conn, cache, interval), name="portfolio-snapshot-loop"
    )


async def stop_snapshot_task(task: asyncio.Task | None) -> None:
    """Cancel and await the snapshot task. No-op if task is None."""
    if task is None:
        return
    if not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
