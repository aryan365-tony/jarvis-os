"""Voice pipeline: wake -> listen -> transcribe -> agent -> speak (Phase 5).

Design note
-----------
This is the async state machine that turns speech into an agent turn and speaks
the reply back, while driving the orb. It is deliberately engine-agnostic: the
wake detector, transcriber, and speaker are injected (real engines from
``engines.py`` in production, fakes in tests), so the *logic* — including
barge-in — is fully unit-testable without audio hardware.

State cycle (published as ``VoiceActivity`` on ``VOICE_ACTIVITY``):

    IDLE ──wake──▶ LISTENING ──speech end──▶ THINKING ──first token──▶ SPEAKING
      ▲                                                                   │
      └──────────────────────── reply done / barge-in ────────────────────┘

Barge-in: while SPEAKING, if the wake/VAD detector fires again, TTS is cancelled
immediately and we jump straight back to LISTENING — the user can always
interrupt. Voice and text share the SAME agent, so history is unified.

Everything is optional: if no engines are present the pipeline reports itself
unavailable and never blocks the text UI.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Protocol

from ..eventbus import EventBus
from ..events import (
    LOG,
    VOICE_ACTIVITY,
    Level,
    LogLine,
    VoiceActivity,
    VoicePhase,
)

log = logging.getLogger("jarvis.voice.pipeline")


class WakeDetector(Protocol):
    async def wait_for_wake(self) -> None: ...


class Transcriber(Protocol):
    async def listen_and_transcribe(self) -> str: ...


class Speaker(Protocol):
    async def speak(self, text_stream: "asyncio.Queue[str | None]") -> None: ...
    def barge_in_detected(self) -> bool: ...


# The agent front-end: given a transcript + a token sink, run one turn.
AgentTurn = Callable[[str, Callable[[str], Awaitable[None]]], Awaitable[str]]


class VoicePipeline:
    def __init__(
        self,
        bus: EventBus,
        wake: WakeDetector,
        stt: Transcriber,
        tts: Speaker,
        agent_turn: AgentTurn,
    ) -> None:
        self._bus = bus
        self._wake = wake
        self._stt = stt
        self._tts = tts
        self._agent_turn = agent_turn
        self._stop = asyncio.Event()

    def _activity(self, phase: VoicePhase, level: float = 0.0, text: str = "") -> None:
        self._bus.publish(VOICE_ACTIVITY, VoiceActivity(phase=phase, level=level, text=text))

    def request_stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        """Main loop. Returns only when stopped."""
        self._activity(VoicePhase.IDLE)
        while not self._stop.is_set():
            try:
                await self._one_interaction()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("voice interaction failed; returning to idle")
                self._bus.publish(
                    LOG, LogLine("voice", Level.WARNING, "voice cycle error; recovered")
                )
                self._activity(VoicePhase.IDLE)
                await asyncio.sleep(0.5)

    async def _one_interaction(self) -> None:
        # 1) Wait for the wake word.
        self._activity(VoicePhase.IDLE)
        await self._wake.wait_for_wake()
        if self._stop.is_set():
            return

        # 2) Listen + transcribe.
        self._activity(VoicePhase.LISTENING)
        transcript = (await self._stt.listen_and_transcribe()).strip()
        if not transcript:
            self._activity(VoicePhase.IDLE)
            return
        self._activity(VoicePhase.THINKING, text=transcript)

        # 3) Run the agent turn, streaming tokens BOTH to the caption and to the
        #    TTS queue so speech starts as soon as the first token lands.
        token_q: "asyncio.Queue[str | None]" = asyncio.Queue()
        spoke_first = asyncio.Event()

        async def on_token(tok: str) -> None:
            if not spoke_first.is_set():
                spoke_first.set()
                self._activity(VoicePhase.SPEAKING)
            await token_q.put(tok)

        speak_task = asyncio.create_task(self._tts.speak(token_q))
        try:
            await self._agent_turn(transcript, on_token)
        finally:
            await token_q.put(None)  # sentinel: end of stream

        # 4) Wait for speech to finish OR a barge-in to cut it short.
        while not speak_task.done():
            if self._barge_in():
                speak_task.cancel()
                self._bus.publish(
                    LOG, LogLine("voice", Level.INFO, "barge-in: interrupting speech")
                )
                break
            await asyncio.sleep(0.05)
        try:
            await speak_task
        except asyncio.CancelledError:
            pass

        self._activity(VoicePhase.IDLE)

    def _barge_in(self) -> bool:
        """Detect a user interruption while speaking.

        Prefer the wake/VAD detector (it owns the mic energy) and fall back to
        the speaker's own signal; either firing lets the user cut speech off.
        """
        for src in (self._wake, self._tts):
            fn = getattr(src, "barge_in_detected", None)
            try:
                if callable(fn) and fn():
                    return True
            except Exception:
                pass
        return False
