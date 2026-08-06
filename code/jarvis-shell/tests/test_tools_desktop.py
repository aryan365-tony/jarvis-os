"""Tests for Phase D Desktop GUI Control tools."""

import subprocess
from types import SimpleNamespace

from jarvis.tools import desktop_control


def _fake_completed(stdout="out", stderr="", rc=0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=rc)


def test_desktop_list_windows(monkeypatch):
    captured = {}
    monkeypatch.setattr(subprocess, "run", lambda args, **k: captured.__setitem__("args", args) or _fake_completed())
    
    desktop_control.desktop_list_windows()
    assert captured["args"] == ["wlrctl", "window", "list"]


def test_desktop_focus_window(monkeypatch):
    captured = {}
    monkeypatch.setattr(subprocess, "run", lambda args, **k: captured.__setitem__("args", args) or _fake_completed())
    
    desktop_control.desktop_focus_window("firefox")
    assert captured["args"] == ["wlrctl", "window", "focus", "firefox"]


def test_desktop_accessibility_type(monkeypatch):
    captured = {}
    monkeypatch.setattr(subprocess, "run", lambda args, **k: captured.__setitem__("args", args) or _fake_completed())
    
    desktop_control.desktop_accessibility_type("hello")
    assert captured["args"] == ["wtype", "hello"]


def test_desktop_accessibility_click(monkeypatch):
    captured = {}
    monkeypatch.setattr(subprocess, "run", lambda args, **k: captured.__setitem__("args", args) or _fake_completed())
    
    desktop_control.desktop_accessibility_click("left")
    assert captured["args"] == ["ydotool", "click", "0xC0"]
    
    desktop_control.desktop_accessibility_click("right")
    assert captured["args"] == ["ydotool", "click", "0xC1"]
