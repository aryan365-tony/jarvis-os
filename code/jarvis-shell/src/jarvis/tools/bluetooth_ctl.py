"""Bluetooth control (core).

Design note
-----------
Uses bluetoothctl. Scan is low tier, pairing and connection are medium.
MAC addresses are validated via a strict regex to prevent injection.
"""

from __future__ import annotations

import re
import subprocess

from .registry import register

_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$")


def _run(args: list[str], timeout: int = 30) -> str:
    proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    return f"exit={proc.returncode}\n{(proc.stdout or '') + (proc.stderr or '')}"[:8000]


@register(
    "bt_scan",
    risk="low",
    domain="core",
    description="Scan for nearby Bluetooth devices for 10 seconds.",
)
def bt_scan() -> str:
    # bluetoothctl --timeout N scan on
    return _run(["bluetoothctl", "--timeout", "10", "scan", "on"], timeout=20)


@register(
    "bt_pair",
    risk="medium",
    domain="core",
    description="Pair with a Bluetooth device using its MAC address.",
    parameters={
        "type": "object",
        "properties": {
            "mac": {"type": "string", "description": "MAC address of the device."},
        },
        "required": ["mac"],
    },
)
def bt_pair(mac: str) -> str:
    if not _MAC_RE.match(mac):
        return "error: invalid MAC address format"
    return _run(["bluetoothctl", "pair", mac])


@register(
    "bt_connect",
    risk="medium",
    domain="core",
    description="Connect or disconnect a paired Bluetooth device.",
    parameters={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["connect", "disconnect"]},
            "mac": {"type": "string", "description": "MAC address of the device."},
        },
        "required": ["action", "mac"],
    },
)
def bt_connect(action: str, mac: str) -> str:
    if not _MAC_RE.match(mac):
        return "error: invalid MAC address format"
    return _run(["bluetoothctl", action, mac])
