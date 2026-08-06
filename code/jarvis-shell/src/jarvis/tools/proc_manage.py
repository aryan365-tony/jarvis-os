"""Process inspection and control via psutil.

Design note
-----------
* ``proc_list`` (low)    — read-only snapshot of processes (pid/name/cpu/mem).
* ``proc_kill`` (medium) — send a signal to a process. Recoverable (the process
                           can be restarted / is supervised), so no snapshot,
                           but it is a deliberate state change => medium.

Refuses to signal pid 1 and its own process group so the agent cannot take down
init or the shell hosting it. psutil is an optional dependency; the tools
degrade to a clear error if it is missing.
"""

from __future__ import annotations

import os
import signal as _signal

from .registry import register

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover - optional dep
    psutil = None  # type: ignore

_SIGNALS = {"TERM": _signal.SIGTERM, "KILL": _signal.SIGKILL, "HUP": _signal.SIGHUP}


@register(
    "proc_list",
    risk="low",
    description="List processes (pid, name, cpu%, mem%), optionally filtered by name.",
    parameters={
        "type": "object",
        "properties": {
            "filter": {"type": "string", "description": "Substring match on name."},
            "limit": {"type": "integer", "description": "Max rows (default 40)."},
        },
    },
)
def proc_list(filter: str = "", limit: int = 40) -> str:
    if psutil is None:
        return "error: psutil not available"
    rows = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        info = p.info
        name = info.get("name") or ""
        if filter and filter.lower() not in name.lower():
            continue
        rows.append(
            (info.get("cpu_percent") or 0.0, f"{info['pid']:>7} {name:<28} "
             f"cpu={info.get('cpu_percent') or 0:5.1f}% mem={info.get('memory_percent') or 0:4.1f}%")
        )
    rows.sort(key=lambda r: r[0], reverse=True)
    lines = [r[1] for r in rows[: max(1, limit)]]
    return "\n".join(lines) if lines else "no matching processes"


@register(
    "proc_kill",
    risk="medium",
    description="Send a signal (TERM/KILL/HUP) to a process by pid.",
    parameters={
        "type": "object",
        "properties": {
            "pid": {"type": "integer"},
            "signal": {"type": "string", "enum": ["TERM", "KILL", "HUP"]},
        },
        "required": ["pid"],
    },
)
def proc_kill(pid: int, signal: str = "TERM") -> str:
    if psutil is None:
        return "error: psutil not available"
    if pid <= 1:
        return "error: refusing to signal pid <= 1 (init)"
    if pid == os.getpid() or pid == os.getpgrp():
        return "error: refusing to signal the shell's own process"
    sig = _SIGNALS.get(signal.upper())
    if sig is None:
        return f"error: unsupported signal {signal}"
    try:
        os.kill(pid, sig)
    except ProcessLookupError:
        return f"error: no such process {pid}"
    except PermissionError:
        return f"error: not permitted to signal {pid}"
    return f"sent SIG{signal.upper()} to {pid}"
