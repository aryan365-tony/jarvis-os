"""Minimal in-process async publish/subscribe bus.

Design note
-----------
We deliberately avoid an external broker. The whole shell runs in one process on
one asyncio loop, so a dict of topic -> subscriber callbacks is enough and keeps
latency at zero. Two subscription styles are supported:

* ``on(topic, coro_fn)`` — register an async callback (used by services).
* ``subscribe(topic)`` — get an ``asyncio.Queue`` to consume (used by the UI,
  which drains it from a Textual worker).

Publishing never blocks the publisher: callbacks are scheduled and queues are
put-nowait with overflow protection so a slow consumer can never stall a fast
producer (a core "never freeze" requirement).

Two channels (Phase 1 durability upgrade)
-----------------------------------------
The bus distinguishes two classes of topic:

* **ui_events** (default): bounded, *drop-oldest*. Correct for HUD/telemetry
  where the latest state supersedes stale ones — a slow UI must never stall a
  fast producer, and losing an intermediate status tick is harmless.
* **audit_events** (topics registered via ``mark_durable``): *unbounded, never
  dropped*. Tool executions, errors, and system-state changes route here so the
  audit trail (the only post-hoc oversight once approvals are collapsed) can
  never silently lose an event. Durable subscriber queues are unbounded, and
  durable publishes use a non-dropping put. A counter (``durable_published``)
  lets tests assert emitted-vs-delivered parity.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Awaitable, Callable

log = logging.getLogger("jarvis.eventbus")

Callback = Callable[[Any], Awaitable[None]]


class EventBus:
    def __init__(
        self,
        queue_maxsize: int = 1024,
        durable_topics: set[str] | None = None,
    ) -> None:
        self._callbacks: dict[str, list[Callback]] = defaultdict(list)
        self._queues: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._queue_maxsize = queue_maxsize
        # Topics whose delivery must never drop (the audit_events channel).
        self._durable_topics: set[str] = set(durable_topics or ())
        # Monotonic counters used by the durability test gate.
        self.durable_published = 0
        self.durable_dropped = 0

    # -- durability configuration ------------------------------------------
    def mark_durable(self, *topics: str) -> None:
        """Register topics as belonging to the never-dropped audit channel."""
        self._durable_topics.update(topics)

    def is_durable(self, topic: str) -> bool:
        return topic in self._durable_topics

    # -- registration -------------------------------------------------------
    def on(self, topic: str, callback: Callback) -> None:
        self._callbacks[topic].append(callback)

    def subscribe(self, *topics: str) -> "Subscription":
        # A subscription that includes any durable topic gets an unbounded queue
        # so a durable event can never be evicted to make room.
        durable = any(t in self._durable_topics for t in topics)
        maxsize = 0 if durable else self._queue_maxsize
        queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        for topic in topics:
            self._queues[topic].append(queue)
        return Subscription(self, topics, queue)

    def _unsubscribe(self, topics: tuple[str, ...], queue: asyncio.Queue) -> None:
        for topic in topics:
            try:
                self._queues[topic].remove(queue)
            except ValueError:
                pass

    # -- publishing ---------------------------------------------------------
    def publish(self, topic: str, payload: Any) -> None:
        """Fire-and-forget publish. Safe to call from any coroutine."""
        durable = topic in self._durable_topics
        if durable:
            self.durable_published += 1
        for cb in self._callbacks.get(topic, ()):  # scheduled, never awaited here
            asyncio.create_task(self._safe_call(cb, payload))
        for queue in self._queues.get(topic, ()):
            if durable:
                # Never drop: the queue is unbounded, so put_nowait cannot fail
                # under normal operation. Count any pathological failure so the
                # test gate can detect a regression instead of silently losing it.
                try:
                    queue.put_nowait((topic, payload))
                except asyncio.QueueFull:  # pragma: no cover - unbounded queue
                    self.durable_dropped += 1
                    log.error("durable event dropped on topic %s", topic)
            else:
                _put_dropping_oldest(queue, (topic, payload))

    @staticmethod
    async def _safe_call(cb: Callback, payload: Any) -> None:
        try:
            await cb(payload)
        except Exception:  # a broken subscriber must not take down the bus
            log.exception("event callback failed")


class Subscription:
    """Async iterator over ``(topic, payload)`` tuples."""

    def __init__(self, bus: EventBus, topics: tuple[str, ...], queue: asyncio.Queue) -> None:
        self._bus = bus
        self._topics = topics
        self._queue = queue

    def __aiter__(self) -> "Subscription":
        return self

    async def __anext__(self) -> tuple[str, Any]:
        return await self._queue.get()

    def close(self) -> None:
        self._bus._unsubscribe(self._topics, self._queue)

    def __enter__(self) -> "Subscription":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _put_dropping_oldest(queue: asyncio.Queue, item: Any) -> None:
    """Put without ever blocking; if full, drop the oldest item.

    Dropping the oldest keeps the UI current (latest state wins) rather than
    stalling producers — the right trade-off for status/telemetry streams.
    """
    if queue.full():
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
    try:
        queue.put_nowait(item)
    except asyncio.QueueFull:  # pragma: no cover - race with another producer
        pass
