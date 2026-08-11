"""Runtime container (lightweight dependency injection).

Design note
-----------
One object owns the shared, long-lived services so the UI and agent don't build
their own duplicates. Construction is cheap and non-blocking; the actual work
(model readiness, voice probe) happens under a :class:`~jarvis.supervisor.Supervisor`
so a crashing background loop self-restarts with capped exponential backoff
instead of silently dying (Phase 1 reliability upgrade).
"""

from __future__ import annotations

import logging

import asyncio

from .audit.chain import audit_log, set_audit_bus, verify_chain_detailed
from .config import Config, get_config
from .db import get_db
from .eventbus import EventBus
from .events import DURABLE_TOPICS, LOG, NOTIFY, Level, LogLine, Notification
from .memory import store
from .readiness import ReadinessService
from .supervisor import Supervisor
from .voice import VoiceService

log = logging.getLogger("jarvis.runtime")

# BUG-003 / RISK-002: session_log and the WAL file grow unbounded without
# periodic maintenance. Prune and checkpoint on this interval.
MAINTENANCE_INTERVAL_S = 3600


class Runtime:
    def __init__(self) -> None:
        self.config: Config = get_config()
        # Touch the DB early so migrations + audit table are applied once, up
        # front, rather than lazily on the first user action.
        self.db = get_db()
        # The bus carries the durable audit_events channel (never dropped).
        self.bus = EventBus()
        self.bus.mark_durable(*DURABLE_TOPICS)
        # Route audit writes through the durable channel for live consumers.
        set_audit_bus(self.bus)
        self.readiness = ReadinessService(self.bus)
        self.voice = VoiceService(self.bus)
        self.supervisor = Supervisor()
        # Background loops run supervised: a crash restarts them with backoff and
        # surfaces persistent failures to the audit log rather than looping.
        self.supervisor.supervise("readiness", self.readiness.run, notify_fn=self._on_task_gave_up)
        self.supervisor.supervise("voice", self.voice.run, notify_fn=self._on_task_gave_up)
        self.supervisor.supervise("db_maintenance", self._maintenance_loop)
        # Agent's confirm/task callbacks are wired by the UI (it owns the
        # dialogs), so it is created there with UI-bound callbacks.

    def start_background(self) -> None:
        """Kick off non-blocking background initialisation."""
        import asyncio
        asyncio.create_task(asyncio.to_thread(self._verify_audit_on_boot))
        self.supervisor.start_all()

    def _verify_audit_on_boot(self) -> None:
        """Walk the hash chain at boot; warn (never block) if it is broken."""
        try:
            ok, broken_id = verify_chain_detailed()
        except Exception:
            log.exception("audit verification failed to run")
            return
        if ok:
            audit_log("audit_verify_boot", {"result": "ok"})
            return
        audit_log("audit_verify_boot", {"result": "broken", "entry_id": broken_id})
        log.error("audit chain integrity check FAILED at entry id=%s", broken_id)
        # Surface as a non-blocking notification/log; the shell stays usable.
        self.bus.publish(
            NOTIFY,
            Notification(
                title="Audit chain integrity warning",
                body=f"Audit log appears tampered/corrupted at entry {broken_id}.",
                level=Level.WARNING,
            ),
        )
        self.bus.publish(
            LOG,
            LogLine("audit", Level.WARNING, f"audit chain broken at entry {broken_id}"),
        )

    def _on_task_gave_up(self, name: str, failures: int) -> None:
        """RISK-005: previously a give-up was audit-logged only — nothing
        told the person using the shell that a subsystem had gone
        permanently silent. Surface it as a real notification too."""
        self.bus.publish(
            NOTIFY,
            Notification(
                title=f"{name} is not responding",
                body=(
                    f"Background service '{name}' crashed {failures} times and "
                    "stopped; it will retry automatically in a few minutes."
                ),
                level=Level.WARNING,
            ),
        )

    async def _maintenance_loop(self) -> None:
        """Periodic session_log pruning + WAL checkpoint (BUG-003, RISK-002)."""
        while True:
            await asyncio.sleep(MAINTENANCE_INTERVAL_S)
            try:
                await asyncio.to_thread(store.prune_session)
                await asyncio.to_thread(self.db.checkpoint)
            except Exception:
                log.exception("db maintenance cycle failed")

    async def shutdown(self) -> None:
        # BUG-004 (audit) claimed this double-stops readiness/voice. Verified
        # incorrect: readiness/voice `_task` is only set by their own
        # `start()`, never by the Supervisor path used here, so
        # `supervisor.stop_all()` cancels the polling coroutine but never
        # calls `_stop_server_process()` / mic teardown. `readiness.stop()`
        # and `voice.stop()` below are the only calls that actually perform
        # that cleanup; removing them would leave llama-server running after
        # shutdown. Kept as-is; no change needed.
        await self.supervisor.stop_all()
        await self.readiness.stop()
        await self.voice.stop()
        try:
            self.db.checkpoint()
        except Exception:
            log.exception("db checkpoint on shutdown failed")
