"""Qt bridge: exposes the Python runtime to QML via Properties and Signals.

Design note
-----------
This QObject is registered as a context property in the QML engine, making all
backend state (model readiness, voice status, conversation, logs) available to
QML bindings declaratively. The bridge:

* Owns the ``Runtime`` and ``ConversationAgent``.
* Runs an asyncio event-pump that drains the ``EventBus`` and emits Qt signals.
* Provides Q_INVOKABLE methods for QML to send user text and control the UI.
* Keeps the async loop alive via ``qasync`` so existing async services
  (readiness poller, voice probe, httpx streaming) work unchanged.

Nothing in this module imports any UI widget — it is a pure data conduit.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from PyQt6.QtCore import (
    QObject,
    pyqtProperty,
    pyqtSignal,
    pyqtSlot,
    QVariant,
)

from .agent import ConversationAgent
from .audit.chain import audit_log
from .events import (
    HEALTH,
    LOG,
    MODEL_STATUS,
    VOICE_ACTIVITY,
    VOICE_STATUS,
    Level,
    LogLine,
    ServiceState,
    ServiceStatus,
    VoiceActivity,
)
from .memory import store
from .runtime import Runtime
from .tools.registry import get_risk_tier

log = logging.getLogger("jarvis.bridge")


class JarvisBridge(QObject):
    """Singleton QObject registered as ``jarvis`` in the QML context."""

    # ── Signals (QML listens to these) ──────────────────────────────────
    modelStateChanged = pyqtSignal(str)
    modelOnlineChanged = pyqtSignal(bool)
    voiceStateChanged = pyqtSignal(str)
    voiceActivity = pyqtSignal(str, float, str)  # phase, level(0..1), caption
    logAppended = pyqtSignal(str, str, str)  # source, level, message
    conversationAppended = pyqtSignal(str, str)  # role, text
    streamingDelta = pyqtSignal(str)  # chunk of assistant text
    streamingStarted = pyqtSignal()
    streamingFinished = pyqtSignal(str)  # full final text
    notificationPosted = pyqtSignal(str, str)  # title, body
    clockTick = pyqtSignal(str)  # HH:MM

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._runtime = Runtime()
        self._agent: ConversationAgent | None = None
        self._model_state = self._runtime.readiness.state.value
        self._model_online = self._runtime.readiness.desired_online
        self._voice_state = ServiceState.INITIALIZING.value
        self._pump_task: asyncio.Task | None = None
        self._clock_task: asyncio.Task | None = None

    # ── Properties (QML can bind to these) ──────────────────────────────
    @pyqtProperty(str, notify=modelStateChanged)
    def modelState(self) -> str:
        return self._model_state

    @pyqtProperty(bool, notify=modelOnlineChanged)
    def modelOnline(self) -> bool:
        return self._model_online

    @pyqtProperty(str, notify=voiceStateChanged)
    def voiceState(self) -> str:
        return self._voice_state

    # ── Lifecycle ───────────────────────────────────────────────────────
    def start(self) -> None:
        """Called once after the QML engine is loaded. Kicks off all services."""
        self._agent = ConversationAgent(
            on_task=self._on_task,
        )
        # Voice and text share this one agent: route voice transcripts through
        # the same turn, echoing them into the conversation view + token stream.
        self._runtime.voice.set_agent_turn(self._voice_agent_turn)
        self._runtime.start_background()
        self._pump_task = asyncio.create_task(self._pump())
        self._clock_task = asyncio.create_task(self._clock_loop())
        log.info("bridge started, background services launched")

    async def shutdown(self) -> None:
        if self._pump_task:
            self._pump_task.cancel()
        if self._clock_task:
            self._clock_task.cancel()
        await self._runtime.shutdown()
        if self._agent:
            await self._agent.aclose()

    # ── QML-callable methods ────────────────────────────────────────────
    @pyqtSlot(str)
    def sendMessage(self, text: str) -> None:
        """Called from QML when the user submits text."""
        text = text.strip()
        if not text:
            return
        self.conversationAppended.emit("user", text)
        asyncio.create_task(self._handle_user(text))

    @pyqtSlot(result=bool)
    def isOnboarded(self) -> bool:
        return bool(store.load_core_memory().get("onboarded"))

    @pyqtSlot()
    def completeOnboarding(self) -> None:
        store.set_core_memory("onboarded", "1")

    @pyqtSlot(bool)
    def setModelOnline(self, enabled: bool) -> None:
        self._runtime.readiness.set_desired_online(enabled)
        if self._model_online != bool(enabled):
            self._model_online = bool(enabled)
            self.modelOnlineChanged.emit(self._model_online)

    # ── Internal: conversation handling ─────────────────────────────────
    async def _handle_user(self, text: str) -> None:
        self.streamingStarted.emit()
        buffer: list[str] = []

        async def on_delta(chunk: str) -> None:
            buffer.append(chunk)
            self.streamingDelta.emit(chunk)

        assert self._agent is not None
        try:
            await self._agent.send(text, on_delta)
        except Exception as e:
            log.exception("agent turn failed")
            error_msg = f"\n[error: {e}]"
            buffer.append(error_msg)
            self.streamingDelta.emit(error_msg)
        finally:
            full_text = "".join(buffer)
            self.streamingFinished.emit(full_text)
            self.conversationAppended.emit("assistant", full_text)

    # ── Internal: event pump ────────────────────────────────────────────
    async def _pump(self) -> None:
        """Drain the runtime event bus and re-emit as Qt signals."""
        sub = self._runtime.bus.subscribe(
            MODEL_STATUS, VOICE_STATUS, VOICE_ACTIVITY, LOG, HEALTH
        )
        with sub:
            async for topic, payload in sub:
                try:
                    if topic == MODEL_STATUS and isinstance(payload, ServiceStatus):
                        self._model_state = payload.state.value
                        self.modelStateChanged.emit(payload.state.value)
                        online = self._runtime.readiness.desired_online
                        if self._model_online != online:
                            self._model_online = online
                            self.modelOnlineChanged.emit(online)
                    elif topic == VOICE_STATUS and isinstance(payload, ServiceStatus):
                        self._voice_state = payload.state.value
                        self.voiceStateChanged.emit(payload.state.value)
                    elif topic == VOICE_ACTIVITY and isinstance(payload, VoiceActivity):
                        self.voiceActivity.emit(
                            payload.phase.value, float(payload.level), payload.text
                        )
                    elif topic == LOG and isinstance(payload, LogLine):
                        self.logAppended.emit(
                            payload.source, payload.level.value, payload.message
                        )
                except Exception:
                    log.exception("bridge pump error")

    async def _clock_loop(self) -> None:
        """Emit time every second for the HUD clock."""
        while True:
            self.clockTick.emit(datetime.now().strftime("%H:%M"))
            await asyncio.sleep(1.0)



    # ── Voice <-> shared agent bridge (Phase 5) ─────────────────────────
    async def _voice_agent_turn(self, transcript: str, on_token):
        """Run a spoken turn through the SAME agent as text, mirroring it to UI.

        The voice pipeline streams tokens to TTS via ``on_token``; here we also
        echo the transcript and streamed reply into the on-screen conversation
        so speech and text share one visible, unified history.
        """
        self.conversationAppended.emit("user", transcript)
        self.streamingStarted.emit()
        buffer: list[str] = []

        async def sink(tok: str) -> None:
            buffer.append(tok)
            self.streamingDelta.emit(tok)
            await on_token(tok)  # keep feeding TTS

        assert self._agent is not None
        try:
            final = await self._agent.send(transcript, sink)
        except Exception as e:
            log.exception("voice agent turn failed")
            final = f"[error: {e}]"
            self.streamingDelta.emit(final)
        full = "".join(buffer) or final
        self.streamingFinished.emit(full)
        self.conversationAppended.emit("assistant", full)
        return final

    async def _on_task(self, tool_name: str, state: str, detail: str) -> None:
        self._runtime.bus.publish(
            LOG, LogLine("tool", Level.INFO, f"{tool_name}: {state} {detail}".strip())
        )
