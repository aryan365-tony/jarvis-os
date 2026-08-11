"""Tamper-evident audit log (SHA-256 hash chain).

Design note
-----------
Now backed by the shared :class:`jarvis.db.Database` (WAL, one connection) and
the audit table is guaranteed to exist by ``Database`` construction, so the very
first ``audit_log`` call can never fail on a missing table (the previous bug).

Durable channel (Phase 1/4)
---------------------------
Every ``audit_log`` write is persisted synchronously to the hash chain on disk
*and* mirrored onto the bus ``audit_events`` durable channel (when a bus is
attached) so live consumers — and the durability test gate — observe every
event with zero drops.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time

from ..db import get_db

log = logging.getLogger("jarvis.audit")

# Optional bus reference so audit writes also route through the durable
# ``audit_events`` channel (Phase 1). Attached by the Runtime at startup; when
# absent (e.g. in unit tests or the CLI) audit_log still persists to disk.
_bus = None  # type: ignore[var-annotated]


def set_audit_bus(bus) -> None:
    """Attach the event bus so audit_log mirrors events onto audit_events."""
    global _bus
    _bus = bus


def init_audit_table() -> None:
    # Retained for backwards compatibility; Database() already creates the table.
    get_db()


def _mirror_to_bus(event: str, payload: dict) -> None:
    if _bus is None:
        return
    try:
        from ..events import AUDIT_EVENTS, AuditEvent

        _bus.publish(AUDIT_EVENTS, AuditEvent(kind="audit", source=event, data=payload))
    except Exception:  # never let telemetry mirroring break a real audit write
        log.exception("failed to mirror audit event to bus")


def audit_log(event: str, payload: dict) -> None:
    # Uses db.conn directly (not the db.execute() wrapper) intentionally:
    # the SELECT-prev-hash + INSERT must be one atomic unit under a single
    # db.lock acquisition, or two concurrent audit_log() calls could both
    # read the same prev_hash and corrupt the chain. db.execute() commits
    # (and releases nothing extra, but is a separate call) per-statement,
    # which would not provide that atomicity across the read+write pair.
    # (BUG-005 audit claim verified incorrect — the wrapper is not a safe
    # substitute here; kept as-is.)
    db = get_db()
    with db.lock:
        row = db.conn.execute(
            "SELECT row_hash FROM audit_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        prev_hash = row[0] if row else "0" * 64
        ts = time.time()
        payload_json = json.dumps(payload, sort_keys=True)
        row_hash = hashlib.sha256(
            f"{prev_hash}{ts}{event}{payload_json}".encode()
        ).hexdigest()
        db.conn.execute(
            "INSERT INTO audit_log (ts, event, payload, prev_hash, row_hash) VALUES (?,?,?,?,?)",
            (ts, event, payload_json, prev_hash, row_hash),
        )
        db.conn.commit()
    # Mirror onto the durable channel outside the DB lock so a slow subscriber
    # cannot hold the write lock.
    _mirror_to_bus(event, payload)


def verify_chain() -> bool:
    """Return True iff the whole chain is intact. See :func:`verify_chain_detailed`."""
    return verify_chain_detailed()[0]


def verify_chain_detailed(chunk_size: int = 2000) -> tuple[bool, int | None]:
    """Walk the chain; return ``(ok, broken_id)``.

    ``broken_id`` is the ``audit_log.id`` of the first entry whose stored
    ``prev_hash`` or recomputed ``row_hash`` does not match, or ``None`` when the
    chain is fully intact. Used by ``jarvis audit verify`` to report the exact
    offending entry index.

    BUG-010: a single ``db.query()`` over the whole table holds ``db.lock``
    for the entire scan, blocking every writer (including ``audit_log``
    itself) for as long as the scan takes — seconds on a large table at
    boot. Read in bounded chunks instead so each chunk only holds the lock
    briefly, letting writers interleave between chunks.
    """
    prev_hash = "0" * 64
    db = get_db()
    last_id = 0
    while True:
        rows = db.query(
            "SELECT id, ts, event, payload, prev_hash, row_hash FROM audit_log "
            "WHERE id > ? ORDER BY id LIMIT ?",
            (last_id, chunk_size),
        )
        if not rows:
            break
        for row in rows:
            rid, ts, event, payload, stored_prev, stored_hash = (
                row["id"],
                row["ts"],
                row["event"],
                row["payload"],
                row["prev_hash"],
                row["row_hash"],
            )
            if stored_prev != prev_hash:
                return (False, rid)
            expect = hashlib.sha256(
                f"{prev_hash}{ts}{event}{payload}".encode()
            ).hexdigest()
            if expect != stored_hash:
                return (False, rid)
            prev_hash = stored_hash
            last_id = rid
    return (True, None)


def tail(limit: int = 20) -> list[dict]:
    """Return the most recent audit entries (oldest→newest) for review."""
    db = get_db()
    rows = db.query(
        "SELECT id, ts, event, payload FROM audit_log ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    out = []
    for r in reversed(rows):
        try:
            payload = json.loads(r["payload"])
        except (json.JSONDecodeError, TypeError):
            payload = {"raw": r["payload"]}
        out.append({"id": r["id"], "ts": r["ts"], "event": r["event"], "payload": payload})
    return out
