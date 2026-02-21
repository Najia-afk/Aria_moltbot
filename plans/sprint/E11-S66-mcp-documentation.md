# S-66: MCP Documentation Update
**Epic:** E11 — MCP Hybrid Integration | **Priority:** P2 | **Points:** 2 | **Phase:** 3

## Problem
After MCP hybrid integration is implemented, the documentation does not reflect the new
capability. Users and agents need to know:
- How to enable an external MCP server
- How to expose Aria's skills via MCP
- What changed architecturally
- How MCP tools appear alongside native tools

## Root Cause
MCP is a new integration. No documentation exists for it.

## Fix

### 1. Update `ARCHITECTURE.md` — Add MCP section

After the Skill Layer section, add:

```markdown
## MCP Hybrid Layer (Optional)

Aria supports the Model Context Protocol (MCP) as a hybrid integration:

### MCP Client (Consume External Tools)
- External MCP servers (GitHub, Brave Search, filesystem, etc.) are configured in
  `aria_engine/mcp_servers.yaml`
- On engine startup, MCP tools are discovered and registered alongside native skills
- MCP tools appear as `mcp__<server>__<tool>` in the unified tool registry
- The ChatEngine calls them identically to native tools

### MCP Server (Expose Aria's Skills)
- Set `MCP_SERVER_ENABLED=true` to expose all registered skills as an MCP server
- Supports stdio (Claude Desktop) and SSE (web clients) transports
- Run via: `python -m aria_engine.mcp_serve` (stdio) or `--sse` (SSE)

### Architecture Rule
- Native skill path (direct Python) is always the fast path — unchanged
- MCP is additive — all MCP features disabled by default
- MCP tools are prefixed with `mcp__` to prevent naming collisions
```

### 2. Update `SKILLS.md` — Add MCP note

At the end, add:

```markdown
## MCP Integration

Skills from Aria's registry can be exposed to external MCP clients (Claude Desktop,
Cursor, VS Code Copilot). See `aria_engine/mcp_server.py`.

External MCP servers can also be consumed as tools — see `aria_engine/mcp_servers.yaml`.
```

### 3. Update `aria_mind/TOOLS.md` — Add MCP tool section

Add after the existing tool catalog:

```markdown
## External MCP Tools

When MCP servers are configured in `aria_engine/mcp_servers.yaml`, their tools appear
with the prefix `mcp__<server>__<tool>`. Example:

```yaml
mcp__github__create_issue({"repo": "owner/repo", "title": "Bug fix", "body": "..."})
mcp__brave__search({"query": "latest AI news"})
```

Configure MCP servers: edit `aria_engine/mcp_servers.yaml` and restart the engine.
```

### 4. Update `README.md` — Add MCP to features list

In the features section, add:
```markdown
- **MCP Hybrid Integration** — Consume external MCP servers + expose skills as MCP server
```

### 5. Update `CHANGELOG.md`

```markdown
## [Unreleased]
### Added
- MCP hybrid integration (E11):
  - MCP Client Adapter: consume external MCP servers as tools
  - MCP Server Adapter: expose Aria's 30+ skills to external MCP clients
  - Configuration via `aria_engine/mcp_servers.yaml`
  - CLI entrypoint: `python -m aria_engine.mcp_serve`
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ❌ | Documentation only |
| 2 | .env for secrets | ❌ | Documentation only |
| 3 | models.yaml | ❌ | Documentation only |
| 4 | Docker-first | ❌ | Documentation only |
| 5 | aria_memories only writable path | ❌ | Documentation only |
| 6 | No soul modification | ✅ | Do NOT modify any soul files |

## Dependencies
- **All S-60 through S-65** must complete first — document what was built

## Verification
```bash
# 1. All listed files exist and were updated:
grep -l "MCP" ARCHITECTURE.md SKILLS.md aria_mind/TOOLS.md README.md CHANGELOG.md
# EXPECTED: all 5 files listed

# 2. No soul files modified:
git diff --name-only aria_mind/soul/
# EXPECTED: no output (empty)
```

## Prompt for Agent
```
Files to read first:
- aria_souvenirs/aria_v2_210226/plans/MCP_HYBRID_ARCHITECTURE.md (design)
- ARCHITECTURE.md (find insertion point)
- SKILLS.md (end of file)
- aria_mind/TOOLS.md (after tool catalog)
- README.md (features section)
- CHANGELOG.md (top)

Steps:
1. Add MCP Hybrid Layer section to ARCHITECTURE.md
2. Add MCP note to SKILLS.md
3. Add External MCP Tools section to aria_mind/TOOLS.md
4. Add MCP to README.md features
5. Add CHANGELOG entry
6. Verify no soul files were touched

Constraints: #6 (never modify soul files)
```
