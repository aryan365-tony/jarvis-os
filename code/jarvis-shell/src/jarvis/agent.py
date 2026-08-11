"""Conversation agent: the single AI pipeline behind both text and voice.

Design note
-----------
Voice and text are two front-ends to *this* one agent, satisfying the
"same capabilities, shared history, identical pipeline" requirement. The agent:

1. keeps a running message list seeded from persistent memory;
2. streams assistant tokens out via a callback (the UI renders them live);
3. accumulates OpenAI-style streaming ``tool_calls``; when the model asks for a
   tool it runs it through the registry, appends the result, and continues the turn;
4. enforces a large safety step cap so a runaway model can never hang the interface in an infinite loop.

Everything is async so the render loop keeps animating while the model works.
"""

from __future__ import annotations

import asyncio
import json
from typing import Awaitable, Callable

from .config import get_config
from .llm_client import AsyncLLMClient
from .memory import store
from .tools.registry import execute, tool_schemas

# Streaming sink: called with each assistant text delta.
DeltaFn = Callable[[str], Awaitable[None]]
# Surface a tool starting/finishing to the UI (active tasks widget).
TaskFn = Callable[[str, str, str], Awaitable[None]]  # (tool_name, state, detail)

# Rolling context window: caps memory growth and keeps requests under the
# model's context limit. Index 0 (system message) is always preserved.
MAX_CONTEXT_MESSAGES = 80


class ConversationAgent:
    def __init__(
        self,
        llm: AsyncLLMClient | None = None,
        on_task: TaskFn | None = None,
    ) -> None:
        self._cfg = get_config()
        self._llm = llm or AsyncLLMClient()
        self._on_task = on_task
        self._messages: list[dict] = []
        self._send_lock = asyncio.Lock()
        self._seed_history()

    def _trim_messages(self) -> None:
        """Cap in-memory history so a long session can't leak memory or
        exceed the model's context window (BUG-001)."""
        if len(self._messages) > MAX_CONTEXT_MESSAGES:
            self._messages = [self._messages[0]] + self._messages[-(MAX_CONTEXT_MESSAGES - 1):]

    def _seed_history(self) -> None:
        """Prime context from persistent core memory + recent session log."""
        system = self._cfg.llm.system_prompt
        core = store.load_core_memory()
        if core:
            facts = "\n".join(f"- {k}: {v}" for k, v in core.items())
            system += f"\n\nKnown context about the user and machine:\n{facts}"
        self._messages = [{"role": "system", "content": system}]
        self._messages.extend(store.recent_session(limit=20))

    async def send(self, user_text: str, on_delta: DeltaFn) -> str:
        """Run one full turn (possibly multi-step with tools). Returns final text.

        Serialized via ``_send_lock``: text and voice front-ends share this
        agent and its ``_messages`` list, so concurrent turns would interleave
        appends and corrupt the conversation sent to the model (BUG-002).
        """
        async with self._send_lock:
            return await self._send_locked(user_text, on_delta)

    async def _send_locked(self, user_text: str, on_delta: DeltaFn) -> str:
        self._messages.append({"role": "user", "content": user_text})
        self._trim_messages()
        store.append_session("user", user_text)

        final_text = ""

        # Hard safety guard against infinite streaming bugs (was max_turns_per_session_task)
        for _step in range(9999):
            content, tool_calls = await self._one_completion(on_delta)
            if content:
                final_text = content
                self._messages.append({"role": "assistant", "content": content})
                self._trim_messages()

            if not tool_calls:
                break

            # Execute each requested tool, then loop so the model can react.
            self._messages.append(
                {"role": "assistant", "content": content or None, "tool_calls": tool_calls}
            )
            self._trim_messages()
            for tc in tool_calls:
                name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                if self._on_task:
                    await self._on_task(name, "running", "")
                result = await execute(name, args)
                if self._on_task:
                    await self._on_task(name, "done", result[:120])
                self._messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.get("id", name),
                        "name": name,
                        "content": result,
                    }
                )
                self._trim_messages()

        if final_text:
            store.append_session("assistant", final_text)
        return final_text

    async def _one_completion(self, on_delta: DeltaFn) -> tuple[str, list[dict]]:
        """Stream one model completion, returning (text, tool_calls)."""
        content_parts: list[str] = []
        # tool_calls arrive as indexed deltas that must be stitched together.
        tool_acc: dict[int, dict] = {}

        try:
            async for chunk in self._llm.stream_chat(self._messages, tool_schemas()):
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta", {})

                text = delta.get("content")
                if text:
                    content_parts.append(text)
                    await on_delta(text)

                for tcd in delta.get("tool_calls", []) or []:
                    idx = tcd.get("index", 0)
                    slot = tool_acc.setdefault(
                        idx,
                        {"id": tcd.get("id", ""), "type": "function",
                         "function": {"name": "", "arguments": ""}},
                    )
                    fn = tcd.get("function", {})
                    if fn.get("name"):
                        slot["function"]["name"] = fn["name"]
                    if fn.get("arguments"):
                        slot["function"]["arguments"] += fn["arguments"]
                    if tcd.get("id"):
                        slot["id"] = tcd["id"]
        except Exception as e:
            # Graceful degradation: surface a readable error instead of crashing.
            msg = f"\n[assistant unavailable: {e}]"
            await on_delta(msg)
            return ("".join(content_parts) + msg, [])

        tool_calls = [tool_acc[i] for i in sorted(tool_acc)] if tool_acc else []
        return ("".join(content_parts), tool_calls)

    async def aclose(self) -> None:
        await self._llm.aclose()
