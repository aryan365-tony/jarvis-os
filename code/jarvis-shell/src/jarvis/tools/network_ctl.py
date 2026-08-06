"""Network control (core).

Design note
-----------
Read-only queries (scan, status) are low tier.
Connections/toggles are medium tier (recoverable but disruptive).
Identifiers (ssid, vpn-name) are validated to prevent shell injection, though nmcli
itself is not a root-escalation path (NetworkManager allows users to toggle connections).
"""

from __future__ import annotations

import re
import subprocess

from .registry import register

_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")


def _run(args: list[str], timeout: int = 30) -> str:
    proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    return f"exit={proc.returncode}\n{(proc.stdout or '') + (proc.stderr or '')}"[:8000]


@register(
    "net_status",
    risk="low",
    domain="core",
    description="Show network device status and active connections.",
)
def net_status() -> str:
    out1 = _run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"])
    out2 = _run(["nmcli", "-t", "-f", "NAME,UUID,TYPE,DEVICE", "connection", "show", "--active"])
    return f"Devices:\n{out1}\n\nActive Connections:\n{out2}"


@register(
    "net_wifi_scan",
    risk="low",
    domain="core",
    description="Scan for available WiFi networks.",
)
def net_wifi_scan() -> str:
    return _run(["nmcli", "-t", "-f", "SSID,BSSID,SIGNAL,SECURITY", "device", "wifi", "list"])


@register(
    "net_wifi_connect",
    risk="medium",
    domain="core",
    description="Connect to a WiFi network. Returns connection result.",
    parameters={
        "type": "object",
        "properties": {
            "ssid": {"type": "string", "description": "The SSID of the WiFi network."},
            "password": {"type": "string", "description": "The password (if required)."},
        },
        "required": ["ssid"],
    },
)
def net_wifi_connect(ssid: str, password: str = "") -> str:
    if not _ID_RE.match(ssid):
        return "error: invalid SSID format"
    args = ["nmcli", "device", "wifi", "connect", ssid]
    if password:
        args.extend(["password", password])
    # The password is in args, so we use _run but we shouldn't log the password.
    # The standard _run doesn't log args, it just runs them and returns output.
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=60)
        # Avoid returning password in error output if nmcli decides to reflect it
        out = (proc.stdout or "") + (proc.stderr or "")
        if password:
            out = out.replace(password, "***")
        return f"exit={proc.returncode}\n{out}"[:8000]
    except Exception as e:
        return f"error: {e}"


@register(
    "net_hotspot_toggle",
    risk="medium",
    domain="core",
    description="Toggle a WiFi hotspot on or off.",
    parameters={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["on", "off"]},
            "ifname": {"type": "string", "description": "WiFi interface name (e.g. wlan0)"},
        },
        "required": ["action"],
    },
)
def net_hotspot_toggle(action: str, ifname: str = "wlan0") -> str:
    if not _ID_RE.match(ifname):
        return "error: invalid interface name"
    if action == "on":
        return _run(["nmcli", "device", "wifi", "hotspot", "ifname", ifname])
    return _run(["nmcli", "connection", "down", "Hotspot"])  # Default nmcli hotspot connection name


@register(
    "net_vpn_toggle",
    risk="medium",
    domain="core",
    description="Toggle a VPN connection on or off.",
    parameters={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["on", "off"]},
            "vpn_name": {"type": "string"},
        },
        "required": ["action", "vpn_name"],
    },
)
def net_vpn_toggle(action: str, vpn_name: str) -> str:
    if not _ID_RE.match(vpn_name):
        return "error: invalid VPN name"
    cmd = "up" if action == "on" else "down"
    return _run(["nmcli", "connection", cmd, vpn_name])
