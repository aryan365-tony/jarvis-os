import httpx, json
from typing import Iterator
from .config import load_config

cfg = load_config()

class LLMClient:
    def __init__(self):
        self._client = httpx.Client(timeout=cfg.llm.request_timeout_s)

    def stream_chat(self, messages: list[dict], tools: list[dict]) -> Iterator[dict]:
        payload = {
            "model": cfg.llm.model_name,
            "messages": messages,
            "tools": tools,
            "stream": True,
        }
        with self._client.stream(
            "POST", cfg.llm.endpoint, json=payload
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data = line[len("data: "):]
                if data.strip() == "[DONE]":
                    return
                yield json.loads(data)
