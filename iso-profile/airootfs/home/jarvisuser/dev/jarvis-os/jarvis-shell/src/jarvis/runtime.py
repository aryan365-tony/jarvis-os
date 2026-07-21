"""Runtime container (lightweight dependency injection).

Design note
-----------
One object owns the shared, long-lived services so the UI and agent don't build
their own duplicates. Construction is cheap and non-blocking; the actual work
(model readiness, voice probe) happens in background tasks started via
``start_background``.
"""

from __future__ import annotations

from .agent import ConversationAgent
from .config import Config, get_config
from .db import get_db
from .eventbus import EventBus
from .readiness import ReadinessService
from .voice import VoiceService


class Runtime:
    def __init__(self) -> None:
        self.config: Config = get_config()
        # Touch the DB early so migrations + audit table are applied once, up
        # front, rather than lazily on the first user action.
        self.db = get_db()
        self.bus = EventBus()
        self.readiness = ReadinessService(self.bus)
        self.voice = VoiceService(self.bus)
        # Agent's confirm/task callbacks are wired by the UI (it owns the
        # dialogs), so it is created there with UI-bound callbacks.

    def start_background(self) -> None:
        """Kick off non-blocking background initialisation."""
        self.readiness.start()
        self.voice.start()

    async def shutdown(self) -> None:
        await self.readiness.stop()
        await self.voice.stop()
