"""Media and audio control (core).

Design note
-----------
Uses playerctl for MPRIS playback control and wpctl for wireplumber/pipewire audio control.
All actions are low tier.
"""

from __future__ import annotations

import re
import subprocess

from .registry import register

_FLOAT_RE = re.compile(r"^[0-9]+(\.[0-9]+)?$")
_INT_RE = re.compile(r"^[0-9]+$")


def _run(args: list[str], timeout: int = 15) -> str:
    proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    return f"exit={proc.returncode}\n{(proc.stdout or '') + (proc.stderr or '')}"[:8000]


@register(
    "media_play_pause",
    risk="low",
    domain="core",
    description="Toggle play/pause for active media players.",
)
def media_play_pause() -> str:
    return _run(["playerctl", "play-pause"])


@register(
    "media_next_prev",
    risk="low",
    domain="core",
    description="Skip to next or previous media track.",
    parameters={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["next", "previous"]},
        },
        "required": ["action"],
    },
)
def media_next_prev(action: str) -> str:
    return _run(["playerctl", action])


@register(
    "volume_set",
    risk="low",
    domain="core",
    description="Set the default audio output volume (0.0 to 1.0).",
    parameters={
        "type": "object",
        "properties": {
            "level": {"type": "string", "description": "Volume level (e.g., '0.5' for 50%)."},
        },
        "required": ["level"],
    },
)
def volume_set(level: str) -> str:
    if not _FLOAT_RE.match(level):
        return "error: invalid volume level"
    val = float(level)
    if val < 0.0 or val > 1.5:
        return "error: volume must be between 0.0 and 1.5"
    return _run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", level])


@register(
    "audio_output_switch",
    risk="low",
    domain="core",
    description="Switch default audio output device. First run without ID to list devices.",
    parameters={
        "type": "object",
        "properties": {
            "device_id": {"type": "string", "description": "Device ID to switch to. Omit to list."},
        },
    },
)
def audio_output_switch(device_id: str = "") -> str:
    if not device_id:
        return _run(["wpctl", "status"])
    if not _INT_RE.match(device_id):
        return "error: invalid device ID format"
    return _run(["wpctl", "set-default", device_id])
