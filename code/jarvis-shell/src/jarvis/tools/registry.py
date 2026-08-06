"""Tool registry with risk tiers, per-turn budgets, and async execution.

Design note
-----------
Fixes three issues from the original:
* irreversible tools are confirmed by the registry via an **async** callback
  (tools no longer receive ``confirm_async`` as a function argument — that was
  the ``optimize_backend`` signature bug);
* ``max_calls_per_turn`` is now enforced, plus a global per-turn ceiling;
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
               automatically *before* execution (the snapshot is the safety net,
               not a human gate).

The confirm callback returns an :class:`ApprovalResult` carrying the snapshot id
(if one was taken) so the audit entry can link the action to its snapshot. A
plain ``bool`` is also accepted for backwards compatibility.

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

# Global ceiling on total tool calls in a single turn. Raised from the original
# small per-tool default to accommodate the much larger Phase 2 tool surface,
# but kept finite so a runaway model can never issue unbounded system commands.
PER_TURN_TOOL_BUDGET = 24


@dataclass
class ApprovalResult:
    """Outcome of a tool-approval request.

    ``approved`` gates execution; ``snapshot_id`` is the id of the pre-action
    snapshot taken for a ``high``-tier tool (``None`` for low/medium), threaded
    into the audit entry so the action links to its rollback point.
    """

    approved: bool
    snapshot_id: str | None = None


# An async predicate the UI supplies: given (tool_name, args) -> ApprovalResult
# (a plain bool is also accepted and treated as ApprovalResult(bool, None)).
ConfirmFn = Callable[[str, dict], Awaitable["ApprovalResult | bool"]]


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
    max_calls_per_turn: int = 3
    domain: str = "core"

REGISTRY: dict[str, Tool] = {}


def register(
    name: str,
    risk: Risk,
    description: str = "",
    parameters: dict | None = None,
    max_calls_per_turn: int = 3,
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
            max_calls_per_turn=max_calls_per_turn,
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


def domain_enabled(domain: str) -> bool:
    """Single source of truth for whether a tool's domain may execute.

    ``"core"`` (native OS tools already in this repo) is always enabled and is
    not present in config — it cannot be turned off via config, matching the
    existing tools' behavior today. Every other domain must be explicitly
    opted into via ``config.tools.enabled_domains``.
    """
    if domain == "core":
        return True
    from .. import config as _config  # local import avoids a config<->registry cycle
    return _config.get_config().tools.enabled_domains.get(domain, False)


async def _resolve_approval(
    confirm: ConfirmFn | None, name: str, args: dict
) -> ApprovalResult:
    if confirm is None:
        # No approver wired (e.g. tests): high-tier tools are denied by default
        # so they can never execute without the snapshot safety net.
        return ApprovalResult(approved=False)
    try:
        result = await confirm(name, args)
    except Exception:
        return ApprovalResult(approved=False)
    if isinstance(result, ApprovalResult):
        return result
    return ApprovalResult(approved=bool(result))


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

    if not domain_enabled(tool.domain):
        audit_log("tool_call_rejected", {"name": name, "reason": "domain_disabled", "domain": tool.domain})
        return f"error: '{tool.domain}' tools are disabled in config"

    # Per-turn call budgets (per-tool and global ceiling).
    if call_counts is not None:
        used = call_counts.get(name, 0)
        if used >= tool.max_calls_per_turn:
            audit_log("tool_call_rejected", {"name": name, "reason": "budget_exceeded"})
            return f"error: call budget exceeded for {name}"
        if sum(call_counts.values()) >= PER_TURN_TOOL_BUDGET:
            audit_log(
                "tool_call_rejected",
                {"name": name, "reason": "per_turn_budget_exceeded"},
            )
            return "error: per-turn tool budget exceeded"
        call_counts[name] = used + 1

    snapshot_id: str | None = None
    if tool.risk == "high":
        approval = await _resolve_approval(confirm, name, args)
        if not approval.approved:
            audit_log("tool_call_denied", {"name": name, "args": args, "tier": tool.risk})
            return "denied: high-risk action was not approved"
        snapshot_id = approval.snapshot_id

    audit_log(
        "tool_call_start",
        {"name": name, "args": args, "tier": tool.risk, "snapshot_id": snapshot_id},
    )
    try:
        # Run the (possibly blocking) tool off the event loop.
        result = await asyncio.to_thread(tool.fn, **args)
        audit_log(
            "tool_call_ok",
            {
                "name": name,
                "tier": tool.risk,
                "snapshot_id": snapshot_id,
                "result": (result or "")[:500],
            },
        )
        return result
    except Exception as e:  # tools must never crash the agent
        audit_log(
            "tool_call_error",
            {"name": name, "tier": tool.risk, "snapshot_id": snapshot_id, "error": str(e)},
        )
        return f"error: {e}"
