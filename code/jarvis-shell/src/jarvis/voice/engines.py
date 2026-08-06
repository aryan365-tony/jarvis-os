"""Voice engine detection and lazy construction (Phase 5).

Design note
-----------
Every speech component is an OPTIONAL accelerator. This module is the single
place that knows how to detect and build each engine, so the pipeline can stay
free of import-time dependencies and degrade cleanly to text when anything is
missing. Nothing here imports a heavy module at import time — engines are only
constructed on demand inside try/except.

Engines (all optional):
* wake  — openWakeWord ("hey jarvis")
* stt   — faster-whisper (sized from the GPU via llama/scripts/detect_gpu.py)
* tts   — piper
* audio — sounddevice (mic capture / playback)
"""

from __future__ import annotations

import importlib.util
import logging
import os
import subprocess

log = logging.getLogger("jarvis.voice.engines")


def available(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def audio_available() -> bool:
    return available("sounddevice") and available("numpy")


def wake_available() -> bool:
    return available("openwakeword") and audio_available()


def stt_available() -> bool:
    return available("faster_whisper") and audio_available()


def tts_available() -> bool:
    return available("piper") and audio_available()


def recommend_whisper_size() -> str:
    """Pick a faster-whisper model size from detected hardware.

    Reuses ``llama/scripts/detect_gpu.py`` (same heuristic that sizes the LLM
    backend). Falls back to the CPU-friendly ``base`` model on any error.
    """
    try:
        base = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        )
        script = os.path.join(base, "llama", "scripts", "detect_gpu.py")
        backend = subprocess.check_output(["python3", script], text=True, timeout=20).strip()
    except Exception:
        backend = "cpu"
    # GPU present -> a larger, more accurate model is affordable.
    return "small" if backend != "cpu" else "base"
