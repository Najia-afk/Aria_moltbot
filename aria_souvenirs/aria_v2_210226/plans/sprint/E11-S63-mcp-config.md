# S-63: MCP Configuration — YAML, EngineConfig, .env
**Epic:** E11 — MCP Hybrid Integration | **Priority:** P0 | **Points:** 2 | **Phase:** 1

## Problem
There is no configuration surface for MCP integration. No YAML config for external MCP
servers, no `EngineConfig` fields for MCP settings, and no `.env.example` entries.

## Root Cause
MCP is a new integration. `aria_engine/config.py` `EngineConfig` (lines 1-65) has no MCP
fields. No `mcp_servers.yaml` file exists. `.env.example` has no MCP variables.

## Fix

### 1. New file: `aria_engine/mcp_servers.yaml`

```yaml
# MCP Server Configuration
# External MCP servers that Aria can consume as tool providers.
# All servers are disabled by default — enable individually.
#
# Transport types:
#   stdio — spawn a subprocess communicating via stdin/stdout
#   sse   — connect to an HTTP server using Server-Sent Events
#
# Environment variables: use ${VAR_NAME} syntax to reference .env values.

servers: {}
  # ─── Examples (uncomment to enable) ─────────────────────────────
  #
  # github:
  #   transport: stdio
  #   command: npx
  #   args: ["-y", "@modelcontextprotocol/server-github"]
  #   env:
  #     GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
  #   enabled: false
  #
  # filesystem:
  #   transport: stdio
  #   command: npx
  #   args: ["-y", "@modelcontextprotocol/server-filesystem", "/data"]
  #   enabled: false
  #
  # brave_search:
  #   transport: stdio
  #   command: npx
  #   args: ["-y", "@modelcontextprotocol/server-brave-search"]
  #   env:
  #     BRAVE_API_KEY: "${BRAVE_API_KEY}"
  #   enabled: false
  #
  # custom_sse:
  #   transport: sse
  #   url: "http://localhost:9000/mcp"
  #   enabled: false
```

### 2. `aria_engine/config.py` — Add MCP fields to EngineConfig

After existing `ws_ping_timeout` field (line 53), add:

```python
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

### 3. `aria_engine/config_loader.py` — Add `load_mcp_configs()` function

```python
def load_mcp_configs(yaml_path: str) -> list:
    """Load MCP server configurations from YAML file."""
    from pathlib import Path
    path = Path(yaml_path)
    if not path.exists():
        return []

    import yaml
    data = yaml.safe_load(path.read_text())
    servers = data.get("servers", {})
    if not servers:
        return []

    from aria_engine.mcp_client import MCPServerConfig
    configs = []
    for name, cfg in servers.items():
        configs.append(MCPServerConfig(
            name=name,
            transport=cfg.get("transport", "stdio"),
            command=cfg.get("command"),
            args=cfg.get("args", []),
            url=cfg.get("url"),
            env=cfg.get("env", {}),
            enabled=cfg.get("enabled", True),
        ))
    return configs
```

### 4. `.env.example` — Add MCP section

At the end of the file, add:
```bash
# ── MCP Integration (optional) ────────────────────────────────
# MCP_SERVER_ENABLED=false        # Expose Aria skills as MCP server
# MCP_SERVER_PORT=9100            # MCP SSE server port
# GITHUB_TOKEN=                   # For GitHub MCP server  
# BRAVE_API_KEY=                  # For Brave Search MCP server
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Config layer only |
| 2 | .env for secrets (zero in code) | ✅ | All tokens via `${VAR}` in YAML, vars in `.env.example` |
| 3 | models.yaml single source of truth | ❌ | MCP config is separate from model routing |
| 4 | Docker-first testing | ✅ | Empty servers={} means zero behavior change in Docker |
| 5 | aria_memories only writable path | ❌ | Config is read-only |
| 6 | No soul modification | ❌ | No soul files touched |

## Dependencies
- **S-60** should complete first — defines `MCPServerConfig` dataclass used by `load_mcp_configs()`
- No downstream blockers

## Verification
```bash
# 1. Config fields exist:
python -c "
from aria_engine.config import EngineConfig
c = EngineConfig()
print(f'mcp_servers_yaml={c.mcp_servers_yaml}')
print(f'mcp_server_enabled={c.mcp_server_enabled}')
print(f'mcp_server_port={c.mcp_server_port}')
"
# EXPECTED: Three lines with default values (path, False, 9100)

# 2. YAML loads cleanly:
python -c "
from aria_engine.config_loader import load_mcp_configs
configs = load_mcp_configs('aria_engine/mcp_servers.yaml')
print(f'configs={len(configs)}')
"
# EXPECTED: configs=0 (all commented out)

# 3. mcp_servers.yaml is valid YAML:
python -c "import yaml; yaml.safe_load(open('aria_engine/mcp_servers.yaml')); print('valid YAML')"
# EXPECTED: valid YAML

# 4. Existing tests still pass:
pytest tests/ -x -q
# EXPECTED: all pass
```

## Prompt for Agent
```
Files to read first:
- aria_engine/config.py (full — understand EngineConfig)
- aria_engine/config_loader.py (full — understand existing config loading)
- .env.example (end of file — see where to add MCP section)

Steps:
1. Create aria_engine/mcp_servers.yaml with commented examples
2. Add 3 MCP fields to EngineConfig in config.py
3. Add load_mcp_configs() function to config_loader.py
4. Add MCP section to .env.example
5. Run verification commands

Constraints: #1 (config layer), #2 (.env for secrets), #4 (Docker-first)
```
