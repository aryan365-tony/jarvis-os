"""Phase 2: registry tier migration, budgets, and snapshot-linked approval."""

import pytest

from jarvis.tools import registry
from jarvis.tools.registry import ApprovalResult, execute, get_risk_tier, register


@pytest.fixture(autouse=True)
def _no_audit(monkeypatch):
    monkeypatch.setattr(registry, "audit_log", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def _clean_registry():
    saved = dict(registry.REGISTRY)
    try:
        yield
    finally:
        registry.REGISTRY.clear()
        registry.REGISTRY.update(saved)


def test_legacy_tiers_map_forward():
    register("legacy_irr", risk="irreversible")(lambda: "x")
    register("legacy_safe", risk="safe")(lambda: "x")
    assert get_risk_tier("legacy_irr") == "high"
    assert get_risk_tier("legacy_safe") == "low"


def test_invalid_tier_rejected_at_registration():
    with pytest.raises(ValueError):
        register("bad", risk="catastrophic")(lambda: "x")


async def test_high_tier_denied_without_approver():
    register("danger", risk="high")(lambda: "did it")
    out = await execute("danger", {}, confirm=None)
    assert out.startswith("denied")


async def test_high_tier_runs_and_threads_snapshot_id():
    seen = {}

    @register("danger2", risk="high")
    def danger2():
        return "boom"

    async def approver(name, args):
        return ApprovalResult(approved=True, snapshot_id="snap-42")

    def capture(event, payload):
        if event == "tool_call_ok":
            seen.update(payload)

    registry.audit_log = capture  # type: ignore[assignment]
    out = await execute("danger2", {}, confirm=approver)
    assert out == "boom"
    assert seen.get("snapshot_id") == "snap-42"


async def test_low_tier_runs_without_confirm():
    register("safe_op", risk="low")(lambda: "ok")
    assert await execute("safe_op", {}, confirm=None) == "ok"


async def test_per_tool_budget_enforced():
    register("countme", risk="low", max_calls_per_turn=2)(lambda: "ok")
    counts: dict[str, int] = {}
    assert await execute("countme", {}, call_counts=counts) == "ok"
    assert await execute("countme", {}, call_counts=counts) == "ok"
    out = await execute("countme", {}, call_counts=counts)
    assert "budget exceeded" in out


async def test_global_per_turn_ceiling(monkeypatch):
    monkeypatch.setattr(registry, "PER_TURN_TOOL_BUDGET", 3)
    for i in range(5):
        register(f"t{i}", risk="low", max_calls_per_turn=99)(lambda: "ok")
    counts: dict[str, int] = {}
    assert await execute("t0", {}, call_counts=counts) == "ok"
    assert await execute("t1", {}, call_counts=counts) == "ok"
    assert await execute("t2", {}, call_counts=counts) == "ok"
    out = await execute("t3", {}, call_counts=counts)
    assert "per-turn tool budget" in out
