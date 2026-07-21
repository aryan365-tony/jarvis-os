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
from pathlib import Path

import httpx

from .config import get_config
from .eventbus import EventBus
from .events import LOG, MODEL_STATUS, Level, LogLine, ServiceState, ServiceStatus


class ReadinessService:
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._cfg = get_config()
        self._desired_online = self._cfg.boot.model_auto_start
        self._state = (
            ServiceState.INITIALIZING
            if self._desired_online
            else ServiceState.UNAVAILABLE
        )
        self._task: asyncio.Task | None = None
        self._server_proc: asyncio.subprocess.Process | None = None
        self._model_dir = Path(__file__).resolve().parents[3] / "llama" / "models"
        self._download_script = (
            Path(__file__).resolve().parents[3] / "llama" / "download-model.sh"
        )
        self._server_script = (
            Path(__file__).resolve().parents[3] / "llama" / "serve.sh"
        )
        self._online_since = 0.0

    def _any_model_path(self) -> Path | None:
        for p in sorted(self._model_dir.glob("*.gguf")):
            if p.is_file():
                return p
        return None

    @property
    def state(self) -> ServiceState:
        return self._state

    @property
    def desired_online(self) -> bool:
        return self._desired_online

    def set_desired_online(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self._desired_online == enabled:
            return
        self._desired_online = enabled
        self._online_since = time.monotonic() if enabled else 0.0
        if enabled:
            self._emit(ServiceState.INITIALIZING, "starting backend")
        else:
            self._emit(ServiceState.UNAVAILABLE, "offline by user")

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="readiness-poller")

    async def stop(self) -> None:
        await self._stop_server_process()
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

    async def _start_server_process(self) -> bool:
        if self._server_proc and self._server_proc.returncode is None:
            return True

        if not self._server_script.exists():
            self._emit(ServiceState.ERROR, f"serve script missing: {self._server_script}")
            return False

        try:
            self._server_proc = await asyncio.create_subprocess_exec(
                "/bin/bash",
                str(self._server_script),
            )
        except Exception as e:
            self._emit(ServiceState.ERROR, f"failed to spawn backend: {e}")
            return False

        # Detect immediate exits (missing model/backend) to avoid restart loops.
        await asyncio.sleep(0.4)
        if self._server_proc.returncode is not None:
            code = self._server_proc.returncode
            self._server_proc = None
            if code == 0:
                self._desired_online = False
                self._emit(
                    ServiceState.UNAVAILABLE,
                    "model missing or backend intentionally skipped",
                )
            else:
                self._emit(ServiceState.ERROR, f"backend exited code={code}")
            return False

        self._online_since = time.monotonic()
        return True

    async def _ensure_model_present(self) -> bool:
        model = self._any_model_path()
        if model is not None:
            return True

        if not self._download_script.exists():
            self._emit(ServiceState.ERROR, f"model downloader missing: {self._download_script}")
            return False

        self._emit(ServiceState.INITIALIZING, "downloading model")
        self._bus.publish(LOG, LogLine("model", Level.INFO, "model missing; starting download"))

        try:
            proc = await asyncio.create_subprocess_exec(
                "/bin/bash",
                str(self._download_script),
            )
            code = await proc.wait()
        except Exception as e:
            self._emit(ServiceState.ERROR, f"model download failed: {e}")
            return False

        if code != 0:
            self._emit(ServiceState.ERROR, f"model download failed code={code}")
            return False

        model = self._any_model_path()
        if model is None:
            self._emit(ServiceState.ERROR, "model download reported success but no GGUF exists")
            return False

        self._bus.publish(LOG, LogLine("model", Level.INFO, "model download complete"))
        return True

    async def _stop_server_process(self) -> None:
        if not self._server_proc or self._server_proc.returncode is not None:
            self._server_proc = None
            return
        self._server_proc.terminate()
        try:
            await asyncio.wait_for(self._server_proc.wait(), timeout=3.0)
        except asyncio.TimeoutError:
            self._server_proc.kill()
            await self._server_proc.wait()
        finally:
            self._server_proc = None

    async def _run(self) -> None:
        cfg = self._cfg
        self._bus.publish(
            MODEL_STATUS,
            ServiceStatus(
                "model",
                self._state,
                "starting" if self._desired_online else "offline by default",
            ),
        )
        async with httpx.AsyncClient(timeout=3.0) as client:
            while True:
                if not self._desired_online:
                    await self._stop_server_process()
                    self._emit(ServiceState.UNAVAILABLE, "offline by user")
                    await asyncio.sleep(cfg.boot.health_poll_interval_s)
                    continue

                if not await self._ensure_model_present():
                    # Do not loop endlessly on a broken network/download path.
                    self._desired_online = False
                    self._emit(ServiceState.UNAVAILABLE, "offline (download/start failed)")
                    await asyncio.sleep(cfg.boot.health_poll_interval_s)
                    continue

                if not await self._start_server_process():
                    await asyncio.sleep(cfg.boot.health_poll_interval_s)
                    continue

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
                        and time.monotonic() - self._online_since > cfg.boot.model_ready_timeout_s
                    ):
                        self._emit(ServiceState.DEGRADED, "model taking longer than expected")
                    elif self._state == ServiceState.READY:
                        # Was healthy, now failing: server likely restarting.
                        self._emit(ServiceState.INITIALIZING, "reconnecting")
                await asyncio.sleep(cfg.boot.health_poll_interval_s)
