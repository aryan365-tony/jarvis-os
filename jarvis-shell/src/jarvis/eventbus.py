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
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Awaitable, Callable

log = logging.getLogger("jarvis.eventbus")

Callback = Callable[[Any], Awaitable[None]]


class EventBus:
    def __init__(self, queue_maxsize: int = 1024) -> None:
        self._callbacks: dict[str, list[Callback]] = defaultdict(list)
        self._queues: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._queue_maxsize = queue_maxsize

    # -- registration -------------------------------------------------------
    def on(self, topic: str, callback: Callback) -> None:
        self._callbacks[topic].append(callback)

    def subscribe(self, *topics: str) -> "Subscription":
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._queue_maxsize)
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
        for cb in self._callbacks.get(topic, ()):  # scheduled, never awaited here
            asyncio.create_task(self._safe_call(cb, payload))
        for queue in self._queues.get(topic, ()):  # non-blocking hand-off
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
