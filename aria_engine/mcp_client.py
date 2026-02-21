"""
MCP Client Adapter — Connect to external MCP servers.

Bridges external MCP-compatible tool servers into Aria's ToolRegistry.
Uses the ``mcp`` Python SDK for JSON-RPC communication over stdio or SSE.

Conditionally imported: if ``mcp`` package is not installed, all methods
return empty results and log a warning.  Zero impact on existing deployments.

Architecture rule: this module lives in the engine layer.  It does NOT
import aria_skills, aria_mind, or any SQLAlchemy model.
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger("aria.engine.mcp_client")

# ── Conditional import — MCP features disabled if SDK not installed ──────────
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.client.sse import sse_client

    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    logger.info("MCP SDK not installed — external MCP servers disabled")


# ── Configuration dataclass ──────────────────────────────────────────────────

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


# ── Client adapter ───────────────────────────────────────────────────────────

class MCPClientAdapter:
    """
    Bridges external MCP servers into Aria's ToolRegistry.

    Lifecycle::

        adapter = MCPClientAdapter(tool_registry)
        count   = await adapter.connect_all(configs)
        # … tools are now in registry.get_tools_for_llm() …
        await adapter.disconnect_all()

    Each MCP server connection is held in an ``AsyncExitStack`` so that
    transports and sessions are torn down cleanly on disconnect.
    """

    def __init__(self, tool_registry: Any) -> None:
        self._registry = tool_registry
        self._sessions: dict[str, ClientSession] = {}
        self._stacks: dict[str, AsyncExitStack] = {}
        self._configs: dict[str, MCPServerConfig] = {}
        self._tool_count: int = 0

    # ── public API ───────────────────────────────────────────────────────

    async def connect_all(self, configs: list[MCPServerConfig]) -> int:
        """Connect to all configured MCP servers.  Returns total tools registered."""
        total = 0
        for cfg in configs:
            total += await self.connect(cfg)
        return total

    async def connect(self, config: MCPServerConfig) -> int:
        """
        Connect to a single MCP server, discover its tools, and register
        them in the shared ``ToolRegistry``.

        Returns the number of tools registered from this server.
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
                logger.error(
                    "Unknown MCP transport '%s' for server '%s'",
                    config.transport,
                    config.name,
                )
                return 0
        except Exception as e:
            logger.error("Failed to connect to MCP server '%s': %s", config.name, e)
            return 0

    async def disconnect_all(self) -> None:
        """Graceful shutdown of all MCP server connections."""
        for name in list(self._stacks):
            await self._disconnect(name)
        logger.info("MCP client: disconnected all servers")

    async def execute_mcp_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a tool on an external MCP server via JSON-RPC."""
        session = self._sessions.get(server_name)
        if session is None:
            return {"error": f"MCP server '{server_name}' not connected"}

        try:
            result = await session.call_tool(tool_name, arguments)

            # MCP returns CallToolResult with .content list and .isError flag
            if result.isError:
                text_parts = [
                    c.text for c in result.content if hasattr(c, "text")
                ]
                return {"error": " ".join(text_parts) or "MCP tool returned error"}

            # Normalise content list → string
            text_parts = [c.text for c in result.content if hasattr(c, "text")]
            return {"success": True, "data": "\n".join(text_parts) if text_parts else str(result.content)}

        except Exception as e:
            logger.error("MCP tool call failed: %s.%s — %s", server_name, tool_name, e)
            return {"error": str(e)}

    async def health_check(self) -> dict[str, str]:
        """Ping each connected MCP server.  Returns ``{name: status}``."""
        status: dict[str, str] = {}
        for name, session in self._sessions.items():
            try:
                await asyncio.wait_for(session.send_ping(), timeout=5.0)
                status[name] = "healthy"
            except Exception:
                status[name] = "unhealthy"
        return status

    # ── properties ───────────────────────────────────────────────────────

    @property
    def connected_servers(self) -> list[str]:
        """Names of currently-connected MCP servers."""
        return list(self._sessions.keys())

    @property
    def total_tools(self) -> int:
        """Total number of MCP tools registered across all servers."""
        return self._tool_count

    # ── private helpers ──────────────────────────────────────────────────

    async def _connect_stdio(self, config: MCPServerConfig) -> int:
        """Connect via stdio transport (subprocess)."""
        if not config.command:
            logger.error("MCP server '%s' has transport=stdio but no command", config.name)
            return 0

        resolved_env = self._resolve_env(config.env)

        server_params = StdioServerParameters(
            command=config.command,
            args=config.args,
            env={**os.environ, **resolved_env},
        )

        stack = AsyncExitStack()
        try:
            transport = await stack.enter_async_context(stdio_client(server_params))
            read_stream, write_stream = transport
            session = await stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await session.initialize()
        except Exception:
            await stack.aclose()
            raise

        self._sessions[config.name] = session
        self._stacks[config.name] = stack
        self._configs[config.name] = config

        return await self._discover_and_register(config.name, session)

    async def _connect_sse(self, config: MCPServerConfig) -> int:
        """Connect via SSE transport (HTTP)."""
        if not config.url:
            logger.error("MCP server '%s' has transport=sse but no url", config.name)
            return 0

        stack = AsyncExitStack()
        try:
            transport = await stack.enter_async_context(sse_client(config.url))
            read_stream, write_stream = transport
            session = await stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await session.initialize()
        except Exception:
            await stack.aclose()
            raise

        self._sessions[config.name] = session
        self._stacks[config.name] = stack
        self._configs[config.name] = config

        return await self._discover_and_register(config.name, session)

    async def _discover_and_register(
        self, server_name: str, session: ClientSession
    ) -> int:
        """Discover tools from an MCP session and register them."""
        response = await session.list_tools()
        tools = response.tools if hasattr(response, "tools") else []

        count = 0
        for tool in tools:
            full_name = f"mcp__{server_name}__{tool.name}"

            # Close over the correct names for the handler
            def _make_handler(srv: str, tname: str) -> Callable[..., Any]:
                async def _handler(**kwargs: Any) -> dict[str, Any]:
                    return await self.execute_mcp_tool(srv, tname, kwargs)
                return _handler

            self._registry.register_tool(
                name=full_name,
                description=tool.description or f"MCP tool from {server_name}",
                parameters=tool.inputSchema,
                handler=_make_handler(server_name, tool.name),
                skill_name=f"mcp_{server_name}",
            )
            count += 1

        logger.info("MCP server '%s': registered %d tools", server_name, count)
        self._tool_count += count
        return count

    async def _disconnect(self, name: str) -> None:
        """Disconnect a single MCP server, tearing down its transport stack."""
        stack = self._stacks.pop(name, None)
        self._sessions.pop(name, None)
        self._configs.pop(name, None)
        if stack is not None:
            try:
                await stack.aclose()
            except Exception as e:
                logger.debug("Error closing MCP stack for '%s': %s", name, e)

    @staticmethod
    def _resolve_env(env: dict[str, str]) -> dict[str, str]:
        """Resolve ``${VAR}`` references in env dict from ``os.environ``."""
        resolved: dict[str, str] = {}
        for key, val in env.items():
            if val.startswith("${") and val.endswith("}"):
                env_name = val[2:-1]
                resolved[key] = os.environ.get(env_name, "")
            else:
                resolved[key] = val
        return resolved
