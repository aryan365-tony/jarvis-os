"""Notification control (core).

Design note
-----------
Uses notify-send to broadcast D-Bus notifications to the compositor (e.g. mako).
"""

from __future__ import annotations

import subprocess

from .registry import register


def _run(args: list[str], timeout: int = 15) -> str:
    proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    return f"exit={proc.returncode}\n{(proc.stdout or '') + (proc.stderr or '')}"[:8000]


@register(
    "notify_send",
    risk="low",
    domain="core",
    description="Send a desktop notification to the user.",
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Notification title."},
            "body": {"type": "string", "description": "Notification body/message."},
        },
        "required": ["title", "body"],
    },
)
def notify_send(title: str, body: str) -> str:
    return _run(["notify-send", title, body])
