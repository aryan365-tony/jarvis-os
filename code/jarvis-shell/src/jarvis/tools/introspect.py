"""Tool introspection (core).

Design note
-----------
Read-only pure python introspection, so it is low tier.
"""

from __future__ import annotations

from .registry import REGISTRY, register


@register(
    "tool_list",
    risk="low",
    domain="core",
    description="List all available tools, their descriptions, risk tiers, and domains.",
    parameters={"type": "object", "properties": {}},
)
def tool_list() -> str:
    lines = []
    for t in sorted(REGISTRY.values(), key=lambda x: x.name):
        lines.append(f"- {t.name} (domain: {t.domain}, risk: {t.risk}): {t.description}")
    return "\n".join(lines)
