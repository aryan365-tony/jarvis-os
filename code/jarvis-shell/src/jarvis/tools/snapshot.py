"""Snapshot safety net via snapper (Phase 3).

Design note
-----------
This is the recovery backbone the whole autonomy model rests on: before any
``high``-tier tool runs, the approval path takes a **pre-action snapshot** here,
so a bad change is always one ``snapper rollback`` away. The tools are thin,
audited wrappers over the scoped ``sudo snapper`` grant — no shell strings.

Two of the functions are also registered as agent tools so the model can list
and (rarely, deliberately) roll back on its own; ``snapshot_rollback`` is
``high`` because reverting the running system is itself a major action.

``create_pre_action_snapshot`` is NOT a registered tool — it is called by the
registry's approval path, not by the model.
"""

from __future__ import annotations

import re
import subprocess

from ..audit.chain import audit_log
from .registry import register

# The single config that snapshots the root subvolume (@). Created by the
# installer (jarvis-install) alongside a "home" config for @home.
_ROOT_CONFIG = "root"
_NUM_RE = re.compile(r"^\d+$")


def _snapper(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["sudo", "-n", "snapper", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def create_pre_action_snapshot(description: str, config: str = _ROOT_CONFIG) -> str | None:
    """Take a pre-action snapshot; return its numeric id (or ``None`` on failure).

    Called by the registry approval path for high-tier tools. Failure to
    snapshot is logged and returns ``None`` so the caller can decide whether to
    proceed without a safety net (the approver denies in that case).
    """
    desc = description[:200]
    proc = _snapper(
        ["-c", config, "create", "--type", "single", "--print-number",
         "--cleanup-algorithm", "number", "-d", desc]
    )
    if proc.returncode != 0:
        audit_log("snapshot_create_failed", {"config": config, "err": proc.stderr.strip()})
        return None
    snap_id = proc.stdout.strip()
    if not _NUM_RE.match(snap_id):
        audit_log("snapshot_create_unparsable", {"out": proc.stdout.strip()})
        return None
    audit_log("snapshot_created", {"config": config, "id": snap_id, "desc": desc})
    return snap_id


@register(
    "snapshot_list",
    risk="low",
    description="List system snapshots (id, date, description) for a snapper config.",
    parameters={
        "type": "object",
        "properties": {"config": {"type": "string", "description": "snapper config (default 'root')."}},
    },
)
def snapshot_list(config: str = _ROOT_CONFIG) -> str:
    proc = _snapper(["-c", config, "list", "--columns", "number,date,description"], timeout=30)
    return (proc.stdout or proc.stderr or "(no output)")[:8000]


@register(
    "snapshot_rollback",
    risk="high",
    description=(
        "Roll the system back to a numbered snapshot. Major action: taking a "
        "pre-rollback snapshot of the current state is handled automatically."
    ),
    parameters={
        "type": "object",
        "properties": {
            "snapshot_id": {"type": "integer"},
            "config": {"type": "string"},
        },
        "required": ["snapshot_id"],
    },
)
def snapshot_rollback(snapshot_id: int, config: str = _ROOT_CONFIG) -> str:
    sid = str(snapshot_id)
    if not _NUM_RE.match(sid):
        return "error: snapshot_id must be numeric"
    proc = _snapper(["-c", config, "rollback", sid], timeout=120)
    if proc.returncode != 0:
        return f"error: rollback failed: {proc.stderr.strip()}"
    audit_log("snapshot_rollback", {"config": config, "id": sid})
    return (
        f"rolled back to snapshot {sid}. A reboot is required to boot into the "
        "restored state (run: sudo systemctl reboot)."
    )
