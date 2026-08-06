"""Calendar control (calendar).

Design note
-----------
Uses caldav for CalDAV integration. 
Token/credentials fetched from environment variables.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

try:
    import caldav
    _HAS_CALDAV = True
except ImportError:
    _HAS_CALDAV = False
from .registry import register


def _get_client() -> caldav.DAVClient | str:
    url = os.environ.get("CALDAV_URL")
    user = os.environ.get("CALDAV_USER")
    password = os.environ.get("CALDAV_PASSWORD")
    if not url or not user or not password:
        return "error: missing CALDAV_URL, CALDAV_USER, or CALDAV_PASSWORD env vars"
    
    if not _HAS_CALDAV:
        return "error: caldav module is not installed. Calendar tools are disabled."
        
    return caldav.DAVClient(url=url, username=user, password=password)


@register(
    "calendar_read",
    risk="low",
    domain="calendar",
    description="Read upcoming calendar events.",
)
def calendar_read() -> str:
    client = _get_client()
    if isinstance(client, str):
        return client
    try:
        principal = client.principal()
        calendars = principal.calendars()
        if not calendars:
            return "No calendars found."
        
        cal = calendars[0]
        events = cal.events()
        
        lines = []
        for e in events[:20]:
            e.load()
            comp = getattr(e.vobject_instance, "vevent", None)
            if comp:
                lines.append(f"Event: {comp.summary.value} at {comp.dtstart.value}")
        
        if not lines:
            return "No upcoming events found."
        return "\n".join(lines)[:8000]
    except Exception as e:
        return f"error: {e}"


@register(
    "calendar_create_event",
    risk="medium",
    domain="calendar",
    description="Create a new calendar event.",
    parameters={
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "Event title."},
            "start": {"type": "string", "description": "Start time in ISO format (e.g. 2026-08-06T10:00:00Z)."},
            "end": {"type": "string", "description": "End time in ISO format."},
        },
        "required": ["summary", "start", "end"],
    },
)
def calendar_create_event(summary: str, start: str, end: str) -> str:
    client = _get_client()
    if isinstance(client, str):
        return client
    try:
        principal = client.principal()
        calendars = principal.calendars()
        if not calendars:
            return "error: no calendars found"
        
        cal = calendars[0]
        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
        
        cal.save_event(
            dtstart=start_dt,
            dtend=end_dt,
            summary=summary,
        )
        return "ok: event created"
    except Exception as e:
        return f"error: {e}"
