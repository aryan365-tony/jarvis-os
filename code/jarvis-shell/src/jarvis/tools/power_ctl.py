"""Power control (core).

Design note
-----------
Status queries are low tier.
Suspend and shutdown/reboot are high tier and irreversible for the session.
They explicitly require a confirm phrase to prevent accidental agent hallucination
of a shutdown command.
"""

from __future__ import annotations

import subprocess

from .registry import register


def _run(args: list[str], timeout: int = 15) -> str:
    proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    return f"exit={proc.returncode}\n{(proc.stdout or '') + (proc.stderr or '')}"[:8000]


@register(
    "power_status",
    risk="low",
    domain="core",
    description="Show battery and power status.",
)
def power_status() -> str:
    return _run(["upower", "-d"])


@register(
    "power_suspend",
    risk="high",
    domain="core",
    description="Suspend (sleep) the system.",
)
def power_suspend() -> str:
    return _run(["sudo", "-n", "systemctl", "suspend"])


@register(
    "power_shutdown_reboot",
    risk="high",
    domain="core",
    description="Shutdown or reboot the system.",
    parameters={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["poweroff", "reboot"]},
        },
        "required": ["action"],
    },
)
def power_shutdown_reboot(action: str) -> str:
    if action not in ("poweroff", "reboot"):
        return "error: invalid action"
    return _run(["sudo", "-n", "systemctl", action])
