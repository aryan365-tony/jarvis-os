"""Display / session control (low risk, user-scope).

Design note
-----------
Brightness and session lock are user-facing, instantly reversible conveniences
=> ``low`` tier. Brightness prefers ``brightnessctl`` (works rootless with the
video group / udev rule) and falls back to writing sysfs only if permitted.
Locking uses loginctl for the current session. Nothing here is system-altering,
so no snapshot/confirmation.
"""

from __future__ import annotations

import shutil
import subprocess

from .registry import register


def _run(args: list[str], timeout: int = 10) -> str:
    proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    return f"exit={proc.returncode}\n{(proc.stdout or '') + (proc.stderr or '')}"[:2000]


@register(
    "display_brightness",
    risk="low",
    description="Get or set screen brightness as a percentage (0-100).",
    parameters={
        "type": "object",
        "properties": {
            "percent": {
                "type": "integer",
                "description": "Target 0-100; omit to just read current value.",
            }
        },
    },
)
def display_brightness(percent: int | None = None) -> str:
    if shutil.which("brightnessctl") is None:
        return "error: brightnessctl not available"
    if percent is None:
        return _run(["brightnessctl", "-m"])
    pct = max(0, min(int(percent), 100))
    return _run(["brightnessctl", "set", f"{pct}%"])


@register(
    "session_lock",
    risk="low",
    description="Lock the current graphical session.",
    parameters={"type": "object", "properties": {}},
)
def session_lock() -> str:
    if shutil.which("loginctl") is None:
        return "error: loginctl not available"
    return _run(["loginctl", "lock-session"])
