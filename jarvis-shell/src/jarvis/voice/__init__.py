"""Voice subsystem (text-first, background-initialising).

Design note
-----------
Voice is treated as an *optional accelerator*, never a gate. On start we probe
for STT/TTS/wake availability in the background and publish status events. When
every engine is present AND an agent turn callback has been wired by the UI, the
real :class:`~jarvis.voice.pipeline.VoicePipeline` runs (wake → listen → the
SHARED agent → speak, with barge-in). Otherwise we degrade honestly to text:

    INITIALIZING  (probing, UI already usable via text)
    -> UNAVAILABLE  (engine/mic missing -> text fallback, clearly indicated)
    -> READY        (engines present + agent wired -> voice pipeline running)

Voice and text drive the *same* agent, so history is unified.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from ..config import get_config
from ..eventbus import EventBus
from ..events import LOG, VOICE_STATUS, Level, LogLine, ServiceState, ServiceStatus
from . import engines

log = logging.getLogger("jarvis.voice")

# (transcript, on_token) -> final_text. Wired by the UI to the shared agent.
AgentTurn = Callable[[str, Callable[[str], Awaitable[None]]], Awaitable[str]]


class VoiceService:
    """Owns voice state and, when possible, runs the real speech pipeline."""

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._cfg = get_config()
        self._state = ServiceState.UNAVAILABLE
        self._task: asyncio.Task | None = None
        self._agent_turn: AgentTurn | None = None
        self._pipeline = None  # type: ignore[var-annotated]

    @property
    def state(self) -> ServiceState:
        return self._state

    @property
    def available(self) -> bool:
        return self._state in (ServiceState.READY, ServiceState.DEGRADED)

    def set_agent_turn(self, agent_turn: AgentTurn) -> None:
        """Wire the shared agent so voice input flows through the same pipeline."""
        self._agent_turn = agent_turn

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self.run(), name="voice-probe")

    async def run(self) -> None:
        """Run the voice pipeline in the caller's task (used by the supervisor)."""
        if not self._cfg.voice.enabled:
            self._emit(ServiceState.UNAVAILABLE, "disabled in config")
            return

        self._emit(ServiceState.INITIALIZING, "probing audio + speech engines")
        await asyncio.sleep(0)  # let the UI paint first

        ready = (
            engines.wake_available()
            and engines.stt_available()
            and engines.tts_available()
        )
        if not ready or self._agent_turn is None:
            reason = self._degradation_reason()
            self._emit(ServiceState.UNAVAILABLE, reason)
            return

        try:
            self._pipeline = self._build_pipeline()
        except Exception as e:
            log.exception("voice engine construction failed")
            self._emit(ServiceState.DEGRADED, f"engine init failed: {e} — using text")
            return

        self._emit(ServiceState.READY, "speech pipeline active")
        try:
            await self._pipeline.run()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("voice pipeline crashed")
            self._emit(ServiceState.DEGRADED, "pipeline crashed — text still available")
            raise  # let the supervisor restart with backoff

    def _degradation_reason(self) -> str:
        if self._agent_turn is None:
            return "agent not wired yet — text available"
        missing = []
        if not engines.wake_available():
            missing.append("wake")
        if not engines.stt_available():
            missing.append("STT")
        if not engines.tts_available():
            missing.append("TTS")
        return f"{'/'.join(missing)} engine not installed — using text (enable later)"

    def _build_pipeline(self):
        from .engines_impl import OpenWakeWordDetector, PiperSpeaker, WhisperTranscriber
        from .pipeline import VoicePipeline

        assert self._agent_turn is not None
        wake = OpenWakeWordDetector(self._cfg.voice.wake_word)
        stt = WhisperTranscriber()
        tts = PiperSpeaker(self._cfg.voice.tts_voice)
        return VoicePipeline(self._bus, wake, stt, tts, self._agent_turn)

    async def stop(self) -> None:
        if self._pipeline is not None:
            try:
                self._pipeline.request_stop()
            except Exception:
                pass
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
