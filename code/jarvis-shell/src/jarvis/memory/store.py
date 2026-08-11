"""Persistent memory: core key/value facts + rolling conversation log.

Design note
-----------
Uses the shared :class:`jarvis.db.Database`. Session history is persisted so the
assistant keeps context across restarts (a "living assistant", not a fresh chat
every boot). All reads degrade to empty rather than raising, so a missing table
never blocks the UI.
"""

from __future__ import annotations

import time

from ..db import get_db

# BUG-013: session_log writes are frequent (every user/assistant/tool
# message) but not safety-critical the way audit_log is. Committing (and
# fsyncing the WAL) on every single insert added ~2 commits/turn on top of
# audit_log's own commits. Batch every N writes instead, bounding the
# at-most-lost-on-crash window to a handful of recent turns rather than
# eliminating durability. core_memory writes stay commit=True (rare, and
# each one matters).
_SESSION_FLUSH_EVERY = 20
_uncommitted_writes = 0


def load_core_memory() -> dict[str, str]:
    try:
        rows = get_db().query(
            "SELECT key, value FROM core_memory ORDER BY updated_at"
        )
        return {r["key"]: r["value"] for r in rows}
    except Exception:
        return {}


def set_core_memory(key: str, value: str) -> None:
    get_db().execute(
        "INSERT INTO core_memory (key, value, updated_at) VALUES (?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (key, value, time.time()),
    )


def append_session(role: str, content: str) -> None:
    global _uncommitted_writes
    db = get_db()
    _uncommitted_writes += 1
    flush = _uncommitted_writes >= _SESSION_FLUSH_EVERY
    db.execute(
        "INSERT INTO session_log (role, content, ts) VALUES (?,?,?)",
        (role, content, time.time()),
        commit=flush,
    )
    if flush:
        _uncommitted_writes = 0


def prune_session(keep: int = 5000) -> None:
    """Drop old session_log rows beyond ``keep`` (BUG-003: unbounded growth)."""
    get_db().execute(
        "DELETE FROM session_log WHERE id NOT IN "
        "(SELECT id FROM session_log ORDER BY id DESC LIMIT ?)",
        (keep,),
    )


def recent_session(limit: int = 20) -> list[dict]:
    try:
        rows = get_db().query(
            "SELECT role, content FROM session_log ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
    except Exception:
        return []
