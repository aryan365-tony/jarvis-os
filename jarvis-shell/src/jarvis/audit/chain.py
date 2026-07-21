"""Tamper-evident audit log (SHA-256 hash chain).

Design note
-----------
Now backed by the shared :class:`jarvis.db.Database` (WAL, one connection) and
the audit table is guaranteed to exist by ``Database`` construction, so the very
first ``audit_log`` call can never fail on a missing table (the previous bug).
"""

from __future__ import annotations

import hashlib
import json
import time

from ..db import get_db


def init_audit_table() -> None:
    # Retained for backwards compatibility; Database() already creates the table.
    get_db()


def audit_log(event: str, payload: dict) -> None:
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


def verify_chain() -> bool:
    prev_hash = "0" * 64
    db = get_db()
    for row in db.query(
        "SELECT id, ts, event, payload, prev_hash, row_hash FROM audit_log ORDER BY id"
    ):
        ts, event, payload, stored_prev, stored_hash = (
            row["ts"],
            row["event"],
            row["payload"],
            row["prev_hash"],
            row["row_hash"],
        )
        if stored_prev != prev_hash:
            return False
        expect = hashlib.sha256(
            f"{prev_hash}{ts}{event}{payload}".encode()
        ).hexdigest()
        if expect != stored_hash:
            return False
        prev_hash = stored_hash
    return True
