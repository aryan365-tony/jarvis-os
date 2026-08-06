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
    parameters={
        "type": "object",
        "properties": {
            "confirm_phrase": {
                "type": "string",
                "description": "Must be exactly: 'I understand this will suspend the system'"
            }
        },
        "required": ["confirm_phrase"],
    },
)
def power_suspend(confirm_phrase: str) -> str:
    if confirm_phrase != "I understand this will suspend the system":
        return "error: missing or incorrect confirm_phrase"
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
            "confirm_phrase": {
                "type": "string",
                "description": "Must be exactly: 'I understand this will terminate the session'"
            }
        },
        "required": ["action", "confirm_phrase"],
    },
)
def power_shutdown_reboot(action: str, confirm_phrase: str) -> str:
    if confirm_phrase != "I understand this will terminate the session":
        return "error: missing or incorrect confirm_phrase"
    if action not in ("poweroff", "reboot"):
        return "error: invalid action"
    return _run(["sudo", "-n", "systemctl", action])
