"""Conversation view: scrollable message list with live-streaming assistant text.

Design note
-----------
Streaming updates a lightweight ``Static`` (fast, smooth, no reflow storms). On
completion the message is re-rendered as Markdown so code blocks and formatting
look right — matching the "streaming responses + markdown + code formatting"
requirement without paying markdown-parse cost on every token.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Markdown, Static


class Message(Static):
    """A single finalized message bubble (user or assistant)."""

    def __init__(self, role: str, text: str) -> None:
        super().__init__()
        self._role = role
        self._text = text
        self.add_class(role)  # "user" | "assistant" | "system"

    def compose(self) -> ComposeResult:
        who = {"user": "You", "assistant": "Jarvis", "system": "System"}.get(
            self._role, self._role
        )
        yield Static(who, classes="who")
        yield Markdown(self._text, classes="body")


class StreamingMessage(Static):
    """An assistant message being streamed token-by-token."""

    def __init__(self) -> None:
        super().__init__()
        self.add_class("assistant")
        self._buffer = ""
        self._body: Static | None = None

    def compose(self) -> ComposeResult:
        yield Static("Jarvis", classes="who")
        self._body = Static("▋", classes="body streaming")
        yield self._body

    def on_mount(self) -> None:
        # Flush any tokens that arrived before compose ran, so the first message
        # streams visibly instead of only appearing on finalize.
        if self._body is not None and self._buffer:
            self._body.update(self._buffer + "▋")

    def append(self, text: str) -> None:
        self._buffer += text
        if self._body is not None and self._body.is_mounted:
            # Cursor glyph communicates "still thinking" motion cheaply.
            self._body.update(self._buffer + "▋")

    @property
    def text(self) -> str:
        return self._buffer


class Conversation(VerticalScroll):
    """Ordered list of messages; owns streaming lifecycle."""

    async def add_user(self, text: str) -> None:
        await self.mount(Message("user", text))
        self.scroll_end(animate=False)

    async def add_system(self, text: str) -> None:
        await self.mount(Message("system", text))
        self.scroll_end(animate=False)

    async def begin_assistant(self) -> StreamingMessage:
        msg = StreamingMessage()
        await self.mount(msg)
        self.scroll_end(animate=False)
        return msg

    async def finalize_assistant(self, streaming: StreamingMessage) -> None:
        """Replace the streaming widget with a rendered Markdown message."""
        text = streaming.text or ""
        final = Message("assistant", text)
        await self.mount(final, after=streaming)
        await streaming.remove()
        self.scroll_end(animate=False)
