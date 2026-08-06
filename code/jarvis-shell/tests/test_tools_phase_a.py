"""Tests for Phase A OS control tools."""

import subprocess
from types import SimpleNamespace

import pytest

from jarvis.tools import bluetooth_ctl, media_ctl, network_ctl, notify, power_ctl, scheduler, voice_ctl


def _fake_completed(stdout="out", stderr="", rc=0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=rc)


def test_network_ctl(monkeypatch):
    captured = {}
    monkeypatch.setattr(subprocess, "run", lambda args, **k: captured.__setitem__("args", args) or _fake_completed())
    
    network_ctl.net_status()
    assert captured["args"][:3] == ["nmcli", "-t", "-f"]
    
    network_ctl.net_wifi_connect("MySSID", "secret")
    assert captured["args"][:5] == ["nmcli", "device", "wifi", "connect", "MySSID"]
    
    assert "error" in network_ctl.net_wifi_connect("bad;rm", "")


def test_bluetooth_ctl(monkeypatch):
    captured = {}
    monkeypatch.setattr(subprocess, "run", lambda args, **k: captured.__setitem__("args", args) or _fake_completed())
    
    bluetooth_ctl.bt_scan()
    assert captured["args"][:2] == ["bluetoothctl", "--timeout"]
    
    out = bluetooth_ctl.bt_pair("00:11:22:33:44:55")
    assert captured["args"] == ["bluetoothctl", "pair", "00:11:22:33:44:55"]
    
    assert "error" in bluetooth_ctl.bt_pair("bad mac")


def test_power_ctl(monkeypatch):
    captured = {}
    monkeypatch.setattr(subprocess, "run", lambda args, **k: captured.__setitem__("args", args) or _fake_completed())
    
    assert "error" in power_ctl.power_suspend("wrong phrase")
    
    power_ctl.power_suspend("I understand this will suspend the system")
    assert captured["args"] == ["sudo", "-n", "systemctl", "suspend"]


def test_media_ctl(monkeypatch):
    captured = {}
    monkeypatch.setattr(subprocess, "run", lambda args, **k: captured.__setitem__("args", args) or _fake_completed())
    
    media_ctl.media_play_pause()
    assert captured["args"] == ["playerctl", "play-pause"]
    
    assert "error" in media_ctl.volume_set("2.0")
    
    media_ctl.volume_set("0.5")
    assert captured["args"] == ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "0.5"]


def test_notify(monkeypatch):
    captured = {}
    monkeypatch.setattr(subprocess, "run", lambda args, **k: captured.__setitem__("args", args) or _fake_completed())
    
    notify.notify_send("Hello", "World")
    assert captured["args"] == ["notify-send", "Hello", "World"]


def test_scheduler(monkeypatch):
    captured = {}
    monkeypatch.setattr(subprocess, "run", lambda args, **k: captured.__setitem__("args", args) or _fake_completed())
    
    scheduler.task_schedule_once("10s", "echo hi")
    assert captured["args"][:3] == ["systemd-run", "--user", "--on-active=10s"]
    assert captured["args"][-1] == "echo hi"
