"""Filesystem tools split by privilege boundary.

Design note
-----------
The plan asks for "high outside /home/jarvisuser/scratch, low inside". A tool's
risk tier is *static* at registration, so we expose two tools instead of one
dynamically-tiered tool:

* ``fs_read``      (low)  — read a text file (agent inspecting the system).
* ``fs_scratch``   (low)  — write/mkdir/remove/move directly as ``jarvisuser`` (no root).
* ``fs_system``    (high) — mutate paths anywhere the boundary allows, routed
                            through the root helper ``sudo jarvis-fsop``. High
                            tier => a pre-action snapshot is taken by the
                            registry before this runs.

``fs_system`` NEVER shells out to a generic command; it only ever invokes the
audited, denylist-guarded ``jarvis-fsop`` helper. That helper — not this Python
— is the security boundary.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from ..config import get_config
from .registry import register

_FSOP = "/usr/local/bin/jarvis-fsop"


def _scratch_dir() -> Path:
    return Path(get_config().policy.fs_scratch_dir).expanduser()


def _inside_scratch(path: str) -> bool:
    scratch = _scratch_dir().resolve()
    try:
        target = Path(path).expanduser().resolve()
    except OSError:
        target = Path(os.path.realpath(os.path.expanduser(path)))
    return target == scratch or scratch in target.parents


def _run_fsop(args: list[str], stdin: str | None = None) -> str:
    proc = subprocess.run(
        ["sudo", "-n", _FSOP, *args],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        return f"error(fsop exit={proc.returncode}): {proc.stderr.strip() or proc.stdout.strip()}"
    return proc.stdout.strip() or "ok"


# --------------------------------------------------------------------------- #
# low: read
# --------------------------------------------------------------------------- #
@register(
    "fs_read",
    risk="low",
    description="Read a UTF-8 text file and return up to 16 KB of its contents.",
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
)
def fs_read(path: str) -> str:
    try:
        data = Path(path).expanduser().read_text(errors="replace")
    except Exception as e:
        return f"error: {e}"
    return data[:16000]


# --------------------------------------------------------------------------- #
# low: scratch mutations (no root)
# --------------------------------------------------------------------------- #
@register(
    "fs_scratch",
    risk="low",
    description=(
        "Create, write, remove, or move files WITHIN the agent scratch "
        "directory (~jarvisuser/scratch by default). Refuses paths outside scratch; "
        "use fs_system for system-wide mutations."
    ),
    parameters={
        "type": "object",
        "properties": {
            "op": {"type": "string", "enum": ["write", "mkdir", "rm", "move"]},
            "path": {"type": "string"},
            "dst": {"type": "string", "description": "Destination for move."},
            "content": {"type": "string", "description": "Content for write."},
        },
        "required": ["op", "path"],
    },
)
def fs_scratch(op: str, path: str, dst: str | None = None, content: str = "") -> str:
    scratch = _scratch_dir()
    scratch.mkdir(parents=True, exist_ok=True)
    if not _inside_scratch(path):
        return f"error: path is outside the scratch dir ({scratch}); use fs_system for system paths"
    p = Path(path).expanduser()
    try:
        if op == "write":
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return f"wrote {len(content)} bytes to {p}"
        if op == "mkdir":
            p.mkdir(parents=True, exist_ok=True)
            return f"mkdir {p}"
        if op == "rm":
            if p.is_dir():
                import shutil

                shutil.rmtree(p)
            elif p.exists() or p.is_symlink():
                p.unlink()
            else:
                return f"error: no such path: {p}"
            return f"removed {p}"
        if op == "move":
            if not dst:
                return "error: move needs dst"
            if not _inside_scratch(dst):
                return f"error: move dst is outside the scratch dir; use fs_system"
            Path(dst).expanduser().parent.mkdir(parents=True, exist_ok=True)
            p.rename(Path(dst).expanduser())
            return f"moved {p} -> {dst}"
        return f"error: unknown op {op}"
    except Exception as e:
        return f"error: {e}"


# --------------------------------------------------------------------------- #
# high: system mutations (root via jarvis-fsop)
# --------------------------------------------------------------------------- #
@register(
    "fs_system",
    risk="high",
    description=(
        "Mutate a system file/directory via the audited root helper "
        "(jarvis-fsop): write, mkdir, rm, chmod, chown, copy, move. "
        "Protected paths (boot, sudoers, secrets, audit store) are refused."
    ),
    parameters={
        "type": "object",
        "properties": {
            "op": {
                "type": "string",
                "enum": ["write", "mkdir", "rm", "chmod", "chown", "copy", "move"],
            },
            "path": {"type": "string"},
            "dst": {"type": "string", "description": "Destination for copy/move."},
            "mode": {"type": "string", "description": "Octal mode for chmod."},
            "owner": {"type": "string", "description": "owner[:group] for chown."},
            "content": {"type": "string", "description": "Content for write."},
        },
        "required": ["op", "path"],
    },
)
def fs_system(
    op: str,
    path: str,
    dst: str | None = None,
    mode: str | None = None,
    owner: str | None = None,
    content: str = "",
) -> str:
    if op == "write":
        return _run_fsop(["write", path], stdin=content)
    if op in ("mkdir", "rm"):
        return _run_fsop([op, path])
    if op == "chmod":
        if not mode:
            return "error: chmod needs mode"
        return _run_fsop(["chmod", mode, path])
    if op == "chown":
        if not owner:
            return "error: chown needs owner"
        return _run_fsop(["chown", owner, path])
    if op in ("copy", "move"):
        if not dst:
            return f"error: {op} needs dst"
        return _run_fsop([op, path, dst])
    return f"error: unknown op {op}"
