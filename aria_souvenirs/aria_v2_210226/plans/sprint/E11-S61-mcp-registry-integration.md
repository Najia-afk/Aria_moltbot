# S-61: MCP Client — ToolRegistry Integration
**Epic:** E11 — MCP Hybrid Integration | **Priority:** P0 | **Points:** 3 | **Phase:** 1

## Problem
After S-60 creates `MCPClientAdapter`, it still needs to be wired into the engine startup
lifecycle so MCP tools are discovered automatically when the engine boots.

Currently `aria_engine/tool_registry.py` `ToolRegistry` has no `register_mcp_tools()` convenience
method, and `aria_engine/entrypoint.py` has no MCP boot phase.

## Root Cause
`ToolRegistry` was designed for native skills only. The `register_tool()` method (line ~340) works
for individual tools but there's no batch method for MCP-discovered tools. The entrypoint
`AriaEngine.__init__()` (line 30) has no MCP adapter field and no MCP boot phase.

## Fix

### 1. `aria_engine/tool_registry.py` — Add `register_mcp_tools()` method

After the existing `register_tool()` method (~line 350), add:

```python
def register_mcp_tools(
    self,
    tools: list[dict[str, Any]],
    server_name: str,
    handler_factory: Callable[[str], Callable],
) -> int:
    """
    Batch-register tools discovered from an external MCP server.

    Args:
        tools: List of MCP tool definitions (name, description, inputSchema)
        server_name: Name of the MCP server (used as prefix)
        handler_factory: Callable(tool_name) -> async handler(**kwargs)

    Returns:
        Number of tools registered.
    """
    count = 0
    for tool in tools:
        name = f"mcp__{server_name}__{tool['name']}"
        self._tools[name] = ToolDefinition(
            name=name,
            description=tool.get("description", ""),
            parameters=tool.get("inputSchema", {"type": "object", "properties": {}}),
            skill_name=f"mcp_{server_name}",
            function_name=tool["name"],
            _handler=handler_factory(tool["name"]),
        )
        count += 1
    logger.info("Registered %d MCP tools from server '%s'", count, server_name)
    return count
```

### 2. `aria_engine/entrypoint.py` — Add MCP boot phase

In `AriaEngine.__init__()`, add:
```python
self._mcp_client = None
```

After existing Phase 3 (Load agent state), add Phase 3.5:
```python
# Phase 3.5: Connect to external MCP servers
from aria_engine.mcp_client import HAS_MCP
if HAS_MCP:
    from aria_engine.mcp_client import MCPClientAdapter
    from aria_engine.config_loader import load_mcp_configs
    mcp_configs = load_mcp_configs(self.config.mcp_servers_yaml)
    if mcp_configs:
        self._mcp_client = MCPClientAdapter(self._tool_registry)
        mcp_count = await self._mcp_client.connect_all(mcp_configs)
        logger.info("Phase 3.5: MCP client — %d external tools from %d servers",
                     mcp_count, len(self._mcp_client.connected_servers))
```

In shutdown, add:
```python
if self._mcp_client:
    await self._mcp_client.disconnect_all()
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Changes only in engine layer |
| 2 | .env for secrets (zero in code) | ✅ | No secrets added |
| 3 | models.yaml single source of truth | ❌ | No model changes |
| 4 | Docker-first testing | ✅ | Conditional import — works with or without mcp SDK |
| 5 | aria_memories only writable path | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul files touched |

## Dependencies
- **S-60** must complete first — provides `MCPClientAdapter` and `MCPServerConfig`
- **S-63** should complete first — provides `mcp_servers_yaml` config path in `EngineConfig`

## Verification
```bash
# 1. register_mcp_tools exists and works:
python -c "
from aria_engine.tool_registry import ToolRegistry
r = ToolRegistry()
count = r.register_mcp_tools(
    tools=[{'name': 'test_tool', 'description': 'test', 'inputSchema': {'type': 'object', 'properties': {}}}],
    server_name='test_server',
    handler_factory=lambda name: (lambda **kw: {'ok': True}),
)
print(f'registered={count}')
assert count == 1
tools = r.get_tools_for_llm()
names = [t['function']['name'] for t in tools]
assert 'mcp__test_server__test_tool' in names
print('PASS')
"
# EXPECTED: registered=1 \n PASS

# 2. Existing tests still pass:
pytest tests/ -x -q
# EXPECTED: all pass
```

## Prompt for Agent
```
Files to read first:
- aria_engine/tool_registry.py (lines 330-360 — register_tool method area)
- aria_engine/entrypoint.py (full — understand boot sequence)
- plans/sprint/E11-S60-mcp-client-core.md (the dependency)

Steps:
1. Add register_mcp_tools() method to ToolRegistry after register_tool()
2. Add self._mcp_client = None to AriaEngine.__init__()
3. Add Phase 3.5 MCP boot after Phase 3 in the startup coroutine
4. Add MCP disconnect in shutdown
5. Run verification commands

Constraints: #1 (engine layer only), #4 (Docker-first)
```
