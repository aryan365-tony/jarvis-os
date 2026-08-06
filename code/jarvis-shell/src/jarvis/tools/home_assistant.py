"""Home Assistant control (home_assistant).

Design note
-----------
Direct API integration via httpx. Token fetched from environment variable.
"""
from __future__ import annotations

import os
import httpx

from ..config import get_config
from .registry import register


def _get_client() -> httpx.Client:
    cfg = get_config()
    token = os.environ.get(cfg.tools.home_assistant_token_env, "")
    return httpx.Client(
        base_url=f"{cfg.tools.home_assistant_url.rstrip('/')}/api/",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=10.0,
    )


@register(
    "ha_list_entities",
    risk="low",
    domain="home_assistant",
    description="List available Home Assistant entities (optionally filtered by domain).",
    parameters={
        "type": "object",
        "properties": {
            "domain": {"type": "string", "description": "Filter by HA domain (e.g., 'light', 'climate')."},
        },
    },
)
def ha_list_entities(domain: str = "") -> str:
    try:
        with _get_client() as client:
            resp = client.get("states")
            resp.raise_for_status()
            entities = resp.json()
    except Exception as e:
        return f"error: {e}"

    lines = []
    for e in entities:
        if domain and not e["entity_id"].startswith(f"{domain}."):
            continue
        lines.append(f"{e['entity_id']}: {e['state']} (name: {e['attributes'].get('friendly_name', 'unknown')})")
    
    if not lines:
        return "No entities found."
    return "\n".join(lines)[:8000]


@register(
    "ha_get_state",
    risk="low",
    domain="home_assistant",
    description="Get detailed state and attributes of a specific HA entity.",
    parameters={
        "type": "object",
        "properties": {
            "entity_id": {"type": "string"},
        },
        "required": ["entity_id"],
    },
)
def ha_get_state(entity_id: str) -> str:
    try:
        with _get_client() as client:
            resp = client.get(f"states/{entity_id}")
            resp.raise_for_status()
            return str(resp.json())[:8000]
    except Exception as e:
        return f"error: {e}"


def _call_service(domain: str, service: str, entity_id: str | None = None, **kwargs) -> str:
    payload = kwargs
    if entity_id:
        payload["entity_id"] = entity_id
    try:
        with _get_client() as client:
            resp = client.post(f"services/{domain}/{service}", json=payload)
            resp.raise_for_status()
            return "ok"
    except Exception as e:
        return f"error: {e}"


@register(
    "ha_lights_scenes",
    risk="medium",
    domain="home_assistant",
    description="Control lights or activate scenes.",
    parameters={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["turn_on", "turn_off", "toggle"]},
            "entity_id": {"type": "string", "description": "light.* or scene.* entity_id"},
        },
        "required": ["action", "entity_id"],
    },
)
def ha_lights_scenes(action: str, entity_id: str) -> str:
    domain = entity_id.split(".")[0]
    if domain not in ("light", "scene"):
        return "error: must be a light or scene entity"
    return _call_service(domain, action, entity_id)


@register(
    "ha_climate_control",
    risk="medium",
    domain="home_assistant",
    description="Control climate/thermostat entities.",
    parameters={
        "type": "object",
        "properties": {
            "entity_id": {"type": "string"},
            "temperature": {"type": "number"},
            "hvac_mode": {"type": "string", "enum": ["off", "heat", "cool", "heat_cool", "auto", "dry", "fan_only"]},
        },
        "required": ["entity_id"],
    },
)
def ha_climate_control(entity_id: str, temperature: float | None = None, hvac_mode: str | None = None) -> str:
    if not entity_id.startswith("climate."):
        return "error: must be a climate entity"
    if temperature is not None:
        return _call_service("climate", "set_temperature", entity_id, temperature=temperature)
    if hvac_mode:
        return _call_service("climate", "set_hvac_mode", entity_id, hvac_mode=hvac_mode)
    return "error: must provide temperature or hvac_mode"


@register(
    "ha_media_player",
    risk="medium",
    domain="home_assistant",
    description="Control HA media players.",
    parameters={
        "type": "object",
        "properties": {
            "entity_id": {"type": "string"},
            "action": {"type": "string", "enum": ["media_play_pause", "media_next_track", "media_previous_track", "volume_up", "volume_down"]},
        },
        "required": ["entity_id", "action"],
    },
)
def ha_media_player(entity_id: str, action: str) -> str:
    if not entity_id.startswith("media_player."):
        return "error: must be a media_player entity"
    return _call_service("media_player", action, entity_id)


@register(
    "ha_locks_security",
    risk="high",
    domain="home_assistant",
    description="Unlock locks or disarm alarms (high tier, requires confirm phrase).",
    parameters={
        "type": "object",
        "properties": {
            "entity_id": {"type": "string"},
            "action": {"type": "string", "enum": ["unlock", "lock", "alarm_disarm", "alarm_arm_home", "alarm_arm_away"]},
            "confirm_phrase": {"type": "string", "description": "Must be exactly: 'I confirm security action'"},
        },
        "required": ["entity_id", "action", "confirm_phrase"],
    },
)
def ha_locks_security(entity_id: str, action: str, confirm_phrase: str) -> str:
    if confirm_phrase != "I confirm security action":
        return "error: missing or incorrect confirm_phrase"
    domain = entity_id.split(".")[0]
    if domain not in ("lock", "alarm_control_panel"):
        return "error: must be a lock or alarm_control_panel entity"
    return _call_service(domain, action, entity_id)


@register(
    "ha_camera_snapshot",
    risk="medium",
    domain="home_assistant",
    description="Request a snapshot URL or image data from a camera (simulated as text here).",
    parameters={
        "type": "object",
        "properties": {
            "entity_id": {"type": "string"},
        },
        "required": ["entity_id"],
    },
)
def ha_camera_snapshot(entity_id: str) -> str:
    if not entity_id.startswith("camera."):
        return "error: must be a camera entity"
    try:
        cfg = get_config()
        token = os.environ.get(cfg.tools.home_assistant_token_env, "")
        return f"Snapshot available at: {cfg.tools.home_assistant_url}/api/camera_proxy/{entity_id}?token={token}"
    except Exception as e:
        return f"error: {e}"


@register(
    "ha_automation_toggle",
    risk="medium",
    domain="home_assistant",
    description="Turn an automation on or off.",
    parameters={
        "type": "object",
        "properties": {
            "entity_id": {"type": "string"},
            "action": {"type": "string", "enum": ["turn_on", "turn_off", "toggle", "trigger"]},
        },
        "required": ["entity_id", "action"],
    },
)
def ha_automation_toggle(entity_id: str, action: str) -> str:
    if not entity_id.startswith("automation."):
        return "error: must be an automation entity"
    return _call_service("automation", action, entity_id)
