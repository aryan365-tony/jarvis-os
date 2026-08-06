"""Scheduling control (core).

Design note
-----------
Uses systemd-run --user to schedule one-off or recurring commands.
Medium tier.
"""

from __future__ import annotations

import subprocess

from .registry import register


def _run(args: list[str]) -> str:
    proc = subprocess.run(args, capture_output=True, text=True, timeout=15)
    return f"exit={proc.returncode}\n{(proc.stdout or '') + (proc.stderr or '')}"[:8000]


@register(
    "task_schedule_once",
    risk="medium",
    domain="core",
    description="Schedule a command to run once after a delay.",
    parameters={
        "type": "object",
        "properties": {
            "delay": {"type": "string", "description": "Delay (e.g., '10s', '5m', '1h')."},
            "command": {"type": "string", "description": "Bash command to execute."},
        },
        "required": ["delay", "command"],
    },
)
def task_schedule_once(delay: str, command: str) -> str:
    args = ["systemd-run", "--user", f"--on-active={delay}", "--", "/bin/bash", "-c", command]
    return _run(args)


@register(
    "task_schedule_recurring",
    risk="medium",
    domain="core",
    description="Schedule a recurring command via systemd-run.",
    parameters={
        "type": "object",
        "properties": {
            "calendar": {"type": "string", "description": "systemd OnCalendar expression (e.g. 'hourly', '*-*-* 04:00:00')."},
            "command": {"type": "string", "description": "Bash command to execute."},
        },
        "required": ["calendar", "command"],
    },
)
def task_schedule_recurring(calendar: str, command: str) -> str:
    args = ["systemd-run", "--user", f"--on-calendar={calendar}", "--", "/bin/bash", "-c", command]
    return _run(args)
