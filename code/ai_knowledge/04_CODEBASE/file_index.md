# File Index

> **AI SYSTEM INSTRUCTION**: Do not rely on static text for class or function definitions. This project uses `graphify` (an AST-based knowledge graph).
> Run `graphify query "<query>"` or use MCP `query_graph` to retrieve LIVE, up-to-date class/function information.

## Tool Expansion (Phase 2)
The `jarvis-shell/src/jarvis/tools/` directory contains 54 tool implementations across multiple domains (core, home_assistant, browser, desktop_control, calendar). Each tool is registered with `@register` and explicitly assigns a `risk` and `domain`.
