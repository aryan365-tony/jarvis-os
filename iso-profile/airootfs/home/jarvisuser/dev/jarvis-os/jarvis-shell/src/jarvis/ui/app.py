"""Jarvis workspace — the AI-first, text-first shell UI.

Design note
-----------
The whole experience is built around progressive availability:

* The UI mounts and accepts text input **immediately** (no waiting on the model).
* An event pump drains the runtime's event bus and lights up capabilities
  (model, voice, health) as they arrive.
* Voice and text are two front-ends to one :class:`ConversationAgent`.
* Irreversible tools prompt a modal; nothing else blocks.
* Accessibility (reduced motion, high contrast) is honoured via CSS classes.
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from ..agent import ConversationAgent
from ..events import (
    HEALTH,
    LOG,
    MODEL_STATUS,
    VOICE_STATUS,
    Level,
    LogLine,
    ServiceState,
    ServiceStatus,
)
from ..memory import store
from ..runtime import Runtime
from .screens import ConfirmScreen, OnboardingScreen
from .widgets.composer import Composer
from .widgets.conversation import Conversation
from .widgets.status_panel import StatusPanel
from .widgets.statusbar import StatusBar


class JarvisApp(App):
    CSS_PATH = "jarvis.tcss"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("f2", "toggle_panel", "Backend activity"),
        Binding("ctrl+l", "focus_input", "Focus input"),
        Binding("ctrl+m", "toggle_motion", "Reduce motion"),
    ]

    def __init__(self, runtime: Runtime | None = None) -> None:
        super().__init__()
        self.runtime = runtime or Runtime()
        self._agent: ConversationAgent | None = None
        self._panel_visible = self.runtime.config.ui.show_status_panel_on_start

    # -- layout -------------------------------------------------------------
    def compose(self) -> ComposeResult:
        yield StatusBar(id="statusbar")
        with Horizontal(id="body"):
            with Vertical(id="main"):
                yield Conversation(id="conversation")
                yield Composer(id="composer")
            yield StatusPanel(id="status-panel")
        yield Static(
            "[dim]F2 backend • Ctrl+L input • Ctrl+M motion • Ctrl+Q quit[/]",
            id="hintbar",
        )

    # -- lifecycle ----------------------------------------------------------
    async def on_mount(self) -> None:
        self._apply_accessibility()
        self.query_one("#status-panel").display = self._panel_visible

        # Agent is created with UI-bound confirm + task callbacks.
        self._agent = ConversationAgent(
            confirm=self._confirm_async, on_task=self._on_task
        )

        conv = self.query_one(Conversation)
        await conv.add_system("Jarvis is online. Type to begin — voice will join when ready.")
        self.query_one(Composer).focus_input()

        # Start background services and the event pump. Nothing here blocks.
        self.runtime.start_background()
        self.run_worker(self._pump(), name="event-pump", exclusive=False)

        if not store.load_core_memory().get("onboarded"):
            self.call_after_refresh(self._run_onboarding)

    async def on_unmount(self) -> None:
        await self.runtime.shutdown()
        if self._agent:
            await self._agent.aclose()

    # -- accessibility ------------------------------------------------------
    def _apply_accessibility(self) -> None:
        ui = self.runtime.config.ui
        self.set_class(ui.reduced_motion, "reduced-motion")
        self.set_class(ui.high_contrast, "high-contrast")

    def action_toggle_motion(self) -> None:
        self.runtime.config.ui.reduced_motion = not self.runtime.config.ui.reduced_motion
        self._apply_accessibility()

    def action_toggle_panel(self) -> None:
        self._panel_visible = not self._panel_visible
        self.query_one("#status-panel").display = self._panel_visible

    def action_focus_input(self) -> None:
        self.query_one(Composer).focus_input()

    # -- onboarding ---------------------------------------------------------
    def _run_onboarding(self) -> None:
        def _done(prefs: dict | None) -> None:
            if prefs:
                self.runtime.config.ui.reduced_motion = prefs.get("reduced_motion", False)
                self.runtime.config.ui.high_contrast = prefs.get("high_contrast", False)
                self._apply_accessibility()
            store.set_core_memory("onboarded", "1")

        self.push_screen(OnboardingScreen(), _done)

    # -- event pump ---------------------------------------------------------
    async def _pump(self) -> None:
        """Drain the event bus and reflect state in the UI. Never blocks input."""
        sub = self.runtime.bus.subscribe(MODEL_STATUS, VOICE_STATUS, LOG, HEALTH)
        statusbar = self.query_one(StatusBar)
        panel = self.query_one(StatusPanel)
        composer = self.query_one(Composer)
        with sub:
            async for topic, payload in sub:
                if topic == MODEL_STATUS and isinstance(payload, ServiceStatus):
                    statusbar.model_state = payload.state
                    panel.set_service("model", payload.state, payload.detail)
                elif topic == VOICE_STATUS and isinstance(payload, ServiceStatus):
                    statusbar.voice_state = payload.state
                    panel.set_service("voice", payload.state, payload.detail)
                    composer.set_voice_state(payload.state)
                elif topic == LOG and isinstance(payload, LogLine):
                    panel.log_line(payload.source, payload.level, payload.message)

    # -- agent callbacks ----------------------------------------------------
    async def _confirm_async(self, name: str, args: dict) -> bool:
        # Show a modal and await the user's decision without freezing the app.
        return bool(await self.push_screen_wait(ConfirmScreen(name, args)))

    async def _on_task(self, tool_name: str, state: str, detail: str) -> None:
        self.runtime.bus.publish(
            LOG, LogLine("tool", Level.INFO, f"{tool_name}: {state} {detail}".strip())
        )

    # -- user input ---------------------------------------------------------
    def on_composer_submitted(self, message: Composer.Submitted) -> None:
        self.run_worker(self._handle_user(message.text), name="agent-turn", exclusive=False)

    async def _handle_user(self, text: str) -> None:
        conv = self.query_one(Conversation)
        await conv.add_user(text)
        streaming = await conv.begin_assistant()

        async def on_delta(chunk: str) -> None:
            streaming.append(chunk)
            conv.scroll_end(animate=False)

        assert self._agent is not None
        try:
            await self._agent.send(text, on_delta)
        finally:
            await conv.finalize_assistant(streaming)

