"""Top HUD status bar: model + voice state, clock, and health at a glance.

Only shows what is relevant; state is driven entirely by event-bus updates so it
reflects progressive availability in real time.
"""

from __future__ import annotations

from datetime import datetime

from textual.reactive import reactive
from textual.widgets import Static

from ...events import ServiceState

_DOT = {
    ServiceState.READY: "green",
    ServiceState.INITIALIZING: "yellow",
    ServiceState.DEGRADED: "orange1",
    ServiceState.UNAVAILABLE: "grey50",
    ServiceState.ERROR: "red",
}


class StatusBar(Static):
    model_state: reactive[ServiceState] = reactive(ServiceState.INITIALIZING)
    voice_state: reactive[ServiceState] = reactive(ServiceState.INITIALIZING)
    clock: reactive[str] = reactive("")

    def on_mount(self) -> None:
        self._tick()
        self.set_interval(1.0, self._tick)

    def _tick(self) -> None:
        self.clock = datetime.now().strftime("%H:%M")

    def _pill(self, label: str, state: ServiceState) -> str:
        color = _DOT.get(state, "grey50")
        return f"[{color}]●[/] {label} [dim]{state.value}[/]"

    def render(self) -> str:
        left = "[b]JARVIS[/b]"
        mid = "   ".join(
            (
                self._pill("model", self.model_state),
                self._pill("voice", self.voice_state),
            )
        )
        return f"{left}    {mid}    [dim]{self.clock}[/]"
