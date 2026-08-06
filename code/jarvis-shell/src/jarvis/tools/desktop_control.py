"""Desktop GUI control (desktop_control).

Design note
-----------
Uses Wayland protocols via wlrctl for window management and wtype/ydotool for injection.
"""

from __future__ import annotations

import subprocess

from .registry import register


def _run(args: list[str], timeout: int = 15) -> str:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return f"exit={proc.returncode}\n{(proc.stdout or '') + (proc.stderr or '')}"[:8000]
    except FileNotFoundError:
        return f"error: command '{args[0]}' not found. The tool is likely not installed."


@register(
    "desktop_list_windows",
    risk="low",
    domain="desktop_control",
    description="List active windows on the Wayland desktop.",
)
def desktop_list_windows() -> str:
    return _run(["wlrctl", "window", "list"])


@register(
    "desktop_focus_window",
    risk="medium",
    domain="desktop_control",
    description="Focus a specific window by its app_id or title.",
    parameters={
        "type": "object",
        "properties": {
            "match": {"type": "string", "description": "App ID or title substring."},
        },
        "required": ["match"],
    },
)
def desktop_focus_window(match: str) -> str:
    return _run(["wlrctl", "window", "focus", match])


@register(
    "desktop_accessibility_type",
    risk="high",
    domain="desktop_control",
    description="Type text into the currently focused window.",
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string"},
        },
        "required": ["text"],
    },
)
def desktop_accessibility_type(text: str) -> str:
    return _run(["wtype", text])


@register(
    "desktop_accessibility_click",
    risk="high",
    domain="desktop_control",
    description="Click a mouse button at the current pointer location.",
    parameters={
        "type": "object",
        "properties": {
            "button": {"type": "string", "enum": ["left", "right", "middle"]},
        },
        "required": ["button"],
    },
)
def desktop_accessibility_click(button: str) -> str:
    # ydotool uses numeric buttons (1=left, 2=middle, 3=right)
    # ydotool click 0xC0 (left), 0xC1 (right)
    btn_code = "0xC0" if button == "left" else "0xC1" if button == "right" else "0xC2"
    return _run(["ydotool", "click", btn_code])
