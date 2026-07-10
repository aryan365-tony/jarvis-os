"""Voice subsystem (text-first, background-initialising).

Design note
-----------
Voice is treated as an *optional accelerator*, never a gate. On start we probe
for STT/TTS availability in the background and publish status events. Because no
speech engine ships yet, the honest, non-blocking behaviour is:

    INITIALIZING  (probing, UI already usable via text)
    -> UNAVAILABLE  (no engine found -> text fallback, clearly indicated)
    -> READY        (engine present -> voice offered, seamless switch)

This gives the "voice initialises in background, text works immediately, switch
seamlessly when ready" experience with a clean seam for real STT/TTS later.
"""

from __future__ import annotations

import asyncio
import importlib.util

from ..config import get_config
from ..eventbus import EventBus
from ..events import LOG, VOICE_STATUS, Level, LogLine, ServiceState, ServiceStatus


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


class VoiceService:
    """Owns voice state and exposes a seam for real STT/TTS engines."""

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._cfg = get_config()
        self._state = ServiceState.UNAVAILABLE
        self._task: asyncio.Task | None = None

    @property
    def state(self) -> ServiceState:
        return self._state

    @property
    def available(self) -> bool:
        return self._state in (ServiceState.READY, ServiceState.DEGRADED)

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._probe(), name="voice-probe")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def _emit(self, state: ServiceState, detail: str) -> None:
        self._state = state
        self._bus.publish(VOICE_STATUS, ServiceStatus("voice", state, detail))
        self._bus.publish(LOG, LogLine("voice", Level.INFO, f"voice {state.value}: {detail}"))

    async def _probe(self) -> None:
        if not self._cfg.voice.enabled:
            self._emit(ServiceState.UNAVAILABLE, "disabled in config")
            return

        self._emit(ServiceState.INITIALIZING, "probing audio + speech engines")
        # Yield so the UI paints before we do the (cheap) capability check.
        await asyncio.sleep(0)

        has_stt = any(_module_available(m) for m in ("vosk", "faster_whisper", "whisper"))
        has_tts = any(_module_available(m) for m in ("piper", "TTS")) or _module_available("subprocess")

        if has_stt and has_tts:
            # Real engines would be constructed here; kept as a seam for now.
            self._emit(ServiceState.READY, "speech engines available")
        else:
            missing = "STT" if not has_stt else "TTS"
            self._emit(
                ServiceState.UNAVAILABLE,
                f"{missing} engine not installed — using text (voice can be enabled later)",
            )
