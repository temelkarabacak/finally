"""Chat message persistence: the two-transaction split around the LLM call.

The shared connection is opened with autocommit=True
(backend/app/db/connection.py), under which each execute() commits on its
own -- exactly the same reasoning app/portfolio/trades.py's module
docstring documents for execute_trade(). This module now governs a second
call site for that same discipline.

save_chat_message() wraps its single INSERT in an explicit SQL
BEGIN/COMMIT (ROLLBACK on any exception) with zero awaits inside the
block -- a coroutine only yields at an await point, so a block with no
await inside it is what serializes this write against the 30s snapshot
task and against a concurrent trade-bar fill on the single-threaded event
loop. This is exactly why the (awaited) LLM call is issued strictly
between two separate calls to this function, never inside either's
transaction.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime

from app.db import DEFAULT_USER_ID


def save_chat_message(
    conn: sqlite3.Connection,
    role: str,
    content: str,
    actions: dict | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> None:
    """Insert one chat_messages row inside its own BEGIN/COMMIT."""
    now_iso = datetime.now(UTC).isoformat()
    actions_json = json.dumps(actions) if actions is not None else None

    conn.execute("BEGIN")
    try:
        conn.execute(
            "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (uuid.uuid4().hex, user_id, role, content, actions_json, now_iso),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def load_recent_chat_messages(
    conn: sqlite3.Connection, limit: int = 20, user_id: str = DEFAULT_USER_ID
) -> list[dict]:
    """Return the most recent `limit` chat_messages rows, oldest first.

    Only role/content are returned -- never `actions` -- so replayed
    history can never leak a prior turn's portfolio figures into a later
    prompt (those must always come fresh from build_portfolio_context()).
    """
    rows = conn.execute(
        "SELECT role, content FROM chat_messages WHERE user_id = ? "
        "ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    return [{"role": role, "content": content} for role, content in reversed(rows)]
