"""Read-only system diagnostics (all low risk).

Design note
-----------
These let the agent understand system state without changing anything:
journalctl, dmesg, df, free, uptime/loadavg. Everything is read-only => ``low``
tier, no snapshot, no confirmation. Output is size-capped so a huge log cannot
blow the context window.
"""

from __future__ import annotations

import re
import shutil
import subprocess

from .registry import register

_UNIT_RE = re.compile(r"^[A-Za-z0-9@._:-]+$")
_CAP = 8000


def _run(args: list[str], timeout: int = 30) -> str:
    proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    return ((proc.stdout or "") + (proc.stderr or ""))[:_CAP] or "(no output)"


@register(
    "diag_journal",
    risk="low",
    description="Read recent journald logs, optionally for one unit.",
    parameters={
        "type": "object",
        "properties": {
            "unit": {"type": "string"},
            "lines": {"type": "integer", "description": "Tail N lines (default 80)."},
        },
    },
)
def diag_journal(unit: str = "", lines: int = 80) -> str:
    n = str(max(1, min(lines, 1000)))
    args = ["journalctl", "--no-pager", "-n", n]
    if unit:
        if not _UNIT_RE.match(unit):
            return "error: invalid unit name"
        args += ["-u", unit]
    return _run(args)


@register(
    "diag_dmesg",
    risk="low",
    description="Read the kernel ring buffer (dmesg).",
    parameters={"type": "object", "properties": {
        "lines": {"type": "integer", "description": "Tail N lines (default 80)."}}},
)
def diag_dmesg(lines: int = 80) -> str:
    out = _run(["dmesg", "--color=never"])
    tail = out.splitlines()[-max(1, min(lines, 1000)):]
    return "\n".join(tail) or "(no output)"


@register(
    "diag_resources",
    risk="low",
    description="Report disk usage, memory, and load (df / free / uptime).",
    parameters={"type": "object", "properties": {}},
)
def diag_resources() -> str:
    parts = []
    if shutil.which("df"):
        parts.append("== df -h ==\n" + _run(["df", "-h"]))
    if shutil.which("free"):
        parts.append("== free -h ==\n" + _run(["free", "-h"]))
    if shutil.which("uptime"):
        parts.append("== uptime ==\n" + _run(["uptime"]))
    return "\n\n".join(parts)[:_CAP] or "(no tools available)"
