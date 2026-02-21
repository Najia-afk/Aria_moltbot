# S-65: MCP Integration Tests
**Epic:** E11 — MCP Hybrid Integration | **Priority:** P2 | **Points:** 3 | **Phase:** 3

## Problem
No test coverage for MCP client adapter, MCP server adapter, or configuration loading.
MCP integration needs both unit tests (mocked) and integration tests to ensure tools
flow correctly through the hybrid path.

## Root Cause
MCP is a new integration. No test files exist for `mcp_client.py`, `mcp_server.py`,
or `mcp_servers.yaml` loading.

## Fix

### New file: `tests/test_mcp_client.py`

```python
"""Tests for MCP Client Adapter."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from aria_engine.tool_registry import ToolRegistry
from aria_engine.mcp_client import MCPClientAdapter, MCPServerConfig, HAS_MCP


class TestMCPClientAdapter:
    """Test MCP client without real MCP servers."""

    def test_init(self):
        registry = ToolRegistry()
        adapter = MCPClientAdapter(registry)
        assert adapter.connected_servers == []
        assert adapter.total_tools == 0

    @pytest.mark.asyncio
    async def test_connect_disabled_server(self):
        registry = ToolRegistry()
        adapter = MCPClientAdapter(registry)
        config = MCPServerConfig(name="test", transport="stdio", enabled=False)
        count = await adapter.connect(config)
        assert count == 0

    @pytest.mark.asyncio
    async def test_connect_unknown_transport(self):
        registry = ToolRegistry()
        adapter = MCPClientAdapter(registry)
        config = MCPServerConfig(name="test", transport="unknown", enabled=True)
        count = await adapter.connect(config)
        assert count == 0

    @pytest.mark.asyncio
    async def test_disconnect_all_empty(self):
        registry = ToolRegistry()
        adapter = MCPClientAdapter(registry)
        await adapter.disconnect_all()  # Should not raise

    @pytest.mark.asyncio
    async def test_execute_mcp_tool_not_connected(self):
        registry = ToolRegistry()
        adapter = MCPClientAdapter(registry)
        result = await adapter.execute_mcp_tool("absent", "tool", {})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_health_check_empty(self):
        registry = ToolRegistry()
        adapter = MCPClientAdapter(registry)
        health = await adapter.health_check()
        assert health == {}


class TestMCPServerConfig:
    """Test configuration dataclass."""

    def test_defaults(self):
        config = MCPServerConfig(name="test", transport="stdio")
        assert config.enabled is True
        assert config.args == []
        assert config.env == {}

    def test_full_config(self):
        config = MCPServerConfig(
            name="github",
            transport="stdio",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-github"],
            env={"GITHUB_TOKEN": "${GITHUB_TOKEN}"},
            enabled=True,
        )
        assert config.name == "github"
        assert config.command == "npx"
```

### New file: `tests/test_mcp_server.py`

```python
"""Tests for MCP Server Adapter."""
import pytest
from aria_engine.tool_registry import ToolRegistry
from aria_engine.mcp_server import MCPServerAdapter, HAS_MCP_SERVER


class TestMCPServerAdapter:
    """Test MCP server adapter."""

    def test_init(self):
        registry = ToolRegistry()
        adapter = MCPServerAdapter(registry)
        assert adapter.tool_count == 0

    def test_tool_count_matches_registry(self):
        registry = ToolRegistry()
        count = registry.discover_from_manifests()
        adapter = MCPServerAdapter(registry)
        assert adapter.tool_count == count

    @pytest.mark.skipif(not HAS_MCP_SERVER, reason="mcp SDK not installed")
    def test_server_created(self):
        registry = ToolRegistry()
        adapter = MCPServerAdapter(registry)
        assert adapter._server is not None
```

### New file: `tests/test_mcp_config.py`

```python
"""Tests for MCP configuration loading."""
import pytest
import tempfile
from pathlib import Path

from aria_engine.config import EngineConfig


class TestMCPConfig:
    """Test MCP configuration."""

    def test_engine_config_defaults(self):
        config = EngineConfig()
        assert config.mcp_server_enabled is False
        assert config.mcp_server_port == 9100
        assert "mcp_servers.yaml" in config.mcp_servers_yaml

    def test_load_mcp_configs_empty(self):
        from aria_engine.config_loader import load_mcp_configs
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("servers: {}\n")
            f.flush()
            configs = load_mcp_configs(f.name)
            assert configs == []

    def test_load_mcp_configs_missing_file(self):
        from aria_engine.config_loader import load_mcp_configs
        configs = load_mcp_configs("/nonexistent/path.yaml")
        assert configs == []
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ❌ | Test files only |
| 2 | .env for secrets (zero in code) | ❌ | No secrets in tests |
| 3 | models.yaml single source of truth | ❌ | No model changes |
| 4 | Docker-first testing | ✅ | Tests must pass in Docker CI |
| 5 | aria_memories only writable path | ❌ | Tests use tempfile only |
| 6 | No soul modification | ❌ | No soul files |

## Dependencies
- **S-60, S-61, S-62, S-63, S-64** — all MCP code must exist before testing

## Verification
```bash
# 1. All MCP tests pass:
pytest tests/test_mcp_client.py tests/test_mcp_server.py tests/test_mcp_config.py -v
# EXPECTED: all pass

# 2. Full test suite still passes:
pytest tests/ -x -q
# EXPECTED: all pass
```

## Prompt for Agent
```
Files to read first:
- aria_engine/mcp_client.py (full)
- aria_engine/mcp_server.py (full)
- aria_engine/config.py (MCP fields)
- tests/ (list directory — see existing test patterns)

Steps:
1. Create tests/test_mcp_client.py
2. Create tests/test_mcp_server.py
3. Create tests/test_mcp_config.py
4. Run all three test files
5. Run full test suite

Constraints: #4 (Docker-first CI)
```
