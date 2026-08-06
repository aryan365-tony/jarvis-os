"""Crash-loop-resistant supervision for long-lived background tasks.

Design note
-----------
Phase 1 extends the readiness/self-healing pattern beyond the llama backend to
the shell's own background coroutines (readiness poller, voice pipeline, event
pump). Systemd already restarts the *process* if it dies (Restart=always with a
start-limit backoff), but individual in-process async tasks can fail without
taking the process down — leaving a silently degraded shell. This supervisor:

* restarts a supervised coroutine when it raises;
* applies **exponential backoff** between restarts (base * 2**failures, capped);
* **caps** the number of consecutive restarts so a hard crash loop cannot peg
  the CPU forever — instead it gives up and *surfaces* the failure to the audit
  log (never an infinite silent loop);
* resets the failure counter once a task has run healthily past a threshold, so
  an occasional transient error does not eventually exhaust the cap.

A clean return or ``CancelledError`` is terminal and never counts as a crash.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Awaitable, Callable

from .audit.chain import audit_log

log = logging.getLogger("jarvis.supervisor")

CoroFactory = Callable[[], Awaitable[None]]


class SupervisedTask:
    """Runs ``factory()`` under restart-with-backoff supervision."""

    def __init__(
        self,
        name: str,
        factory: CoroFactory,
        *,
        base_backoff_s: float = 1.0,
        max_backoff_s: float = 60.0,
        max_restarts: int = 8,
        healthy_after_s: float = 30.0,
    ) -> None:
        self.name = name
        self._factory = factory
        self._base_backoff_s = base_backoff_s
        self._max_backoff_s = max_backoff_s
        self._max_restarts = max_restarts
        self._healthy_after_s = healthy_after_s
        self._task: asyncio.Task | None = None
        self._failures = 0
        self._gave_up = False

    @property
    def failures(self) -> int:
        return self._failures

    @property
    def gave_up(self) -> bool:
        return self._gave_up

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name=f"supervise:{self.name}")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def _backoff(self) -> float:
        return min(self._base_backoff_s * (2 ** self._failures), self._max_backoff_s)

    async def _run(self) -> None:
        while True:
            started = time.monotonic()
            try:
                await self._factory()
                # Clean return: the task decided it was done. Not a crash.
                log.info("supervised task %s exited cleanly", self.name)
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # the whole point: keep the shell alive
                ran_for = time.monotonic() - started
                if ran_for >= self._healthy_after_s:
                    # It was healthy long enough; treat this as a fresh failure.
                    self._failures = 0
                self._failures += 1
                log.exception("supervised task %s crashed (failure %d/%d)",
                              self.name, self._failures, self._max_restarts)
                audit_log(
                    "supervised_task_crash",
                    {
                        "task": self.name,
                        "failure": self._failures,
                        "max_restarts": self._max_restarts,
                        "error": str(exc),
                        "ran_for_s": round(ran_for, 3),
                    },
                )
                if self._failures >= self._max_restarts:
                    self._gave_up = True
                    audit_log(
                        "supervised_task_gave_up",
                        {"task": self.name, "failures": self._failures},
                    )
                    log.error(
                        "supervised task %s exceeded restart cap (%d); giving up",
                        self.name, self._max_restarts,
                    )
                    return
                await asyncio.sleep(self._backoff())


class Supervisor:
    """Owns a set of :class:`SupervisedTask` objects."""

    def __init__(self) -> None:
        self._tasks: dict[str, SupervisedTask] = {}

    def supervise(self, name: str, factory: CoroFactory, **kw) -> SupervisedTask:
        task = SupervisedTask(name, factory, **kw)
        self._tasks[name] = task
        return task

    def start_all(self) -> None:
        for t in self._tasks.values():
            t.start()

    async def stop_all(self) -> None:
        for t in self._tasks.values():
            await t.stop()

    @property
    def tasks(self) -> dict[str, SupervisedTask]:
        return self._tasks
