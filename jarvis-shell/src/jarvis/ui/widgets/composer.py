"""Composer: the text input row with voice-state affordance.

Text is always available. When voice becomes ready the hint updates so the user
can switch seamlessly; when it's unavailable the row makes that state clear
without blocking anything.
"""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message as TextualMessage
from textual.widgets import Input, Static

from ...events import ServiceState


class Composer(Horizontal):
    class Submitted(TextualMessage):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    def compose(self) -> ComposeResult:
        self._voice_hint = Static("", classes="voice-hint")
        yield self._voice_hint
        self._input = Input(
            placeholder="Ask Jarvis…  (Enter to send)", id="composer-input"
        )
        yield self._input

    def focus_input(self) -> None:
        self._input.focus()

    def set_voice_state(self, state: ServiceState) -> None:
        glyph = {
            ServiceState.READY: "[green]🎙 voice ready[/]",
            ServiceState.INITIALIZING: "[yellow]🎙 …[/]",
            ServiceState.DEGRADED: "[orange1]🎙 limited[/]",
            ServiceState.UNAVAILABLE: "[grey50]⌨ text[/]",
            ServiceState.ERROR: "[red]🎙 error[/]",
        }.get(state, "[grey50]⌨ text[/]")
        self._voice_hint.update(glyph)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.stop()
        if not text:
            return
        self._input.value = ""
        self.post_message(self.Submitted(text))
