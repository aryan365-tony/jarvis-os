"""Background readiness poller for the LLM backend.

Design note
-----------
This is the heart of "silent boot". Instead of gating the UI behind the model
(the old ``ExecStartPre`` healthcheck), the shell launches immediately and this
poller watches ``/health`` in the background, publishing state transitions on
the event bus:

    INITIALIZING -> READY            (model came up)
    INITIALIZING -> DEGRADED         (timeout; UI stays usable, text still works
                                      once the endpoint answers)
    READY -> ERROR -> INITIALIZING   (server restarted / crashed)

The UI reacts to these events to light up capabilities progressively.
"""

from __future__ import annotations

import asyncio
import time

import httpx

from .config import get_config
from .eventbus import EventBus
from .events import LOG, MODEL_STATUS, Level, LogLine, ServiceState, ServiceStatus


class ReadinessService:
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._cfg = get_config()
        self._state = ServiceState.INITIALIZING
        self._task: asyncio.Task | None = None

    @property
    def state(self) -> ServiceState:
        return self._state

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="readiness-poller")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def _emit(self, state: ServiceState, detail: str = "") -> None:
        if state != self._state:
            self._state = state
            self._bus.publish(
                MODEL_STATUS, ServiceStatus("model", state, detail)
            )
            self._bus.publish(
                LOG, LogLine("model", Level.INFO, f"backend {state.value}: {detail}".strip())
            )

    async def _run(self) -> None:
        cfg = self._cfg
        started = time.monotonic()
        self._bus.publish(MODEL_STATUS, ServiceStatus("model", ServiceState.INITIALIZING, "starting"))
        async with httpx.AsyncClient(timeout=3.0) as client:
            while True:
                try:
                    r = await client.get(cfg.llm.health_endpoint)
                    if r.status_code == 200:
                        self._emit(ServiceState.READY, "healthy")
                    else:
                        self._emit(ServiceState.INITIALIZING, f"http {r.status_code}")
                except Exception:
                    # Not up yet (or restarting). Flag degraded only after the
                    # configured grace period so we don't alarm the user early.
                    if (
                        self._state != ServiceState.READY
                        and time.monotonic() - started > cfg.boot.model_ready_timeout_s
                    ):
                        self._emit(ServiceState.DEGRADED, "model taking longer than expected")
                    elif self._state == ServiceState.READY:
                        # Was healthy, now failing: server likely restarting.
                        self._emit(ServiceState.INITIALIZING, "reconnecting")
                await asyncio.sleep(cfg.boot.health_poll_interval_s)
