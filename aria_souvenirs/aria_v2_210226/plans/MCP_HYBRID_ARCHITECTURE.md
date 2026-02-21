# MCP Hybrid Architecture — Design Document

**Date:** 2026-02-21  
**Author:** Sprint Agent + Shiva  
**Status:** PLANNED  
**Epic:** E11 — MCP Hybrid Integration  

---

## Executive Summary

Add MCP (Model Context Protocol) support to Aria as a **hybrid layer** without
touching the existing in-process skill execution path. Two new components:

1. **MCP Client Adapter** — Allows `aria_engine` to consume external MCP servers as tools
2. **MCP Server Adapter** — Exposes Aria's `SkillRegistry` as an MCP server for outside consumers

The existing `ToolRegistry → BaseSkill → direct Python execution` path stays untouched.
MCP tools appear alongside native tools in the same `get_tools_for_llm()` output.

---

## Architecture Diagram

```
                    ┌──────────────────────────────────────────────────────┐
                    │                  aria_engine                         │
                    │                                                      │
                    │  ┌─────────────┐     ┌──────────────────────────┐   │
                    │  │  ChatEngine  │────▶│      ToolRegistry        │   │
                    │  └─────────────┘     │                          │   │
                    │                      │  ┌────────────────────┐  │   │
                    │                      │  │  Native Tools      │  │   │  UNCHANGED
                    │                      │  │  (aria_skills/*)   │  │   │  ─────────
                    │                      │  │  Direct Python     │  │   │
                    │                      │  │  execution, 0-hop  │  │   │
                    │                      │  └────────────────────┘  │   │
                    │                      │                          │   │
                    │                      │  ┌────────────────────┐  │   │
                    │                      │  │  MCP Client Proxy  │  │   │  NEW
                    │                      │  │  (mcp_client.py)   │  │   │  ───
                    │                      │  │  JSON-RPC ↔ stdio  │  │   │
                    │                      │  │  or SSE transport  │  │   │
                    │                      │  └────────┬───────────┘  │   │
                    │                      └───────────┼──────────────┘   │
                    └──────────────────────────────────┼──────────────────┘
                                                       │
                          ┌────────────────────────────┼──────────────────┐
                          │        External MCP Servers │                  │
                          │                             ▼                  │
                          │  ┌───────────┐  ┌───────────┐  ┌───────────┐  │
                          │  │ GitHub    │  │ Filesystem│  │ Custom    │  │
                          │  │ MCP srv   │  │ MCP srv   │  │ MCP srv   │  │
                          │  └───────────┘  └───────────┘  └───────────┘  │
                          └───────────────────────────────────────────────┘

    ┌────────────────────────────────┐
    │  MCP Server Adapter (NEW)      │     Exposes aria_skills as MCP
    │  aria_engine/mcp_server.py     │◀─── Claude Desktop, Cursor,
    │  Reads SkillRegistry           │     VS Code Copilot, any MCP client
    │  Serves via stdio / SSE        │
    └────────────────────────────────┘
```

---

## What Does NOT Change

| Component | Status |
|-----------|--------|
| `aria_skills/` directory and `BaseSkill` | **Untouched** |
| `skill.json` manifests | **Untouched** (already MCP-compatible shape) |
| `ToolRegistry.discover_from_skills()` | **Untouched** |
| `ToolRegistry.discover_from_manifests()` | **Untouched** |
| `ToolRegistry.execute()` for native tools | **Untouched** |
| `ChatEngine` tool loop | **Untouched** — sees MCP tools same as native |
| `LLMGateway` | **Untouched** |
| 5-layer architecture | **Untouched** |
| Prometheus metrics on `BaseSkill` | **Untouched** |

---

## Component 1: MCP Client Adapter

**File:** `aria_engine/mcp_client.py`  
**Purpose:** Connect to external MCP servers and register their tools into `ToolRegistry`

### Design

```python
@dataclass
class MCPServerConfig:
    """Configuration for an external MCP server."""
    name: str                          # e.g. "github", "filesystem"
    transport: str                     # "stdio" | "sse"
    command: str | None = None         # For stdio: command to spawn
    args: list[str] | None = None     # For stdio: command arguments
    url: str | None = None            # For SSE: server URL
    env: dict[str, str] | None = None # Environment variables to pass
    enabled: bool = True

class MCPClientAdapter:
    """Bridges external MCP servers into ToolRegistry."""
    
    async def connect(self, config: MCPServerConfig) -> int:
        """Connect to an MCP server, discover tools, register in ToolRegistry."""
        
    async def execute_mcp_tool(self, server_name: str, tool_name: str, args: dict) -> Any:
        """Execute a tool on an external MCP server via JSON-RPC."""
        
    async def disconnect_all(self) -> None:
        """Graceful shutdown of all MCP server connections."""
```

### Tool Registration Flow

1. On engine startup, read `mcp_servers.yaml` config
2. For each enabled server: spawn process (stdio) or connect (SSE)
3. Call `tools/list` JSON-RPC method to discover available tools
4. For each remote tool, register a proxy handler in `ToolRegistry`:
   ```python
   registry.register_tool(
       name=f"mcp__{server_name}__{tool_name}",
       description=remote_tool["description"],
       parameters=remote_tool["inputSchema"],
       handler=lambda **kwargs: self.execute_mcp_tool(server_name, tool_name, kwargs),
       skill_name=f"mcp_{server_name}",
   )
   ```
5. MCP tools appear in `get_tools_for_llm()` alongside native tools
6. `ChatEngine` calls them identically — no special casing needed

### Configuration: `mcp_servers.yaml`

```yaml
# aria_engine/mcp_servers.yaml
# External MCP servers for tool integration
# Loaded on engine startup alongside skill discovery

servers:
  # Example: GitHub MCP server
  # github:
  #   transport: stdio
  #   command: npx
  #   args: ["-y", "@modelcontextprotocol/server-github"]
  #   env:
  #     GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
  #   enabled: false

  # Example: Filesystem MCP server
  # filesystem:
  #   transport: stdio
  #   command: npx
  #   args: ["-y", "@modelcontextprotocol/server-filesystem", "/allowed/path"]
  #   enabled: false

  # Example: Custom SSE server
  # custom_api:
  #   transport: sse
  #   url: "http://localhost:9000/mcp"
  #   enabled: false
```

All servers disabled by default. Zero impact on existing deployment until explicitly enabled.

---

## Component 2: MCP Server Adapter

**File:** `aria_engine/mcp_server.py`  
**Purpose:** Expose Aria's skill registry as an MCP server

### Design

```python
class MCPServerAdapter:
    """Expose Aria's ToolRegistry as an MCP-compatible server."""
    
    def __init__(self, tool_registry: ToolRegistry):
        self._registry = tool_registry
    
    async def handle_tools_list(self) -> list[dict]:
        """MCP tools/list — return all native tools in MCP format."""
        
    async def handle_tools_call(self, name: str, arguments: dict) -> dict:
        """MCP tools/call — execute a tool and return MCP-formatted result."""
        
    async def serve_stdio(self) -> None:
        """Run as stdio MCP server (for Claude Desktop, etc.)."""
        
    async def serve_sse(self, host: str, port: int) -> None:
        """Run as SSE MCP server (for web clients)."""
```

### Translation logic

`skill.json` → MCP tool definition:

```
skill.json                          MCP tools/list response
─────────                          ────────────────────────
name: "get_activities"        →    name: "aria-api-client__get_activities"
description: "..."            →    description: "..."  
parameters/input_schema: {}   →    inputSchema: {}
```

The mapping is 1:1 because `skill.json` was designed with MCP-alignment in mind
(see `SKILL_STANDARD.md` line 160).

---

## Component 3: Configuration Integration

### `aria_engine/config.py` additions

```python
@dataclass
class EngineConfig:
    # ... existing fields ...
    
    # MCP integration
    mcp_servers_yaml: str = field(default_factory=lambda: str(
        Path(__file__).parent / "mcp_servers.yaml"
    ))
    mcp_server_enabled: bool = field(default_factory=lambda: os.environ.get(
        "MCP_SERVER_ENABLED", "false"
    ).lower() in ("true", "1", "yes"))
    mcp_server_port: int = field(default_factory=lambda: int(
        os.environ.get("MCP_SERVER_PORT", "9100")
    ))
```

### Environment variables (`.env.example`)

```bash
# MCP Integration (optional)
MCP_SERVER_ENABLED=false      # Expose Aria skills as MCP server
MCP_SERVER_PORT=9100          # MCP SSE server port
# MCP client configs: see aria_engine/mcp_servers.yaml
```

---

## Dependency: `mcp` Python SDK

```toml
# pyproject.toml — optional dependency group
[project.optional-dependencies]
mcp = ["mcp>=1.0.0"]
```

The `mcp` pip package provides:
- `ClientSession`, `StdioServerParameters` — for client adapter
- `Server`, `stdio_server` — for server adapter
- JSON-RPC message types and transport helpers

Imported conditionally: if `mcp` is not installed, MCP features are silently disabled.
Zero impact on existing deployments.

---

## Integration Points in Existing Code

### `aria_engine/tool_registry.py` — One New Method

```python
def register_mcp_tools(self, tools: list[dict], server_name: str, handler: Callable):
    """Register tools discovered from an external MCP server."""
    for tool in tools:
        name = f"mcp__{server_name}__{tool['name']}"
        self._tools[name] = ToolDefinition(
            name=name,
            description=tool.get("description", ""),
            parameters=tool.get("inputSchema", {"type": "object", "properties": {}}),
            skill_name=f"mcp_{server_name}",
            function_name=tool["name"],
            _handler=handler(tool["name"]),
        )
```

### `aria_engine/entrypoint.py` — Startup Hook

In the boot sequence, after Phase 3 (Load agent state):

```python
# Phase 3.5: Connect to external MCP servers (if configured)
if mcp_client_adapter:
    mcp_tool_count = await mcp_client_adapter.connect_all()
    logger.info("MCP client: %d external tools registered", mcp_tool_count)
```

### `aria_engine/config_loader.py` — Load MCP Config

Read `mcp_servers.yaml` and return `list[MCPServerConfig]`.

---

## What You Gain

| Gain | Details |
|------|---------|
| **Ecosystem access** | Consume any MCP server (GitHub, Slack, Postgres, Brave Search, etc.) |
| **External exposure** | Claude Desktop / Cursor / VS Code can use Aria's 30+ skills |
| **Zero internal changes** | Native skill path completely untouched |
| **Gradual adoption** | All MCP off by default; enable per-server in YAML |
| **Unified tool loop** | ChatEngine sees MCP tools identically to native tools |

## What It Costs

| Cost | Mitigation |
|------|------------|
| Network latency for MCP calls | MCP tools flagged as `source: mcp` for timeout tuning |
| Extra dependency (`mcp` package) | Optional extra, conditionally imported |
| Process management for stdio servers | Graceful shutdown in engine lifecycle |
| New config file to manage | Single YAML, all disabled by default |

---

## Sprint Tickets

| # | Ticket | Title | Points | Phase |
|---|--------|-------|--------|-------|
| 1 | S-60 | MCP Client Adapter — Core | 5 | P0 |
| 2 | S-61 | MCP Client — ToolRegistry Integration | 3 | P0 |
| 3 | S-62 | MCP Server Adapter — Expose Skills | 5 | P1 |
| 4 | S-63 | MCP Config (YAML + EngineConfig + .env) | 2 | P0 |
| 5 | S-64 | MCP Client — Lifecycle & Error Handling | 3 | P1 |
| 6 | S-65 | MCP Integration Tests | 3 | P2 |
| 7 | S-66 | Documentation Update | 2 | P2 |

**Total: 23 points**

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| `mcp` SDK breaking changes | Medium | Low | Pin version, conditional import |
| stdio process leaks | Low | Medium | Proper lifecycle in entrypoint shutdown |
| MCP tool conflicts with native names | Low | Low | `mcp__` prefix guarantees no collision |
| Performance regression | Low | Low | MCP path only for external tools, native path unchanged |
