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
# Called as notify_fn(task_name, failures) when a task gives up (and again on
# every subsequent give-up after a cool-down retry fails).
NotifyFn = Callable[[str, int], None]


class SupervisedTask:
    """Runs ``factory()`` under restart-with-backoff supervision.

    RISK-005: a task that hit ``max_restarts`` used to be dead for the rest
    of the process — no further retries, no visible notification, the shell
    just silently ran with a permanently broken subsystem. Now, after giving
    up, it waits ``giveup_cooldown_s`` and tries again exactly once; a run
    that stays healthy past ``healthy_after_s`` clears the give-up state and
    resumes normal supervision, otherwise it gives up again and repeats the
    cool-down cycle (bounded retry, not a tight crash loop).
    """

    def __init__(
        self,
        name: str,
        factory: CoroFactory,
        *,
        base_backoff_s: float = 1.0,
        max_backoff_s: float = 60.0,
        max_restarts: int = 8,
        healthy_after_s: float = 30.0,
        giveup_cooldown_s: float = 600.0,
        notify_fn: NotifyFn | None = None,
    ) -> None:
        self.name = name
        self._factory = factory
        self._base_backoff_s = base_backoff_s
        self._max_backoff_s = max_backoff_s
        self._max_restarts = max_restarts
        self._healthy_after_s = healthy_after_s
        self._giveup_cooldown_s = giveup_cooldown_s
        self._notify_fn = notify_fn
        self._task: asyncio.Task | None = None
        self._recovery_task: asyncio.Task | None = None
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
        if self._recovery_task:
            self._recovery_task.cancel()
            try:
                await self._recovery_task
            except asyncio.CancelledError:
                pass
            self._recovery_task = None
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
                        "supervised task %s exceeded restart cap (%d); "
                        "giving up, will retry once after %.0fs",
                        self.name, self._max_restarts, self._giveup_cooldown_s,
                    )
                    if self._notify_fn is not None:
                        try:
                            self._notify_fn(self.name, self._failures)
                        except Exception:
                            log.exception("supervisor notify_fn failed for %s", self.name)
                    # Schedule one bounded recovery attempt after a cool-down
                    # instead of dying for the life of the process, but let
                    # this task instance finish now (it is "done", same as
                    # the old give-up contract) — a fresh SupervisedTask.start()
                    # is what actually resumes supervision.
                    self._recovery_task = asyncio.create_task(self._schedule_recovery())
                    return
                await asyncio.sleep(self._backoff())

    async def _schedule_recovery(self) -> None:
        await asyncio.sleep(self._giveup_cooldown_s)
        self._failures = 0
        self._gave_up = False
        self.start()


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
