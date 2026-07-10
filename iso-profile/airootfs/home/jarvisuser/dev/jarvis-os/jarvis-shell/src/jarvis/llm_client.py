"""Async streaming client for the local llama.cpp OpenAI-compatible server.

Design note
-----------
The old client was synchronous (``httpx.Client`` + blocking ``iter_lines``).
Called from the Textual event loop it would freeze every animation on every
token. This version is fully async so streaming happens off the render path and
the HUD keeps moving while the model talks.
"""

from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from .config import get_config


class AsyncLLMClient:
    def __init__(self) -> None:
        cfg = get_config()
        self._cfg = cfg
        # A single shared client with keep-alive avoids per-request handshakes.
        self._client = httpx.AsyncClient(timeout=cfg.llm.request_timeout_s)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def stream_chat(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AsyncIterator[dict]:
        """Yield parsed SSE chunks from ``/v1/chat/completions``.

        Tools are only included when non-empty; some templates reject an empty
        ``tools`` array.
        """
        payload: dict = {
            "model": self._cfg.llm.model_name,
            "messages": messages,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        async with self._client.stream(
            "POST", self._cfg.llm.endpoint, json=payload
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data = line[len("data: ") :]
                if data.strip() == "[DONE]":
                    return
                try:
                    yield json.loads(data)
                except json.JSONDecodeError:
                    # Be resilient to keep-alive comments / partial frames.
                    continue


# Backwards-compatible alias for existing imports/tests.
LLMClient = AsyncLLMClient
