from dataclasses import dataclass
from typing import Callable, Literal, Any
from ..audit.chain import audit_log
from .network_policy import is_allowed_host

Risk = Literal["safe", "reversible", "irreversible"]

@dataclass
class Tool:
    name: str
    risk: Risk
    fn: Callable[..., str]
    max_calls_per_turn: int = 3

REGISTRY: dict[str, Tool] = {}

def register(name: str, risk: Risk, max_calls_per_turn: int = 3):
    def deco(fn):
        REGISTRY[name] = Tool(name, risk, fn, max_calls_per_turn)
        return fn
    return deco

def execute(name: str, args: dict[str, Any], confirm_async: Callable[[str, dict], bool]) -> str:
    tool = REGISTRY.get(name)
    if tool is None:
        audit_log("tool_call_rejected", {"name": name, "reason": "unknown_tool"})
        return f"error: unknown tool {name}"

    if tool.risk == "irreversible":
        if not confirm_async(name, args):
            audit_log("tool_call_denied", {"name": name, "args": args})
            return "denied by user"

    audit_log("tool_call_start", {"name": name, "args": args, "risk": tool.risk})
    try:
        result = tool.fn(**args)
        audit_log("tool_call_ok", {"name": name})
        return result
    except Exception as e:
        audit_log("tool_call_error", {"name": name, "error": str(e)})
        return f"error: {e}"
