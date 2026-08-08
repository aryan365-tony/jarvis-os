"""Phase 3: snapshot tool tests (create / rollback).

Approval-gate tests removed — request_tool_approval and ApprovalResult were
deleted when the approval system was stripped.  Only the underlying snapper
tool functions are tested here.
"""

import subprocess
from types import SimpleNamespace

import pytest

from jarvis.tools import snapshot


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


