"""systemd service control via systemctl.

Design note
-----------
Reversible service actions (start/stop/restart/enable/disable) are ``medium``:
recoverable and frequently needed for autonomy, so they run instantly (no
snapshot). Read-only status/list is ``low``. Both route through the scoped
``sudo systemctl`` grant; unit names are validated to a safe charset.
"""

from __future__ import annotations

import re
import subprocess

from .registry import register

_UNIT_RE = re.compile(r"^[A-Za-z0-9@._:-]+$")
_ACTIONS = {"start", "stop", "restart", "reload", "enable", "disable"}


def _run(args: list[str], timeout: int = 60) -> str:
    proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    return f"exit={proc.returncode}\n{(proc.stdout or '') + (proc.stderr or '')}"[:8000]


@register(
    "svc_status",
    risk="low",
    description="Show status of a unit or list running units (read-only).",
    parameters={
        "type": "object",
        "properties": {"unit": {"type": "string", "description": "Unit name; omit to list."}},
    },
)
def svc_status(unit: str = "") -> str:
    if unit:
        if not _UNIT_RE.match(unit):
            return "error: invalid unit name"
        return _run(["systemctl", "status", "--no-pager", "--full", unit], timeout=30)
    return _run(["systemctl", "list-units", "--type=service", "--no-pager", "--no-legend"], timeout=30)


@register(
    "svc_control",
    risk="medium",
    description="Start/stop/restart/reload/enable/disable a systemd unit.",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": sorted(_ACTIONS),
            },
            "unit": {"type": "string"},
        },
        "required": ["action", "unit"],
    },
)
def svc_control(action: str, unit: str) -> str:
    if action not in _ACTIONS:
        return f"error: unsupported action {action}"
    if not _UNIT_RE.match(unit):
        return "error: invalid unit name"
    return _run(["sudo", "-n", "systemctl", action, unit], timeout=60)
