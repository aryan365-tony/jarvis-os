"""Modal screens: irreversible-action confirmation and first-run onboarding.

Both are non-blocking overlays — the rest of the shell keeps running underneath.
Onboarding is intentionally short: it explains that Jarvis works by text now and
by voice when ready, offers accessibility toggles, and gets out of the way.
"""

from __future__ import annotations

import json

from textual.app import ComposeResult
from textual.containers import Center, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


class ConfirmScreen(ModalScreen[bool]):
    """Yes/No confirmation for an irreversible tool call."""

    def __init__(self, tool_name: str, args: dict) -> None:
        super().__init__()
        self._tool = tool_name
        self._args = args

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(classes="dialog"):
                yield Label("Confirm action", classes="dialog-title")
                yield Static(f"Jarvis wants to run [b]{self._tool}[/b].", classes="dialog-body")
                pretty = json.dumps(self._args, indent=2) if self._args else "(no arguments)"
                yield Static(pretty, classes="dialog-code")
                with Center():
                    yield Button("Approve", variant="success", id="approve")
                    yield Button("Deny", variant="error", id="deny")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "approve")


class OnboardingScreen(ModalScreen[dict]):
    """Compact first-run walkthrough. Returns chosen accessibility prefs."""

    STEPS = [
        (
            "Welcome to Jarvis",
            "Your AI-first assistant. It's already running — just start typing.",
        ),
        (
            "Text now, voice soon",
            "Type to Jarvis at any time. Voice activates automatically in the "
            "background and you can switch to it seamlessly once it's ready.",
        ),
        (
            "Comfort & accessibility",
            "Use the buttons below to tune motion and contrast. You can change "
            "these later from the status panel (F2).",
        ),
        (
            "You're ready",
            "Press Enter to begin. Tip: F2 shows backend activity, Ctrl+Q exits.",
        ),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._i = 0
        self._prefs = {"reduced_motion": False, "high_contrast": False}

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(classes="dialog onboarding"):
                self._title = Label(self.STEPS[0][0], classes="dialog-title")
                yield self._title
                self._body = Static(self.STEPS[0][1], classes="dialog-body")
                yield self._body
                with Center(id="onboarding-toggles"):
                    yield Button("Reduce motion", id="toggle-motion")
                    yield Button("High contrast", id="toggle-contrast")
                with Center():
                    yield Button("Next  ▸", variant="primary", id="next")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "toggle-motion":
            self._prefs["reduced_motion"] = not self._prefs["reduced_motion"]
            event.button.variant = "success" if self._prefs["reduced_motion"] else "default"
        elif event.button.id == "toggle-contrast":
            self._prefs["high_contrast"] = not self._prefs["high_contrast"]
            event.button.variant = "success" if self._prefs["high_contrast"] else "default"
        elif event.button.id == "next":
            self._advance()

    def _advance(self) -> None:
        self._i += 1
        if self._i >= len(self.STEPS):
            self.dismiss(self._prefs)
            return
        title, body = self.STEPS[self._i]
        self._title.update(title)
        self._body.update(body)
