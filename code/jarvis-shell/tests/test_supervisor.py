"""Phase 1: SupervisedTask restart-with-backoff and crash-cap behavior."""

import asyncio

import pytest

from jarvis import supervisor as sup_mod
from jarvis.supervisor import SupervisedTask


@pytest.fixture(autouse=True)
def _silence_audit(monkeypatch):
    # Avoid touching the real DB from the supervisor's audit_log calls.
    monkeypatch.setattr(sup_mod, "audit_log", lambda *a, **k: None)


@pytest.mark.asyncio
async def test_restarts_on_crash_then_succeeds():
    attempts = {"n": 0}

    async def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("boom")
        # Third attempt returns cleanly -> supervisor stops.
        return

    t = SupervisedTask("flaky", flaky, base_backoff_s=0.001, max_backoff_s=0.01)
    t.start()
    await asyncio.wait_for(t._task, timeout=2.0)  # type: ignore[arg-type]
    assert attempts["n"] == 3
    assert not t.gave_up


@pytest.mark.asyncio
async def test_gives_up_after_cap_and_surfaces():
    surfaced = {"gave_up": False}

    def fake_audit(event, payload):
        if event == "supervised_task_gave_up":
            surfaced["gave_up"] = True

    sup_mod.audit_log = fake_audit  # type: ignore[assignment]

    async def always_crash():
        raise RuntimeError("nope")

    t = SupervisedTask(
        "bad", always_crash, base_backoff_s=0.001, max_backoff_s=0.002, max_restarts=3
    )
    t.start()
    await asyncio.wait_for(t._task, timeout=2.0)  # type: ignore[arg-type]
    assert t.gave_up
    assert t.failures == 3
    assert surfaced["gave_up"] is True


@pytest.mark.asyncio
async def test_clean_return_is_not_a_crash():
    ran = {"n": 0}

    async def once():
        ran["n"] += 1
        return

    t = SupervisedTask("once", once, base_backoff_s=0.001)
    t.start()
    await asyncio.wait_for(t._task, timeout=1.0)  # type: ignore[arg-type]
    assert ran["n"] == 1
    assert t.failures == 0
    assert not t.gave_up
