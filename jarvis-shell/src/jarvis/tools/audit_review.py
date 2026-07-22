"""Audit self-review tool (Phase 4).

Design note
-----------
Autonomy requires accountability the agent can inspect itself: this low-risk,
read-only tool lets the model review its own recent actions (what it did, at
what tier, linked to which snapshot) and confirm the tamper-evident chain is
still intact. It never writes, so it is ``low`` tier and needs no snapshot.

It is deliberately the ONLY audit surface exposed as a tool — there is no tool
to delete, edit, or truncate audit entries, so the agent cannot erase its own
trail.
"""

from __future__ import annotations

import json

from ..audit.chain import tail as _tail
from ..audit.chain import verify_chain_detailed
from .registry import register


@register(
    "audit_review",
    risk="low",
    description=(
        "Review the agent's own recent audited actions and verify the "
        "tamper-evident hash chain is intact. Read-only."
    ),
    parameters={
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "How many recent entries (default 20)."},
            "event_filter": {
                "type": "string",
                "description": "Only show entries whose event contains this substring.",
            },
        },
    },
)
def audit_review(limit: int = 20, event_filter: str = "") -> str:
    ok, broken_id = verify_chain_detailed()
    header = (
        "chain: INTACT" if ok else f"chain: BROKEN at entry id {broken_id}"
    )
    entries = _tail(max(1, min(limit, 200)))
    if event_filter:
        entries = [e for e in entries if event_filter in e["event"]]
    lines = [header, f"showing {len(entries)} entr{'y' if len(entries)==1 else 'ies'}:"]
    for e in entries:
        payload = e["payload"]
        # keep the summary compact so it never floods the context window
        summary = {k: payload[k] for k in ("name", "tool", "tier", "snapshot_id") if k in payload}
        lines.append(f"#{e['id']} {e['event']} {json.dumps(summary, sort_keys=True)}")
    return "\n".join(lines)
