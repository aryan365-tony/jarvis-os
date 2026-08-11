"""Tests for Phase B Home Assistant tools."""

from unittest.mock import MagicMock
import httpx
import pytest

from jarvis.tools import home_assistant


class DummyResponse:
    def __init__(self, data):
        self.data = data
    def raise_for_status(self):
        pass
    def json(self):
        return self.data


def test_ha_list_entities(monkeypatch):
    class DummyClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def get(self, url):
            return DummyResponse([
                {"entity_id": "light.living_room", "state": "on", "attributes": {"friendly_name": "Living Room"}},
                {"entity_id": "climate.downstairs", "state": "heat", "attributes": {}},
            ])
            
    monkeypatch.setattr(httpx, "Client", DummyClient)
    
    res = home_assistant.ha_list_entities()
    assert "light.living_room" in res
    assert "climate.downstairs" in res
    
    res2 = home_assistant.ha_list_entities("light")
    assert "light.living_room" in res2
    assert "climate.downstairs" not in res2


def test_ha_locks_security_requires_phrase(monkeypatch):
    class DummyClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def post(self, url, json):
            return DummyResponse({})
    
    monkeypatch.setattr(httpx, "Client", DummyClient)
    res2 = home_assistant.ha_locks_security("lock.front_door", "unlock")
    assert res2 == "ok"

def test_ha_lights_scenes(monkeypatch):
    class DummyClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def post(self, url, json):
            return DummyResponse({})
            
    monkeypatch.setattr(httpx, "Client", DummyClient)
    assert home_assistant.ha_lights_scenes("turn_on", "light.kitchen") == "ok"
    assert "error" in home_assistant.ha_lights_scenes("turn_on", "sensor.kitchen_temp")


def test_ha_climate_control(monkeypatch):
    class DummyClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def post(self, url, json):
            return DummyResponse({})
            
    monkeypatch.setattr(httpx, "Client", DummyClient)
    assert home_assistant.ha_climate_control("climate.living_room", temperature=72) == "ok"
    assert home_assistant.ha_climate_control("climate.living_room", hvac_mode="heat") == "ok"
    assert "error" in home_assistant.ha_climate_control("light.living_room", temperature=72)
    assert "error" in home_assistant.ha_climate_control("climate.living_room")


def test_ha_camera_snapshot():
    assert "error" in home_assistant.ha_camera_snapshot("light.living_room")
    res = home_assistant.ha_camera_snapshot("camera.front_porch")
    assert "Snapshot available at" in res
