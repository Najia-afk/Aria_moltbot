# S-64: MCP Client — Lifecycle & Error Handling
**Epic:** E11 — MCP Hybrid Integration | **Priority:** P1 | **Points:** 3 | **Phase:** 2

## Problem
The MCP client adapter (S-60) needs production-grade lifecycle management: reconnection
on failure, timeout handling, health monitoring, and graceful degradation when an external
MCP server crashes or becomes unreachable.

## Root Cause
S-60 implements the happy path. Production needs:
- Reconnection with exponential backoff
- Per-tool timeout tracking (MCP tools are slower than native)
- Health check integration (report MCP server status in `/health`)
- Prometheus metrics for MCP tool calls
- Graceful handling of stdio process crashes

## Fix

### 1. `aria_engine/mcp_client.py` — Add resilience methods

Add to `MCPClientAdapter`:

```python
async def _reconnect(self, config: MCPServerConfig, attempt: int = 1, max_attempts: int = 3):
    """Reconnect to an MCP server with exponential backoff."""
    import asyncio
    delay = min(2 ** attempt, 30)  # 2s, 4s, 8s... max 30s
    logger.warning("MCP server '%s' disconnected — reconnecting in %ds (attempt %d/%d)",
                    config.name, delay, attempt, max_attempts)
    await asyncio.sleep(delay)
    try:
        await self.connect(config)
        logger.info("MCP server '%s' reconnected successfully", config.name)
    except Exception as e:
        if attempt < max_attempts:
            await self._reconnect(config, attempt + 1, max_attempts)
        else:
            logger.error("MCP server '%s' — gave up after %d attempts: %s",
                          config.name, max_attempts, e)

async def health_check(self) -> dict[str, str]:
    """Check health of all MCP server connections."""
    status = {}
    for name, session in self._sessions.items():
        try:
            await asyncio.wait_for(session.list_tools(), timeout=5.0)
            status[name] = "healthy"
        except Exception:
            status[name] = "unhealthy"
    return status
```

### 2. Modify `execute_mcp_tool()` — Add timeout & metrics

```python
async def execute_mcp_tool(self, server_name: str, tool_name: str, arguments: dict,
                            timeout: float = 60.0) -> dict[str, Any]:
    """Execute with timeout and Prometheus metrics."""
    import time
    start = time.monotonic()
    
    session = self._sessions.get(server_name)
    if not session:
        return {"error": f"MCP server '{server_name}' not connected"}

    try:
        result = await asyncio.wait_for(
            session.call_tool(tool_name, arguments),
            timeout=timeout,
        )
        elapsed = time.monotonic() - start
        
        # Prometheus metrics (if available)
        try:
            from aria_skills.base import SKILL_CALLS, SKILL_LATENCY
            SKILL_CALLS.labels(skill=f"mcp_{server_name}", function=tool_name, status="success").inc()
            SKILL_LATENCY.labels(skill=f"mcp_{server_name}", function=tool_name).observe(elapsed)
        except ImportError:
            pass
        
        # ... normalize result (same as S-60) ...

    except asyncio.TimeoutError:
        elapsed = time.monotonic() - start
        logger.error("MCP tool timed out: %s.%s after %.1fs", server_name, tool_name, elapsed)
        try:
            from aria_skills.base import SKILL_CALLS
            SKILL_CALLS.labels(skill=f"mcp_{server_name}", function=tool_name, status="timeout").inc()
        except ImportError:
            pass
        return {"error": f"MCP tool timed out after {timeout}s"}
```

### 3. Engine health endpoint integration

In the API health router, include MCP status:
```python
# In /health or /status response:
if mcp_client:
    health_data["mcp_servers"] = await mcp_client.health_check()
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Engine layer only |
| 2 | .env for secrets (zero in code) | ❌ | No new secrets |
| 3 | models.yaml single source of truth | ❌ | No model changes |
| 4 | Docker-first testing | ✅ | Must work in Docker |
| 5 | aria_memories only writable path | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul files |

## Dependencies
- **S-60** must complete first — base MCPClientAdapter
- **S-61** should complete first — entrypoint integration

## Verification
```bash
# 1. health_check method exists:
python -c "
from aria_engine.mcp_client import MCPClientAdapter
from aria_engine.tool_registry import ToolRegistry
a = MCPClientAdapter(ToolRegistry())
import asyncio
result = asyncio.run(a.health_check())
print(f'health={result}')
assert result == {}
print('PASS')
"
# EXPECTED: health={} \n PASS

# 2. Existing tests unaffected:
pytest tests/ -x -q
# EXPECTED: all pass
```

## Prompt for Agent
```
Files to read first:
- aria_engine/mcp_client.py (full — the file from S-60)
- aria_skills/base.py (lines 35-55 — Prometheus metrics)
- src/api/routers/ (health-related routers)

Steps:
1. Add _reconnect() method to MCPClientAdapter
2. Add health_check() method to MCPClientAdapter
3. Enhance execute_mcp_tool() with timeout + Prometheus metrics
4. Wire health_check into /health or /status endpoint
5. Run verification

Constraints: #1 (engine layer), #4 (Docker-first)
```
