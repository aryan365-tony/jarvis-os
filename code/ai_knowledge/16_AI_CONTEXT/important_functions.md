# Important Functions

> **AI SYSTEM INSTRUCTION**: Do not rely on static text for class or function definitions. This project uses `graphify` (an AST-based knowledge graph).
> Run `graphify query "<query>"` or use MCP `query_graph` to retrieve LIVE, up-to-date class/function information.

## Tool Registry (Phase 2)
- `jarvis.tools.registry.register`: Decorator for registering tools. It accepts `name`, `risk`, `domain`, `description`, and `parameters`.
- `jarvis.tools.registry.execute`: Executes a tool by name, ensuring the tool's domain is enabled in the configuration (`ToolsConfig.enabled_domains`).
