# S-12: Cron Job Model Selection
**Epic:** E7 — Cron Model | **Priority:** P1 | **Points:** 3 | **Phase:** 2

## Problem
Cron jobs in `aria_engine/scheduler.py` dispatch tasks to agents via `_dispatch_to_agent()` (L410-L418), but there is no `model` parameter. The `EngineCronJob` DB schema has no model column. The `cron_jobs.yaml` config has no model field.

This means scheduled tasks always use the default model. Aria should be able to schedule a cron job that runs on a specific model (e.g., heavy analysis on kimi, lightweight pings on deepseek-chat).

## Root Cause
Cron system was built before multi-model support. The delegation chain (scheduler → agent_pool → chat_engine) supports model selection at the bottom but not at the top.

## Fix

### Fix 1: Add model column to EngineCronJob
**Via:** API migration (Constraint #1)
```sql
-- Conceptual (implement via ORM migration, not direct SQL)
ALTER TABLE aria_engine.engine_cron_jobs ADD COLUMN model VARCHAR(64) DEFAULT NULL;
```
NULL = use default model.

### Fix 2: Update cron_jobs.yaml schema
**File:** `aria_mind/cron_jobs.yaml`
```yaml
jobs:
  - name: memory-consolidation
    schedule: "0 */6 * * *"
    skill: memory_manager
    action: consolidate
    model: kimi          # NEW — optional
    
  - name: heartbeat
    schedule: "*/5 * * * *"
    skill: heartbeat
    action: check
    model: null           # NEW — null = default
```

### Fix 3: Update _dispatch_to_agent() to pass model
**File:** `aria_engine/scheduler.py` L410-L418

**BEFORE:**
```python
async def _dispatch_to_agent(self, job: dict):
    agent = await self.agent_pool.spawn_agent(
        name=f"cron-{job['name']}",
        role="worker",
        instructions=job.get("instructions", ""),
    )
```

**AFTER:**
```python
async def _dispatch_to_agent(self, job: dict):
    agent = await self.agent_pool.spawn_agent(
        name=f"cron-{job['name']}",
        role="worker",
        instructions=job.get("instructions", ""),
        model=job.get("model"),  # NEW — None = default
    )
```

### Fix 4: Update cron job loader to read model field
**File:** `aria_engine/scheduler.py` — find the YAML loading code and ensure it reads the `model` field from each job definition.

### Fix 5: Update cron management UI
**File:** `src/web/templates/` — find cron management template
Add a "Model" dropdown to the cron job create/edit form, populated from the models list.

### Fix 6: Update API cron endpoints
**Files:** `src/api/` — find cron-related endpoints
Add `model` field to create/update cron job schemas.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | DB migration via ORM, API endpoints |
| 2 | .env for secrets | ❌ | No secrets |
| 3 | models.yaml truth | ✅ | Model dropdown should use models from models.yaml/DB |
| 4 | Docker-first testing | ✅ | Test via Docker |
| 5 | aria_memories writable | ❌ | |
| 6 | No soul modification | ❌ | |

## Dependencies
- S-10 (agent model param) — for spawn_agent to accept model
- S-03 (model pruning) — for clean model list in dropdown

## Verification
```bash
# 1. Verify DB column exists:
curl -s http://localhost:8000/graphql -H 'Content-Type: application/json' \
  -d '{"query": "{ cronJobs { edges { node { name model } } } }"}'
# EXPECTED: model field present (null for most jobs)

# 2. Verify cron_jobs.yaml has model field:
grep 'model:' aria_mind/cron_jobs.yaml
# EXPECTED: model entries for some jobs

# 3. Verify _dispatch_to_agent passes model:
grep -A5 '_dispatch_to_agent' aria_engine/scheduler.py | grep 'model'
# EXPECTED: model=job.get("model")

# 4. Verify cron UI has model dropdown:
curl -s http://localhost:5050/operations/cron/ | grep 'model'
# EXPECTED: select/dropdown element for model

# 5. Create a cron job with model via API:
curl -X POST http://localhost:8000/engine/cron -H 'Content-Type: application/json' \
  -d '{"name": "test-cron", "schedule": "0 */6 * * *", "skill": "heartbeat", "action": "check", "model": "kimi"}'
# EXPECTED: 201 with model=kimi
```

## Prompt for Agent
```
Read these files FIRST:
- aria_engine/scheduler.py (full — especially _dispatch_to_agent at L410 and YAML loading)
- aria_mind/cron_jobs.yaml (full)
- aria_engine/agent_pool.py (L280-L320 — spawn_agent)
- src/api/ — find cron job CRUD endpoints
- src/web/templates/ — find cron management template

CONSTRAINTS: #1 (migration via ORM), #3 (model validation).

STEPS:
1. Add model column to cron job ORM model (nullable VARCHAR(64))
2. Create migration
3. Update YAML loader to read model field
4. Update _dispatch_to_agent() to pass model to spawn_agent()
5. Update API create/update cron handlers to accept model field
6. Update cron management UI template: add model dropdown populated from /models API
7. Update cron_jobs.yaml with model field for existing jobs (set to null for most)
8. Add validation: if model is specified, verify it exists
9. Run verification commands
```
