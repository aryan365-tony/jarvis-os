"""Phase 1: durable audit_events channel — zero-drop guarantee."""

import asyncio

import pytest

from jarvis.eventbus import EventBus
from jarvis.events import AUDIT_EVENTS, DURABLE_TOPICS, HEALTH


@pytest.mark.asyncio
async def test_durable_channel_never_drops_under_load():
    bus = EventBus(queue_maxsize=8)  # deliberately tiny bounded size
    bus.mark_durable(*DURABLE_TOPICS)
    sub = bus.subscribe(AUDIT_EVENTS)

    N = 5000  # far exceeds the bounded queue size
    for i in range(N):
        bus.publish(AUDIT_EVENTS, {"i": i})

    received = []
    with sub:
        for _ in range(N):
            topic, payload = await asyncio.wait_for(sub.__anext__(), timeout=1.0)
            received.append(payload["i"])

    assert bus.durable_published == N
    assert bus.durable_dropped == 0
    assert received == list(range(N))  # in-order, complete


@pytest.mark.asyncio
async def test_bounded_ui_channel_drops_oldest():
    bus = EventBus(queue_maxsize=4)
    sub = bus.subscribe(HEALTH)  # not durable
    for i in range(100):
        bus.publish(HEALTH, {"i": i})

    drained = []
    with sub:
        while not sub._queue.empty():  # type: ignore[attr-defined]
            drained.append((await sub.__anext__())[1]["i"])

    # Bounded queue keeps only the most recent items (drop-oldest).
    assert len(drained) <= 4
    assert drained[-1] == 99


@pytest.mark.asyncio
async def test_audit_log_mirrors_to_durable_channel(tmp_path, monkeypatch):
    # Fresh DB so we control the chain.
    from jarvis import db as db_mod
    from jarvis.db import Database
    from jarvis.audit import chain

    database = Database(str(tmp_path / "m.sqlite3"))
    db_mod.set_db(database)

    bus = EventBus()
    bus.mark_durable(*DURABLE_TOPICS)
    chain.set_audit_bus(bus)
    sub = bus.subscribe(AUDIT_EVENTS)

    chain.audit_log("unit_event", {"k": "v"})

    with sub:
        topic, payload = await asyncio.wait_for(sub.__anext__(), timeout=1.0)
    assert topic == AUDIT_EVENTS
    assert payload.source == "unit_event"
    assert payload.data == {"k": "v"}

    chain.set_audit_bus(None)
    database.close()
