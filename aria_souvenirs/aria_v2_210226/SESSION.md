# Aria v2 — 2026-02-21 Sprint Session

## Focus
MCP Hybrid Integration — Epic E11 Sprint Planning

## Decision
Add MCP as a **hybrid layer** to Aria's architecture:
- **MCP Client** — consume external MCP servers (GitHub, Brave Search, etc.) as tools
- **MCP Server** — expose Aria's 30+ skills to Claude Desktop, Cursor, VS Code Copilot

Key principle: **zero changes to existing code paths**. The native in-process
`ToolRegistry → BaseSkill → direct Python execution` stays completely untouched.
MCP tools are registered alongside native tools with `mcp__` prefix.

## Artifacts Created

| File | Purpose |
|------|---------|
| `aria_souvenirs/aria_v2_210226/plans/MCP_HYBRID_ARCHITECTURE.md` | Full architecture doc |
| `plans/sprint/E11-S60-mcp-client-core.md` | MCP Client Adapter — Core (5 pts) |
| `plans/sprint/E11-S61-mcp-registry-integration.md` | ToolRegistry integration (3 pts) |
| `plans/sprint/E11-S62-mcp-server-adapter.md` | MCP Server — Expose Skills (5 pts) |
| `plans/sprint/E11-S63-mcp-config.md` | YAML + EngineConfig + .env (2 pts) |
| `plans/sprint/E11-S64-mcp-lifecycle.md` | Reconnection & error handling (3 pts) |
| `plans/sprint/E11-S65-mcp-tests.md` | Integration tests (3 pts) |
| `plans/sprint/E11-S66-mcp-documentation.md` | Documentation update (2 pts) |
| `plans/SPRINT_OVERVIEW.md` | Updated with E11 board |

## Sprint Summary — E11

**Total: 7 tickets, 23 points, 3 phases**

- Phase 0 (P0): S-60, S-61, S-63 — Foundation (10 pts)
- Phase 1 (P1): S-62, S-64 — Production features (8 pts)
- Phase 2 (P2): S-65, S-66 — Quality & docs (5 pts)

## Key Architecture Decisions

1. **Conditional import** — `mcp` SDK is optional; if not installed, everything degrades gracefully
2. **`mcp__` prefix** — MCP tools use `mcp__<server>__<tool>` naming, no collision with native tools
3. **YAML config** — `aria_engine/mcp_servers.yaml` with `${ENV_VAR}` expansion for secrets
4. **Dual transport** — stdio (Claude Desktop) + SSE (web/remote) for the server adapter
5. **Unified tool loop** — ChatEngine sees MCP tools identically to native tools, no special casing
