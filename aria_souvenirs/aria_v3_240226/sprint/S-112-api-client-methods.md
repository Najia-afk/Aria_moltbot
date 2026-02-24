# S-112: Create Public api_client Methods for Common Operations
**Epic:** E5 — Architecture Cleanup | **Priority:** P1 | **Points:** 8 | **Phase:** 2

## Problem
11 skills access `self._api._client` (private httpx client) directly instead of using public api_client methods. This tightly couples skills to api_client internals. If `_client` changes (e.g., switching HTTP libraries), all 11 skills break.

Affected skills: agent_manager, goals, hourly_goals, knowledge_graph, performance, schedule, sprint_manager, working_memory, moltbook, memeothy

Common patterns:
```python
# Current (bad) — direct _client access
result = await self._api._client.get("/goals")
result = await self._api._client.post("/goals", json=data)
result = await self._api._client.patch(f"/goals/{id}", json=data)
```

## Root Cause
The api_client skill (`aria_skills/api_client/__init__.py`) doesn't expose public methods for all common operations. Skills were forced to access the private client directly.

## Fix
Add public methods to `ApiClientSkill` for all operations currently done via `_client`:

```python
# Add to aria_skills/api_client/__init__.py

# Goals
async def create_goal(self, data: dict) -> dict: ...
async def get_goal(self, goal_id: str) -> dict: ...
async def list_goals(self, **params) -> list: ...
async def update_goal(self, goal_id: str, data: dict) -> dict: ...

# Activities
async def create_activity(self, data: dict) -> dict: ...
async def list_activities(self, **params) -> list: ...

# Agents
async def list_agents(self, **params) -> list: ...
async def spawn_agent(self, data: dict) -> dict: ...
async def terminate_agent(self, session_id: str) -> dict: ...

# Knowledge Graph
async def kg_add_entity(self, data: dict) -> dict: ...
async def kg_add_relation(self, data: dict) -> dict: ...
async def kg_query(self, query: str) -> dict: ...

# Schedule
async def create_job(self, data: dict) -> dict: ...
async def list_jobs(self, **params) -> list: ...
async def update_job(self, job_id: str, data: dict) -> dict: ...

# Working Memory
async def remember(self, data: dict) -> dict: ...
async def recall(self, **params) -> dict: ...
async def checkpoint(self) -> dict: ...

# Performance
async def log_review(self, data: dict) -> dict: ...
async def get_reviews(self, **params) -> list: ...

# Sprint
async def sprint_status(self, **params) -> dict: ...
async def sprint_plan(self, data: dict) -> dict: ...

# Hourly Goals
async def set_hourly_goal(self, data: dict) -> dict: ...
async def get_hourly_goals(self, **params) -> list: ...
async def complete_hourly_goal(self, goal_id: str) -> dict: ...
```

Each method delegates to `self._client` internally but provides a stable public interface.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | api_client is L1 gateway — correct place for these methods |
| 2 | .env for secrets | ❌ | No secrets |
| 3 | models.yaml single source | ❌ | No models |
| 4 | Docker-first testing | ✅ | Test with full stack |
| 5 | aria_memories writable path | ❌ | No memory changes |
| 6 | No soul modification | ❌ | No soul changes |

## Dependencies
- S-113 depends on this ticket (refactor skills to use new methods)

## Verification
```bash
# 1. Verify all public methods exist
python -c "
from aria_skills.api_client import ApiClientSkill
methods = [m for m in dir(ApiClientSkill) if not m.startswith('_')]
required = ['create_goal', 'get_goal', 'list_goals', 'update_goal',
            'create_activity', 'list_agents', 'kg_add_entity', 'remember']
for r in required:
    assert r in methods, f'Missing method: {r}'
print(f'All {len(required)} required methods present')
"
# EXPECTED: All 8 required methods present

# 2. Run existing tests
pytest tests/ -v
# EXPECTED: all pass
```

## Prompt for Agent
```
Read these files first:
- aria_skills/api_client/__init__.py (full file)
- aria_skills/goals/__init__.py (find _client usage patterns)
- aria_skills/working_memory/__init__.py (find _client usage patterns)
- aria_skills/agent_manager/__init__.py (find _client usage patterns)

Steps:
1. Catalog ALL _client.get, _client.post, _client.patch, _client.delete calls across 11 skills
2. Group by resource (goals, activities, agents, KG, schedule, memory, etc.)
3. Create public methods in api_client for each resource
4. Each method: proper error handling, return typed dict
5. Test: verify methods exist and have correct signatures
6. Do NOT refactor the skills yet (that's S-113)
```
