"""Voice configuration control (core).

Design note
-----------
Modifies the voice configuration in jarvis.toml or controls the microphone via wpctl.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from ..config import _resolve_path
from .registry import register


def _update_toml(section: str, key: str, value: str | bool) -> str:
    path = _resolve_path()
    if not path.exists():
        return "error: config file not found"
    
    content = path.read_text(errors="replace")
    if isinstance(value, str):
        replacement = f'{key} = "{value}"'
    else:
        replacement = f'{key} = {"true" if value else "false"}'

    pattern = rf'^({key}\s*=\s*).*$'
    if re.search(pattern, content, flags=re.MULTILINE):
        new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        path.write_text(new_content)
        return f"ok: set {key} to {value} (requires shell restart)"
    
    return f"error: {key} not found in config template"


def _run(args: list[str]) -> str:
    proc = subprocess.run(args, capture_output=True, text=True, timeout=15)
    return f"exit={proc.returncode}\n{(proc.stdout or '') + (proc.stderr or '')}"[:8000]


@register(
    "voice_set_wake_word",
    risk="low",
    domain="core",
    description="Set the wake word for the voice pipeline.",
    parameters={
        "type": "object",
        "properties": {
            "wake_word": {"type": "string"},
        },
        "required": ["wake_word"],
    },
)
def voice_set_wake_word(wake_word: str) -> str:
    return _update_toml("voice", "wake_word", wake_word)


@register(
    "voice_set_tts_voice",
    risk="low",
    domain="core",
    description="Set the text-to-speech voice model name.",
    parameters={
        "type": "object",
        "properties": {
            "tts_voice": {"type": "string"},
        },
        "required": ["tts_voice"],
    },
)
def voice_set_tts_voice(tts_voice: str) -> str:
    return _update_toml("voice", "tts_voice", tts_voice)


@register(
    "voice_mute",
    risk="low",
    domain="core",
    description="Mute or unmute the system microphone.",
    parameters={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["mute", "unmute", "toggle"]},
        },
        "required": ["action"],
    },
)
def voice_mute(action: str) -> str:
    val = "1" if action == "mute" else "0" if action == "unmute" else "toggle"
    return _run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", val])
