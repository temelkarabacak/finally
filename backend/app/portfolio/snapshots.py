"""Portfolio value snapshot writes (the write half only).

record_snapshot has no transaction control of its own: Plan 02-01 calls it
from inside an already-open trade transaction (backend/app/portfolio/trades.py)
and Plan 02-03 will call it from a background 30-second loop. It is a bare
conn.execute so both callers control the surrounding transaction themselves.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime

from app.db import DEFAULT_USER_ID


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
