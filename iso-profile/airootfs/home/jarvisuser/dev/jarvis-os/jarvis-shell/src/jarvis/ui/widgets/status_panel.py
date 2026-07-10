"""Backend Activity panel: observable but non-intrusive.

Hidden by default (toggle with F2). Shows service health and a rolling log of
startup tasks, warnings, and errors — the "observable but not in your face"
requirement. Fed entirely from the event bus.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Label, RichLog, Static

from ...events import Level, ServiceState

_STATE_MARK = {
    ServiceState.READY: "[green]●[/]",
    ServiceState.INITIALIZING: "[yellow]●[/]",
    ServiceState.DEGRADED: "[orange1]●[/]",
    ServiceState.UNAVAILABLE: "[grey50]●[/]",
    ServiceState.ERROR: "[red]●[/]",
}

_LEVEL_COLOR = {
    Level.DEBUG: "grey50",
    Level.INFO: "white",
    Level.WARNING: "orange1",
    Level.ERROR: "red",
}


class StatusPanel(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("Backend Activity", classes="panel-title")
        self._services = Static("", classes="svc-list")
        yield self._services
        self._log = RichLog(highlight=False, markup=True, wrap=True, classes="svc-log")
        yield self._log
        self._states: dict[str, ServiceState] = {}

    def set_service(self, name: str, state: ServiceState, detail: str) -> None:
        self._states[name] = state
        lines = [
            f"{_STATE_MARK.get(st, '●')} {n} [dim]{st.value}[/]"
            for n, st in sorted(self._states.items())
        ]
        self._services.update("\n".join(lines))

    def log_line(self, source: str, level: Level, message: str) -> None:
        color = _LEVEL_COLOR.get(level, "white")
        self._log.write(f"[dim]{source}[/] [{color}]{message}[/]")
