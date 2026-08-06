"""Tests for Phase E Calendar tools."""

from types import SimpleNamespace
from unittest.mock import MagicMock
import caldav
import pytest

from jarvis.tools import calendar_ctl


class DummyVEvent:
    def __init__(self, summary, dtstart):
        self.summary = SimpleNamespace(value=summary)
        self.dtstart = SimpleNamespace(value=dtstart)


class DummyEvent:
    def __init__(self, summary, dtstart):
        self.vobject_instance = SimpleNamespace(vevent=DummyVEvent(summary, dtstart))
    
    def load(self):
        pass


class DummyCalendar:
    def events(self):
        return [DummyEvent("Meeting", "2026-08-06T10:00:00Z")]
    
    def save_event(self, **kwargs):
        pass


class DummyPrincipal:
    def calendars(self):
        return [DummyCalendar()]


class DummyClient:
    def __init__(self, url, username, password):
        pass
    
    def principal(self):
        return DummyPrincipal()


def test_calendar_tools(monkeypatch):
    monkeypatch.setenv("CALDAV_URL", "http://example.com")
    monkeypatch.setenv("CALDAV_USER", "user")
    monkeypatch.setenv("CALDAV_PASSWORD", "pass")
    monkeypatch.setattr(caldav, "DAVClient", DummyClient)
    
    res = calendar_ctl.calendar_read()
    assert "Meeting" in res
    assert "2026-08-06" in res
    
    res2 = calendar_ctl.calendar_create_event("Lunch", "2026-08-06T12:00:00Z", "2026-08-06T13:00:00Z")
    assert res2 == "ok: event created"


def test_calendar_missing_env(monkeypatch):
    monkeypatch.delenv("CALDAV_URL", raising=False)
    assert "error: missing" in calendar_ctl.calendar_read()
