"""Registry: tier registration, legacy alias mapping, and basic execute path.

Budget / per-tool ceiling / approval-gate tests removed — those features were
stripped in the guardrail-removal pass.  ApprovalResult no longer exists in
the registry module.
"""

import pytest

from jarvis.tools import registry
from jarvis.tools.registry import execute, get_risk_tier, register


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


async def test_tool_executes_and_returns_result():
    register("simple_op", risk="low")(lambda: "hello")
    assert await execute("simple_op", {}) == "hello"


async def test_unknown_tool_returns_error():
    out = await execute("no_such_tool_xyz", {})
    assert "unknown tool" in out


async def test_high_tier_executes_unconditionally():
    """After guardrail removal, high-tier tools run with no approval step."""
    register("danger_free", risk="high")(lambda: "ran")
    assert await execute("danger_free", {}) == "ran"
