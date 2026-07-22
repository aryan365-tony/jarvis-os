"""Phase 3: snapshot tool + collapsed approval with snapshot safety net."""

import subprocess
from types import SimpleNamespace

import pytest

from jarvis.tools import snapshot
from jarvis.tools.registry import ApprovalResult


def _cp(stdout="", stderr="", rc=0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=rc)


def test_create_pre_action_snapshot_returns_id(monkeypatch):
    monkeypatch.setattr(snapshot, "audit_log", lambda *a, **k: None)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _cp(stdout="42\n"))
    assert snapshot.create_pre_action_snapshot("test") == "42"


def test_create_pre_action_snapshot_none_on_failure(monkeypatch):
    monkeypatch.setattr(snapshot, "audit_log", lambda *a, **k: None)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _cp(stderr="boom", rc=1))
    assert snapshot.create_pre_action_snapshot("test") is None


def test_rollback_validates_and_calls_snapper(monkeypatch):
    monkeypatch.setattr(snapshot, "audit_log", lambda *a, **k: None)
    captured = {}
    monkeypatch.setattr(
        subprocess, "run",
        lambda args, **k: captured.__setitem__("args", args) or _cp(stdout="ok"),
    )
    out = snapshot.snapshot_rollback(7)
    assert "rolled back to snapshot 7" in out
    assert captured["args"] == ["sudo", "-n", "snapper", "-c", "root", "rollback", "7"]


# --- collapsed approval in the bridge ---------------------------------------
class _StubBridge:
    """Minimal object exposing request_tool_approval without Qt."""

    def __init__(self):
        self._runtime = SimpleNamespace(bus=SimpleNamespace(publish=lambda *a, **k: None))

    # import the real coroutine, bound to this stub
    from jarvis.ui_bridge import JarvisBridge as _B

    request_tool_approval = _B.request_tool_approval


@pytest.fixture
def bridge():
    return _StubBridge()


async def test_low_tier_approved_without_snapshot(bridge, monkeypatch):
    import jarvis.ui_bridge as ub

    called = {"snap": 0}
    monkeypatch.setattr(ub, "get_risk_tier", lambda name: "low")
    monkeypatch.setattr(ub, "create_pre_action_snapshot", lambda *a, **k: called.__setitem__("snap", 1))
    res = await bridge.request_tool_approval("fs_read", {})
    assert isinstance(res, ApprovalResult)
    assert res.approved and res.snapshot_id is None
    assert called["snap"] == 0  # no snapshot for low tier


async def test_high_tier_snapshots_and_threads_id(bridge, monkeypatch):
    import jarvis.ui_bridge as ub

    monkeypatch.setattr(ub, "get_risk_tier", lambda name: "high")
    monkeypatch.setattr(ub, "create_pre_action_snapshot", lambda *a, **k: "99")
    monkeypatch.setattr(ub, "audit_log", lambda *a, **k: None)
    res = await bridge.request_tool_approval("pkg_manage", {"action": "remove"})
    assert res.approved
    assert res.snapshot_id == "99"


async def test_high_tier_denied_when_snapshot_fails(bridge, monkeypatch):
    import jarvis.ui_bridge as ub

    monkeypatch.setattr(ub, "get_risk_tier", lambda name: "high")
    monkeypatch.setattr(ub, "create_pre_action_snapshot", lambda *a, **k: None)
    monkeypatch.setattr(ub, "audit_log", lambda *a, **k: None)
    res = await bridge.request_tool_approval("pkg_manage", {"action": "remove"})
    assert not res.approved  # no safety net -> deny
