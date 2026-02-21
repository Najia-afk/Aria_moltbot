# S-60: MCP Client Adapter — Core  ✅ DONE
**Epic:** E11 — MCP Hybrid Integration | **Priority:** P0 | **Points:** 5 | **Phase:** 1 | **Status:** DONE

## Problem
Aria cannot consume external MCP servers. All tool capabilities are locked to native Python skills
in `aria_skills/`. There is no way to plug into the MCP ecosystem (GitHub, Brave Search, Slack, etc.)
without writing a full custom skill for each.

## Root Cause
The `aria_engine/tool_registry.py` `ToolRegistry` class only discovers tools from `aria_skills/*/skill.json`
manifests (line 121-188). There is no adapter to connect to external processes speaking the MCP JSON-RPC
protocol over stdio or SSE transport.

## Fix

### New file: `aria_engine/mcp_client.py`

```python
"""
MCP Client Adapter — Connect to external MCP servers.

Bridges external MCP-compatible tool servers into Aria's ToolRegistry.
Uses the `mcp` Python SDK for JSON-RPC communication over stdio or SSE.

Conditionally imported: if `mcp` package is not installed, all methods
return empty results and log a warning.
"""
import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("aria.engine.mcp_client")

# Conditional import — MCP features disabled if SDK not installed
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.client.sse import sse_client
    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    logger.info("MCP SDK not installed — external MCP servers disabled")


@dataclass
class MCPServerConfig:
    """Configuration for an external MCP server."""
    name: str
    transport: str  # "stdio" | "sse"
    command: str | None = None
    args: list[str] = field(default_factory=list)
    url: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    enabled: bool = True


class MCPClientAdapter:
    """
    Bridges external MCP servers into ToolRegistry.

    Usage:
        adapter = MCPClientAdapter(tool_registry)
        count = await adapter.connect_all(configs)
        # Tools are now in registry.get_tools_for_llm()
        await adapter.disconnect_all()
    """

    def __init__(self, tool_registry):
        self._registry = tool_registry
        self._sessions: dict[str, ClientSession] = {}
        self._transports: dict[str, Any] = {}
        self._tool_count = 0

    async def connect(self, config: MCPServerConfig) -> int:
        """
        Connect to a single MCP server, discover tools, register them.

        Returns number of tools registered.
        """
        if not HAS_MCP:
            logger.warning("MCP SDK not installed — skipping server '%s'", config.name)
            return 0

        if not config.enabled:
            logger.debug("MCP server '%s' disabled — skipping", config.name)
            return 0

        try:
            if config.transport == "stdio":
                return await self._connect_stdio(config)
            elif config.transport == "sse":
                return await self._connect_sse(config)
            else:
                logger.error("Unknown transport '%s' for MCP server '%s'",
                             config.transport, config.name)
                return 0
        except Exception as e:
            logger.error("Failed to connect to MCP server '%s': %s", config.name, e)
            return 0

    async def _connect_stdio(self, config: MCPServerConfig) -> int:
        """Connect via stdio transport (subprocess)."""
        # Resolve env vars in config.env
        resolved_env = {}
        for key, val in config.env.items():
            if val.startswith("${") and val.endswith("}"):
                env_name = val[2:-1]
                resolved_env[key] = os.environ.get(env_name, "")
            else:
                resolved_env[key] = val

        server_params = StdioServerParameters(
            command=config.command,
            args=config.args,
            env={**os.environ, **resolved_env},
        )

        transport = await stdio_client(server_params).__aenter__()
        read_stream, write_stream = transport
        session = ClientSession(read_stream, write_stream)
        await session.initialize()

        self._sessions[config.name] = session
        self._transports[config.name] = transport

        return await self._discover_and_register(config.name, session)

    async def _connect_sse(self, config: MCPServerConfig) -> int:
        """Connect via SSE transport (HTTP)."""
        if not config.url:
            logger.error("MCP server '%s' has transport=sse but no url", config.name)
            return 0

        transport = await sse_client(config.url).__aenter__()
        read_stream, write_stream = transport
        session = ClientSession(read_stream, write_stream)
        await session.initialize()

        self._sessions[config.name] = session
        self._transports[config.name] = transport

        return await self._discover_and_register(config.name, session)

    async def _discover_and_register(self, server_name: str, session: ClientSession) -> int:
        """Discover tools from an MCP session and register in ToolRegistry."""
        response = await session.list_tools()
        tools = response.tools if hasattr(response, 'tools') else []

        count = 0
        for tool in tools:
            tool_name = f"mcp__{server_name}__{tool.name}"

            # Create a closure that captures the correct tool name and session
            def make_handler(srv_name: str, t_name: str):
                async def handler(**kwargs):
                    return await self.execute_mcp_tool(srv_name, t_name, kwargs)
                return handler

            self._registry.register_tool(
                name=tool_name,
                description=tool.description or f"MCP tool from {server_name}",
                parameters=tool.inputSchema if hasattr(tool, 'inputSchema') else {
                    "type": "object", "properties": {}
                },
                handler=make_handler(server_name, tool.name),
                skill_name=f"mcp_{server_name}",
            )
            count += 1

        logger.info("MCP server '%s': registered %d tools", server_name, count)
        self._tool_count += count
        return count

    async def connect_all(self, configs: list[MCPServerConfig]) -> int:
        """Connect to all configured MCP servers. Returns total tools registered."""
        total = 0
        for config in configs:
            total += await self.connect(config)
        return total

    async def execute_mcp_tool(
        self, server_name: str, tool_name: str, arguments: dict
    ) -> dict[str, Any]:
        """Execute a tool on an external MCP server."""
        session = self._sessions.get(server_name)
        if not session:
            return {"error": f"MCP server '{server_name}' not connected"}

        try:
            result = await session.call_tool(tool_name, arguments)

            # Normalize MCP result to dict
            if hasattr(result, 'content'):
                contents = result.content
                if isinstance(contents, list) and len(contents) > 0:
                    first = contents[0]
                    if hasattr(first, 'text'):
                        return {"success": True, "data": first.text}
                    return {"success": True, "data": str(first)}
                return {"success": True, "data": str(contents)}
            return {"success": True, "data": str(result)}

        except Exception as e:
            logger.error("MCP tool call failed: %s.%s — %s", server_name, tool_name, e)
            return {"error": str(e)}

    async def disconnect_all(self) -> None:
        """Graceful shutdown of all MCP server connections."""
        for name, session in self._sessions.items():
            try:
                await session.__aexit__(None, None, None)
            except Exception as e:
                logger.debug("Error closing MCP session '%s': %s", name, e)

        for name, transport in self._transports.items():
            try:
                if hasattr(transport, '__aexit__'):
                    await transport.__aexit__(None, None, None)
            except Exception:
                pass

        self._sessions.clear()
        self._transports.clear()
        logger.info("MCP client: disconnected all servers")

    @property
    def connected_servers(self) -> list[str]:
        """List of currently connected MCP server names."""
        return list(self._sessions.keys())

    @property
    def total_tools(self) -> int:
        """Total number of MCP tools registered."""
        return self._tool_count
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | MCP adapter lives in engine layer, does NOT import skills or DB directly |
| 2 | .env for secrets (zero in code) | ✅ | MCP server tokens resolved from env vars via `${VAR}` syntax in YAML |
| 3 | models.yaml single source of truth | ❌ | Does not involve model routing |
| 4 | Docker-first testing | ✅ | `mcp` is an optional dep; existing Docker image works without it |
| 5 | aria_memories only writable path | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul files touched |

## Dependencies
- None — this is the foundation ticket. S-61 depends on this.

## Verification
```bash
# 1. Module imports cleanly:
python -c "from aria_engine.mcp_client import MCPClientAdapter, MCPServerConfig, HAS_MCP; print(f'HAS_MCP={HAS_MCP}')"
# EXPECTED: HAS_MCP=True (if mcp installed) or HAS_MCP=False (graceful fallback)

# 2. Class instantiation:
python -c "
from aria_engine.mcp_client import MCPClientAdapter
from aria_engine.tool_registry import ToolRegistry
r = ToolRegistry()
a = MCPClientAdapter(r)
print(f'connected={a.connected_servers}, tools={a.total_tools}')
"
# EXPECTED: connected=[], tools=0

# 3. No import side effects:
python -c "import aria_engine.mcp_client; print('OK')"
# EXPECTED: OK
```

## Prompt for Agent
```
Files to read first:
- aria_engine/tool_registry.py (full — understand ToolRegistry.register_tool)
- aria_engine/config.py (full — understand EngineConfig)
- aria_souvenirs/aria_v2_210226/plans/MCP_HYBRID_ARCHITECTURE.md (full design)

Steps:
1. Create aria_engine/mcp_client.py with the code from the Fix section
2. Verify it imports cleanly with `python -c "from aria_engine.mcp_client import MCPClientAdapter"`
3. If mcp SDK is not installed, verify HAS_MCP=False and no crash
4. Run existing tests to confirm zero regression: `pytest tests/ -x -q`

Constraints: #1 (engine layer only), #2 (env vars for secrets), #4 (Docker-first)
```
