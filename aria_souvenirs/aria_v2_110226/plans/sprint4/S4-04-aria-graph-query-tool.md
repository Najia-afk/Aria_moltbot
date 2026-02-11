# S4-04: Build Lightweight Graph Query Tool for Aria
**Epic:** E9 — Token Optimization | **Priority:** P0 | **Points:** 5 | **Phase:** 3

## Problem
When Aria needs to find which skill handles a task, she currently reads TOOLS.md (~2000 tokens) or the full skill catalog. With the knowledge graph (S4-01) and pathfinding API (S4-02), she can do targeted graph queries costing ~100-200 tokens per lookup.

## Root Cause
No skill/tool exists for Aria to query the knowledge graph for skill discovery. The existing knowledge_graph skill creates entities but doesn't do pathfinding.

## Fix

### Step 1: Add graph query methods to api_client
**File: `aria_skills/api_client/__init__.py`**
```python
    # ========================================
    # Knowledge Graph Queries (S4-04)
    # ========================================
    async def graph_traverse(self, start_name: str, relation_type: str = None,
                             max_depth: int = 2, direction: str = "both") -> SkillResult:
        """Traverse knowledge graph from a starting entity."""
        params = {"start_name": start_name, "max_depth": max_depth, "direction": direction}
        if relation_type:
            params["relation_type"] = relation_type
        return await self.get("/knowledge-graph/traverse", params=params)

    async def graph_search(self, query: str, entity_type: str = None, limit: int = 5) -> SkillResult:
        """Search knowledge graph entities by name."""
        params = {"query": query, "limit": limit}
        if entity_type:
            params["entity_type"] = entity_type
        return await self.get("/knowledge-graph/search", params=params)

    async def find_skill_for_task(self, task: str) -> SkillResult:
        """Find the best skill for a task via knowledge graph."""
        return await self.get("/knowledge-graph/skill-for-task", params={"task": task})
```

### Step 2: Add tool definitions for Aria
**File: `aria_mind/TOOLS.md`**
```yaml
# Skill Discovery (via Knowledge Graph — ~100 tokens per query)
aria-apiclient.find_skill_for_task({"task": "send telegram message"})
# Returns: {candidates: [{skill: "telegram", matched_tool: "send_message", ...}]}

aria-apiclient.graph_traverse({"start_name": "social", "relation_type": "affinity", "max_depth": 2})
# Returns: {nodes: [...], edges: [...]} — skills connected to social focus

aria-apiclient.graph_search({"query": "market", "entity_type": "skill"})
# Returns: {entities: [{name: "market_data", ...}]}
```

### Step 3: Update Aria's skill selection logic
The cognitive loop should use graph queries before falling back to TOOLS.md:

```python
# Before: read full TOOLS.md (~2000 tokens)
# After: targeted graph query (~100 tokens)
skill_result = await api_client.find_skill_for_task(task_description)
if skill_result.success and skill_result.data.get("candidates"):
    selected_skill = skill_result.data["candidates"][0]["skill"]
else:
    # Fallback to reading TOOLS.md
    ...
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | api_client → API → DB |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml | ❌ | No model names |
| 4 | Docker-first | ✅ | Test in Docker |
| 5 | aria_memories | ❌ | No writes |
| 6 | No soul mod | ❌ | No soul files |

## Dependencies
- **S4-01** (graph generated), **S4-02** (pathfinding API)

## Verification
```bash
# 1. API client methods exist:
grep -n 'graph_traverse\|graph_search\|find_skill_for_task' aria_skills/api_client/__init__.py
# EXPECTED: 3 method definitions

# 2. TOOLS.md updated:
grep 'find_skill_for_task\|graph_traverse\|graph_search' aria_mind/TOOLS.md
# EXPECTED: documented

# 3. Token comparison:
echo "Full TOOLS.md:" && wc -c aria_mind/TOOLS.md
echo "Graph query:" && curl -s 'http://localhost:8000/api/knowledge-graph/skill-for-task?task=telegram' | wc -c
# EXPECTED: Graph query is 10-20x smaller
```

## Prompt for Agent
```
Build lightweight graph query tools for Aria's skill discovery.

FILES TO READ FIRST:
- aria_skills/api_client/__init__.py (add methods)
- aria_mind/TOOLS.md (document new tools)
- aria_mind/cognition.py (update skill selection)

STEPS:
1. Add graph_traverse, graph_search, find_skill_for_task to api_client
2. Document in TOOLS.md
3. Update cognitive loop to prefer graph queries over TOOLS.md
4. Run verification

CONSTRAINTS: 5-layer. api_client only. Minimize tokens.
```
