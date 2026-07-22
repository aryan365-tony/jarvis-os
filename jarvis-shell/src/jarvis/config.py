"""Typed configuration loaded once from ``config/jarvis.toml``.

Design note
-----------
Previously three modules each ran ``cfg = load_config()`` at import time, doing
redundant file I/O and making tests hard. Now there is one cached accessor
(``get_config``) and every section has safe defaults, so a partial or missing
TOML never crashes startup — the shell degrades gracefully instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from functools import lru_cache
from pathlib import Path
from typing import Any

try:  # Python 3.11+ ships tomllib in the stdlib.
    import tomllib as _toml
except ModuleNotFoundError:  # pragma: no cover - fallback for < 3.11
    import tomli as _toml  # type: ignore[no-redef]


@dataclass
class LLMConfig:
    endpoint: str = "http://127.0.0.1:8080/v1/chat/completions"
    health_endpoint: str = "http://127.0.0.1:8080/health"
    model_name: str = "gemma-4b-it"
    max_context: int = 8192
    request_timeout_s: int = 60
    system_prompt: str = (
        "You are Jarvis, a concise, proactive on-device assistant. "
        "Prefer short, clear answers. Use tools only when they materially help. "
        "Never invent tool results."
    )


@dataclass
class MemoryConfig:
    db_path: str = "/home/jarvisuser/.local/share/jarvis/memory.sqlite3"
    core_memory_max_tokens: int = 1200
    # At-rest encryption (Phase 1). The conversation DB holds full history and
    # runs with reduced human oversight. Two layers are supported:
    #   * ``encrypt_at_rest`` -> use SQLCipher when the pysqlcipher3 driver is
    #     present, keyed from ``key_path`` (auto-generated 0600 if missing).
    #   * filesystem LUKS on @home (installer ``ENCRYPT_HOME=1``) as the default,
    #     dependency-free option for the offline image.
    # Regardless of layer, the DB file is always chmod 0600, owner-only.
    encrypt_at_rest: bool = False
    key_path: str = "/var/lib/jarvis/memory.key"


@dataclass
class PolicyConfig:
    # Phase 2: the network allowlist was removed — the image is offline by
    # design (no egress path exists), so an allowlist was dead configuration.
    irreversible_requires_confirm: bool = True
    # Raised for the larger Phase 2 tool surface but still a hard ceiling; the
    # registry additionally enforces its own PER_TURN_TOOL_BUDGET.
    max_tool_calls_per_turn: int = 12
    max_turns_per_session_task: int = 25
    # High-tier fs mutations are confined here; anything inside runs low-tier.
    fs_scratch_dir: str = "/home/jarvisuser/scratch"


@dataclass
class UIConfig:
    reduced_motion: bool = False
    high_contrast: bool = False
    text_scale: float = 1.0
    show_status_panel_on_start: bool = False


@dataclass
class VoiceConfig:
    # Voice is optional and initialises in the background; text is always the
    # guaranteed fallback. ``enabled`` lets an image ship without voice at all.
    enabled: bool = True
    wake_word: str = "jarvis"
    stt_model: str = ""  # empty => auto-detect / unavailable
    tts_voice: str = ""


@dataclass
class BootConfig:
    # Keep model offline by default so OS boot/debug does not depend on GGUF.
    model_auto_start: bool = False
    # How long the readiness poller waits for the model before flagging it
    # degraded (the UI stays fully interactive the entire time).
    model_ready_timeout_s: int = 120
    health_poll_interval_s: float = 1.0


@dataclass
class Config:
    llm: LLMConfig = field(default_factory=LLMConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    boot: BootConfig = field(default_factory=BootConfig)


def _filter(cls: type, data: dict[str, Any]) -> dict[str, Any]:
    """Keep only keys that exist on the dataclass so unknown TOML keys are ignored."""
    known = {f.name for f in fields(cls)}
    return {k: v for k, v in data.items() if k in known}


def _resolve_path() -> Path:
    p = Path("config/jarvis.toml")
    if p.exists():
        return p
    return Path(__file__).resolve().parents[3] / "config" / "jarvis.toml"


def load_config(path: str | None = None) -> Config:
    p = Path(path) if path else _resolve_path()
    data: dict[str, Any] = {}
    if p.exists():
        with open(p, "rb") as f:
            data = _toml.load(f)
    return Config(
        llm=LLMConfig(**_filter(LLMConfig, data.get("llm", {}))),
        memory=MemoryConfig(**_filter(MemoryConfig, data.get("memory", {}))),
        policy=PolicyConfig(**_filter(PolicyConfig, data.get("policy", {}))),
        ui=UIConfig(**_filter(UIConfig, data.get("ui", {}))),
        voice=VoiceConfig(**_filter(VoiceConfig, data.get("voice", {}))),
        boot=BootConfig(**_filter(BootConfig, data.get("boot", {}))),
    )


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Cached process-wide config. Use this instead of re-loading."""
    return load_config()
