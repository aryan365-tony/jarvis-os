"""Event vocabulary shared across the shell.

Design note
-----------
The shell is organised around a single in-process async event bus (see
``eventbus.py``). Subsystems never call each other directly for state changes;
they publish events and subscribe to the ones they care about. This keeps the
UI, agent, voice, and readiness services loosely coupled so any of them can be
missing or slow without freezing the others.

Topics are plain strings (constants below) and payloads are small dataclasses so
they are easy to log, serialise, and reason about.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# --- Topics -----------------------------------------------------------------

# Lifecycle of the LLM backend (llama-server).
MODEL_STATUS = "model.status"
# Lifecycle of the voice subsystem (STT/wake/TTS).
VOICE_STATUS = "voice.status"
# A line for the backend activity panel (startup tasks, warnings, errors).
LOG = "system.log"
# Health/metrics tick for the HUD status bar.
HEALTH = "system.health"
# User submitted a message (from text composer or voice transcript).
USER_MESSAGE = "conversation.user_message"
# Streaming assistant token / lifecycle.
ASSISTANT_DELTA = "conversation.assistant_delta"
ASSISTANT_DONE = "conversation.assistant_done"
# A tool started / finished (drives "active tasks" widget).
TASK_UPDATE = "task.update"
# A non-intrusive notification for the user.
NOTIFY = "system.notify"


class Level(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ServiceState(str, Enum):
    """Generic progressive-availability state machine for any subsystem."""

    UNAVAILABLE = "unavailable"
    INITIALIZING = "initializing"
    DEGRADED = "degraded"
    READY = "ready"
    ERROR = "error"


# --- Payloads ---------------------------------------------------------------


@dataclass(slots=True)
class ServiceStatus:
    name: str
    state: ServiceState
    detail: str = ""


@dataclass(slots=True)
class LogLine:
    source: str
    level: Level
    message: str


@dataclass(slots=True)
class HealthSnapshot:
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class UserMessage:
    text: str
    source: str = "text"  # "text" | "voice"


@dataclass(slots=True)
class AssistantDelta:
    turn_id: int
    text: str


@dataclass(slots=True)
class AssistantDone:
    turn_id: int
    text: str


@dataclass(slots=True)
class TaskUpdate:
    task_id: str
    label: str
    state: ServiceState
    detail: str = ""


@dataclass(slots=True)
class Notification:
    title: str
    body: str = ""
    level: Level = Level.INFO
