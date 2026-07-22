"""Headless CLI subcommands for Jarvis (audit + db maintenance).

Design note
-----------
``jarvis`` normally launches the GUI shell (``jarvis.main:main``). A few
operations need to run headless — verifying the audit chain on boot/from a
script, tailing recent agent actions, and DB maintenance from
``ops/cleanup-space.sh``. Those are dispatched here so no GUI/Qt import is
needed for them.

Usage:
    jarvis audit verify        # walk the hash chain, report first broken entry
    jarvis audit tail [N]      # print the last N audit entries (default 20)
    jarvis db checkpoint       # WAL checkpoint (truncate)
    jarvis db vacuum           # checkpoint + VACUUM (compact)
"""

from __future__ import annotations

import json
import sys
from datetime import datetime


def _audit_verify() -> int:
    from .audit.chain import verify_chain_detailed

    ok, broken_id = verify_chain_detailed()
    if ok:
        print("audit chain OK")
        return 0
    print(f"audit chain BROKEN at entry id={broken_id}", file=sys.stderr)
    return 1


def _audit_tail(argv: list[str]) -> int:
    from .audit.chain import tail

    limit = 20
    if argv:
        try:
            limit = int(argv[0])
        except ValueError:
            print(f"invalid count: {argv[0]}", file=sys.stderr)
            return 2
    for e in tail(limit):
        ts = datetime.fromtimestamp(e["ts"]).strftime("%Y-%m-%d %H:%M:%S")
        print(f"#{e['id']:>6}  {ts}  {e['event']}  {json.dumps(e['payload'], sort_keys=True)}")
    return 0


def _run_audit(argv: list[str]) -> int:
    if not argv:
        print("usage: jarvis audit {verify|tail [N]}", file=sys.stderr)
        return 2
    sub, rest = argv[0], argv[1:]
    if sub == "verify":
        return _audit_verify()
    if sub == "tail":
        return _audit_tail(rest)
    print(f"unknown audit subcommand: {sub}", file=sys.stderr)
    return 2


def _run_db(argv: list[str]) -> int:
    from .db import get_db

    if not argv:
        print("usage: jarvis db {checkpoint|vacuum}", file=sys.stderr)
        return 2
    db = get_db()
    sub = argv[0]
    if sub == "checkpoint":
        db.checkpoint()
        print("db checkpoint complete")
        return 0
    if sub == "vacuum":
        db.checkpoint()
        db.vacuum()
        print("db checkpoint + vacuum complete")
        return 0
    print(f"unknown db subcommand: {sub}", file=sys.stderr)
    return 2


def dispatch(argv: list[str]) -> int | None:
    """Handle a headless subcommand. Return an exit code, or None to fall through
    to the GUI (no recognised subcommand)."""
    if not argv:
        return None
    cmd, rest = argv[0], argv[1:]
    if cmd == "audit":
        return _run_audit(rest)
    if cmd == "db":
        return _run_db(rest)
    return None
