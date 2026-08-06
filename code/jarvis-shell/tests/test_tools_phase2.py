"""Phase 2: tool behavior via mocked subprocess (no real system mutation)."""

import subprocess
from types import SimpleNamespace

import pytest

from jarvis.tools import diagnostics, fs_ops, pkg_manage, svc_control


def _fake_completed(stdout="out", stderr="", rc=0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=rc)


# --- pkg_manage --------------------------------------------------------------
def test_pkg_query_rejects_bad_name():
    assert "invalid" in pkg_manage.pkg_query("info", "bad;rm -rf /")


def test_pkg_manage_rejects_bad_pkg(monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: called.__setitem__("n", called["n"] + 1) or _fake_completed())
    out = pkg_manage.pkg_manage("install", ["ok", "evil name"])
    assert "invalid" in out
    assert called["n"] == 0  # never shelled out


def test_pkg_manage_install_shells_pacman(monkeypatch):
    captured = {}
    monkeypatch.setattr(subprocess, "run", lambda args, **k: captured.__setitem__("args", args) or _fake_completed("installed"))
    out = pkg_manage.pkg_manage("install", ["htop"])
    assert "installed" in out
    assert captured["args"][:4] == ["sudo", "-n", "pacman", "-S"]
    assert "htop" in captured["args"]


# --- svc_control -------------------------------------------------------------
def test_svc_control_rejects_bad_action():
    assert "unsupported" in svc_control.svc_control("nuke", "foo.service")


def test_svc_control_rejects_bad_unit():
    assert "invalid" in svc_control.svc_control("restart", "foo;reboot")


def test_svc_control_restart(monkeypatch):
    captured = {}
    monkeypatch.setattr(subprocess, "run", lambda args, **k: captured.__setitem__("args", args) or _fake_completed())
    svc_control.svc_control("restart", "llama-server.service")
    assert captured["args"] == ["sudo", "-n", "systemctl", "restart", "llama-server.service"]


# --- fs_ops scratch confinement ---------------------------------------------
def test_fs_scratch_refuses_outside(monkeypatch, tmp_path):
    monkeypatch.setattr(
        fs_ops, "get_config", lambda: SimpleNamespace(policy=SimpleNamespace(fs_scratch_dir=str(tmp_path)))
    )
    out = fs_ops.fs_scratch("write", "/etc/passwd", content="x")
    assert "outside the scratch" in out


def test_fs_scratch_write_inside(monkeypatch, tmp_path):
    monkeypatch.setattr(
        fs_ops, "get_config", lambda: SimpleNamespace(policy=SimpleNamespace(fs_scratch_dir=str(tmp_path)))
    )
    target = tmp_path / "note.txt"
    out = fs_ops.fs_scratch("write", str(target), content="hello")
    assert "wrote" in out
    assert target.read_text() == "hello"


def test_fs_system_routes_through_fsop(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        subprocess, "run",
        lambda args, **k: captured.__setitem__("args", args) or _fake_completed("ok"),
    )
    fs_ops.fs_system("write", "/etc/motd", content="hi")
    assert captured["args"][:3] == ["sudo", "-n", "/usr/local/bin/jarvis-fsop"]
    assert captured["args"][3] == "write"


# --- diagnostics (read only) -------------------------------------------------
def test_diag_journal_validates_unit():
    assert "invalid" in diagnostics.diag_journal(unit="foo;rm")
