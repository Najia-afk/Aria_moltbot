# S-62: MCP Server Adapter — Expose Skills as MCP
**Epic:** E11 — MCP Hybrid Integration | **Priority:** P1 | **Points:** 5 | **Phase:** 2

## Problem
Aria's 30+ skills are invisible to external AI agents and tools. Claude Desktop, Cursor,
VS Code Copilot, and any MCP client cannot discover or call Aria's tools. There is no
MCP server exposing the `ToolRegistry`.

## Root Cause
No MCP server process exists. The `ToolRegistry.get_tools_for_llm()` method (line ~355 of
`aria_engine/tool_registry.py`) returns OpenAI function-calling format, not MCP `tools/list`
format. No JSON-RPC handler exists for `tools/call`.

## Fix

### New file: `aria_engine/mcp_server.py`

```python
"""
MCP Server Adapter — Expose Aria's skills as an MCP server.

Allows external MCP clients (Claude Desktop, Cursor, VS Code, etc.) to
discover and call all tools registered in Aria's ToolRegistry.

Supports both stdio and SSE transports.

Conditional: requires `mcp` SDK. If not installed, serve methods log a
warning and exit.
"""
import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger("aria.engine.mcp_server")

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    HAS_MCP_SERVER = True
except ImportError:
    HAS_MCP_SERVER = False
    logger.info("MCP server SDK not available — MCP server disabled")


class MCPServerAdapter:
    """
    Expose Aria's ToolRegistry as an MCP-compatible server.

    Usage (stdio — Claude Desktop):
        adapter = MCPServerAdapter(tool_registry)
        await adapter.serve_stdio()

    Usage (SSE — web/remote):
        adapter = MCPServerAdapter(tool_registry)
        await adapter.serve_sse("0.0.0.0", 9100)
    """

    def __init__(self, tool_registry):
        self._registry = tool_registry
        self._server = None

        if HAS_MCP_SERVER:
            self._server = Server("aria-skills")
            self._register_handlers()

    def _register_handlers(self):
        """Register MCP protocol handlers."""
        server = self._server

        @server.list_tools()
        async def handle_list_tools() -> list[Tool]:
            """Return all registered tools in MCP format."""
            tools = []
            for tool_def in self._registry._tools.values():
                tools.append(Tool(
                    name=tool_def.name,
                    description=tool_def.description,
                    inputSchema=tool_def.parameters,
                ))
            return tools

        @server.call_tool()
        async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
            """Execute a tool and return MCP-formatted result."""
            import uuid
            tool_call_id = str(uuid.uuid4())
            result = await self._registry.execute(
                tool_call_id=tool_call_id,
                function_name=name,
                arguments=arguments or {},
            )
            return [TextContent(type="text", text=result.content)]

    async def serve_stdio(self) -> None:
        """Run as stdio MCP server (for Claude Desktop integration)."""
        if not HAS_MCP_SERVER:
            logger.error("Cannot start MCP server — mcp SDK not installed")
            return

        logger.info("Starting MCP stdio server — exposing %d tools",
                     len(self._registry._tools))
        async with stdio_server() as (read_stream, write_stream):
            await self._server.run(read_stream, write_stream)

    async def serve_sse(self, host: str = "0.0.0.0", port: int = 9100) -> None:
        """Run as SSE MCP server (for remote/web clients)."""
        if not HAS_MCP_SERVER:
            logger.error("Cannot start MCP SSE server — mcp SDK not installed")
            return

        try:
            from mcp.server.sse import SseServerTransport
            from starlette.applications import Starlette
            from starlette.routing import Route
            import uvicorn

            sse = SseServerTransport("/messages")

            async def handle_sse(request):
                async with sse.connect_sse(
                    request.scope, request.receive, request._send
                ) as streams:
                    await self._server.run(streams[0], streams[1])

            app = Starlette(routes=[
                Route("/sse", endpoint=handle_sse),
                Route("/messages", endpoint=sse.handle_post_message, methods=["POST"]),
            ])

            logger.info("Starting MCP SSE server on %s:%d — exposing %d tools",
                         host, port, len(self._registry._tools))

            config = uvicorn.Config(app, host=host, port=port, log_level="info")
            server = uvicorn.Server(config)
            await server.serve()

        except ImportError as e:
            logger.error("Cannot start MCP SSE server — missing dependency: %s", e)

    @property
    def tool_count(self) -> int:
        """Number of tools being exposed."""
        return len(self._registry._tools) if self._registry else 0
```

### New file: `aria_engine/__main___mcp.py` (CLI entrypoint)

```python
"""
CLI entrypoint for running Aria as an MCP server.

Usage:
    python -m aria_engine.mcp_serve          # stdio mode (Claude Desktop)
    python -m aria_engine.mcp_serve --sse    # SSE mode (web clients)
"""
import asyncio
import sys

from aria_engine.tool_registry import ToolRegistry
from aria_engine.mcp_server import MCPServerAdapter


async def main():
    registry = ToolRegistry()
    count = registry.discover_from_manifests()
    print(f"Discovered {count} tools from skill manifests", file=sys.stderr)

    adapter = MCPServerAdapter(registry)

    if "--sse" in sys.argv:
        port = 9100
        for i, arg in enumerate(sys.argv):
            if arg == "--port" and i + 1 < len(sys.argv):
                port = int(sys.argv[i + 1])
        await adapter.serve_sse(port=port)
    else:
        await adapter.serve_stdio()


if __name__ == "__main__":
    asyncio.run(main())
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Engine layer only; skills called through ToolRegistry |
| 2 | .env for secrets (zero in code) | ✅ | MCP_SERVER_PORT from env |
| 3 | models.yaml single source of truth | ❌ | No model changes |
| 4 | Docker-first testing | ✅ | Optional — only runs if MCP_SERVER_ENABLED=true |
| 5 | aria_memories only writable path | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul files touched |

## Dependencies
- S-60 should be done (shared `mcp` dependency and patterns)
- Independent of S-61 (different direction: outbound vs inbound)

## Verification
```bash
# 1. Module imports:
python -c "from aria_engine.mcp_server import MCPServerAdapter, HAS_MCP_SERVER; print(f'HAS_MCP_SERVER={HAS_MCP_SERVER}')"
# EXPECTED: HAS_MCP_SERVER=True (if mcp installed)

# 2. Tool count from manifests:
python -c "
from aria_engine.tool_registry import ToolRegistry
from aria_engine.mcp_server import MCPServerAdapter
r = ToolRegistry()
c = r.discover_from_manifests()
a = MCPServerAdapter(r)
print(f'tools_discovered={c}, exposed_via_mcp={a.tool_count}')
assert a.tool_count == c
print('PASS')
"
# EXPECTED: tools_discovered=N, exposed_via_mcp=N, PASS

# 3. Existing tests unaffected:
pytest tests/ -x -q
# EXPECTED: all pass
```

## Prompt for Agent
```
Files to read first:
- aria_engine/tool_registry.py (understand ToolRegistry, ToolDefinition, execute())
- aria_engine/mcp_client.py (S-60 — understand MCP patterns used)
- aria_souvenirs/aria_v2_210226/plans/MCP_HYBRID_ARCHITECTURE.md (design)

Steps:
1. Create aria_engine/mcp_server.py with the code from Fix section
2. Create aria_engine/mcp_serve.py as CLI entrypoint
3. Test imports work cleanly
4. Verify tool count matches between ToolRegistry and MCPServerAdapter
5. Run full test suite

Constraints: #1 (engine layer only), #2 (.env for MCP_SERVER_PORT), #4 (Docker-first)
```
