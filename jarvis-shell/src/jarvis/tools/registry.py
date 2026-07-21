"""Tool registry with risk tiers, per-turn budgets, and async execution.

Design note
-----------
Fixes three issues from the original:
* irreversible tools are confirmed by the registry via an **async** callback
  (tools no longer receive ``confirm_async`` as a function argument — that was
  the ``optimize_backend`` signature bug);
* ``max_calls_per_turn`` is now enforced;
* blocking tool functions run in a worker thread so the UI never freezes.

Each tool also carries an OpenAI-style JSON schema so the agent can advertise
them to the model.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal

from ..audit.chain import audit_log

Risk = Literal["safe", "reversible", "irreversible"]

# An async predicate the UI supplies: given (tool_name, args) -> user approves?
ConfirmFn = Callable[[str, dict], Awaitable[bool]]


@dataclass
class Tool:
    name: str
    risk: Risk
    fn: Callable[..., str]
    description: str = ""
    parameters: dict = field(default_factory=lambda: {"type": "object", "properties": {}})
    max_calls_per_turn: int = 3


REGISTRY: dict[str, Tool] = {}


def register(
    name: str,
    risk: Risk,
    description: str = "",
    parameters: dict | None = None,
    max_calls_per_turn: int = 3,
):
    def deco(fn):
        REGISTRY[name] = Tool(
            name=name,
            risk=risk,
            fn=fn,
            description=description or (fn.__doc__ or "").strip(),
            parameters=parameters or {"type": "object", "properties": {}},
            max_calls_per_turn=max_calls_per_turn,
        )
        return fn

    return deco


def tool_schemas() -> list[dict]:
    """OpenAI-compatible tool definitions for the chat request."""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in REGISTRY.values()
    ]


async def execute(
    name: str,
    args: dict[str, Any],
    confirm: ConfirmFn | None = None,
    call_counts: dict[str, int] | None = None,
) -> str:
    """Execute a tool safely. Returns a string result (never raises)."""
    tool = REGISTRY.get(name)
    if tool is None:
        audit_log("tool_call_rejected", {"name": name, "reason": "unknown_tool"})
        return f"error: unknown tool {name}"

    # Per-turn call budget.
    if call_counts is not None:
        used = call_counts.get(name, 0)
        if used >= tool.max_calls_per_turn:
            audit_log("tool_call_rejected", {"name": name, "reason": "budget_exceeded"})
            return f"error: call budget exceeded for {name}"
        call_counts[name] = used + 1

    if tool.risk == "irreversible":
        approved = False
        if confirm is not None:
            try:
                approved = await confirm(name, args)
            except Exception:
                approved = False
        if not approved:
            audit_log("tool_call_denied", {"name": name, "args": args})
            return "denied by user"

    audit_log("tool_call_start", {"name": name, "args": args, "risk": tool.risk})
    try:
        # Run the (possibly blocking) tool off the event loop.
        result = await asyncio.to_thread(tool.fn, **args)
        audit_log("tool_call_ok", {"name": name})
        return result
    except Exception as e:  # tools must never crash the agent
        audit_log("tool_call_error", {"name": name, "error": str(e)})
        return f"error: {e}"
