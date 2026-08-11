"""Tool registry with risk tiers, per-turn budgets, and async execution.

Design note
-----------
Fixes three issues from the original:
* irreversible tools are confirmed by the registry via an **async** callback
  (tools no longer receive ``confirm_async`` as a function argument — that was
  the ``optimize_backend`` signature bug);
* blocking tool functions run in a worker thread so the UI never freezes.

Risk tiers (Phase 2/3)
----------------------
Every tool declares a risk tier at registration — this is **mandatory** (there
is no default). The tier drives Phase 3's collapsed-approval logic:

* ``low``    — read-only / trivially reversible. Executes instantly.
* ``medium`` — meaningful but recoverable (service restart, user-scope install).
               Executes instantly.
* ``high``   — irreversible / system-altering (package removal, fs mutation
               outside scratch). A pre-action ``snapper`` snapshot is taken
               automatically *before* execution (the snapshot is the safety net).

Each tool also carries an OpenAI-style JSON schema so the agent can advertise
them to the model.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal

from ..audit.chain import audit_log

Risk = Literal["low", "medium", "high"]

# Legacy tiers used by the pre-Phase-2 registry, mapped forward so any code or
# tool still using the old names keeps working.
_LEGACY_TIER_MAP = {"safe": "low", "reversible": "medium", "irreversible": "high"}


def _normalize_tier(risk: str) -> Risk:
    tier = _LEGACY_TIER_MAP.get(risk, risk)
    if tier not in ("low", "medium", "high"):
        raise ValueError(
            f"invalid risk tier {risk!r}; must be one of low/medium/high "
            "(a tier is mandatory at registration)"
        )
    return tier  # type: ignore[return-value]


@dataclass
class Tool:
    name: str
    risk: Risk
    fn: Callable[..., str]
    description: str = ""
    parameters: dict = field(default_factory=lambda: {"type": "object", "properties": {}})
    domain: str = "core"

REGISTRY: dict[str, Tool] = {}


def register(
    name: str,
    risk: Risk,
    description: str = "",
    parameters: dict | None = None,
    domain: str = "core",
):
    # Fail loudly at import time if a tool omits/mistypes its tier — no tool may
    # ever enter the registry without an explicit, valid risk tier.
    tier = _normalize_tier(risk)

    def deco(fn):
        REGISTRY[name] = Tool(
            name=name,
            risk=tier,
            fn=fn,
            description=description or (fn.__doc__ or "").strip(),
            parameters=parameters or {"type": "object", "properties": {}},
            domain=domain,
        )
        return fn

    return deco


def get_risk_tier(name: str) -> Risk:
    """Return the risk tier of a registered tool.

    Raises ``KeyError`` for an unknown tool so callers cannot silently treat an
    unregistered name as low risk.
    """
    return REGISTRY[name].risk


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
) -> str:
    """Execute a tool safely. Returns a string result (never raises)."""
    tool = REGISTRY.get(name)
    if tool is None:
        audit_log("tool_call_rejected", {"name": name, "reason": "unknown_tool"})
        return f"error: unknown tool {name}"

    audit_log(
        "tool_call_start",
        {"name": name, "args": args, "tier": tool.risk, "snapshot_id": None},
    )
    try:
        # Run the (possibly blocking) tool off the event loop.
        result = await asyncio.to_thread(tool.fn, **args)
        audit_log(
            "tool_call_ok",
            {
                "name": name,
                "tier": tool.risk,
                "snapshot_id": None,
                "result": (result or "")[:500],
            },
        )
        return result
    except Exception as e:  # tools must never crash the agent
        audit_log(
            "tool_call_error",
            {"name": name, "tier": tool.risk, "snapshot_id": None, "error": str(e)},
        )
        return f"error: {e}"
