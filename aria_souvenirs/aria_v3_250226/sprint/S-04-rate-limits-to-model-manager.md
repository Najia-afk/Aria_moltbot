# S-04: Move Rate Limits into Model Manager
**Epic:** E2 — Model Pruning | **Priority:** P1 | **Points:** 5 | **Phase:** 2

## Problem
Rate limits are stored in a separate `aria_engine.rate_limits` table (only 4 rows, used as cache timestamps) and displayed in a separate `rate_limits.html` page (213 lines, auto-refresh every 30s). Meanwhile, `models_manager.html` (301 lines) already has a full CRUD modal for models. There is no reason for rate limits to be a standalone concept — they should be per-model parameters visible in the model manager.

As Aria herself said: "Why is rate_limits not just a param in model manager?"

## Root Cause
Rate limits were added as a quick cache/tracking mechanism. They were never integrated into the model entity. The `rate_limits` table schema doesn't even have `max_rpm` or `max_tpd` columns — it stores last-used timestamps.

## Fix

### Fix 1: Add rate limit columns to llm_models
**Via:** GraphQL migration / API endpoint (Constraint #1)
Add to `aria_engine.llm_models`:
- `max_rpm` INTEGER DEFAULT NULL — max requests per minute
- `max_tpd` INTEGER DEFAULT NULL — max tokens per day
- `cooldown_seconds` INTEGER DEFAULT 0 — backoff after rate limit hit

### Fix 2: Update models_manager.html modal
**File:** `src/web/templates/models_manager.html` L34-L127 (existing modal)
Add 3 fields to the model edit modal:
```html
<div class="form-group">
  <label>Max RPM</label>
  <input type="number" name="max_rpm" placeholder="null = unlimited">
</div>
<div class="form-group">
  <label>Max Tokens/Day</label>
  <input type="number" name="max_tpd" placeholder="null = unlimited">
</div>
<div class="form-group">
  <label>Cooldown (seconds)</label>
  <input type="number" name="cooldown_seconds" value="0">
</div>
```

### Fix 3: Show rate limit columns in models table
**File:** `src/web/templates/models_manager.html` — add columns to the models table
Add `Max RPM`, `Max TPD`, `Cooldown` columns after the existing columns.

### Fix 4: Update API model schema
**Files:** `src/api/` — update the model GraphQL type and mutations to include `max_rpm`, `max_tpd`, `cooldown_seconds`.

### Fix 5: Enforce rate limits in llm_gateway
**File:** `aria_engine/llm_gateway.py`
Before calling LiteLLM, check the model's `max_rpm` from the DB (via api_client). If exceeded, either wait `cooldown_seconds` or raise a rate limit exception.

### Fix 6: Remove standalone rate_limits page
**Files:**
- `src/web/templates/rate_limits.html` — DELETE
- `src/web/app.py` — remove `/rate-limits` route
- `src/web/templates/base.html` — remove rate_limits nav link from Models menu

### Fix 7: Deprecate rate_limits table
After migration and verification, mark `aria_engine.rate_limits` for removal in next sprint. Do NOT drop yet — keep for rollback safety.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | DB schema change via API migration, not direct SQL |
| 2 | .env for secrets | ❌ | No secrets involved |
| 3 | models.yaml truth | ✅ | Consider adding rate limit defaults to models.yaml |
| 4 | Docker-first testing | ✅ | Test with Docker compose |
| 5 | aria_memories writable | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul changes |

## Dependencies
- S-03 (model pruning) should be done first — fewer models to migrate

## Verification
```bash
# 1. Verify model schema has new columns:
curl -s http://localhost:8000/graphql -H 'Content-Type: application/json' \
  -d '{"query": "{ models { edges { node { modelId maxRpm maxTpd cooldownSeconds } } } }"}' | python -m json.tool
# EXPECTED: fields present, kimi has max_rpm set

# 2. Verify rate_limits page is gone:
curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/rate-limits
# EXPECTED: 404

# 3. Verify models_manager shows rate limit columns:
curl -s http://localhost:5050/models/manager | grep 'max_rpm'
# EXPECTED: form field present

# 4. Verify llm_gateway respects rate limits:
# Set kimi max_rpm=1 via API, send 2 rapid requests, verify second gets rate-limited
```

## Prompt for Agent
```
Read these files FIRST:
- src/web/templates/models_manager.html (full — 301 lines)
- src/web/templates/rate_limits.html (full — 213 lines)
- src/web/app.py (find both /rate-limits and /models/manager routes)
- src/api/ — find model-related GraphQL schemas and resolvers
- aria_engine/llm_gateway.py (full)

CONSTRAINTS: #1 (5-layer, no direct SQL), #3 (models.yaml source of truth).

STEPS:
1. Find the model ORM model in src/api/ — add max_rpm, max_tpd, cooldown_seconds columns
2. Create a migration (follow existing migration patterns)
3. Update GraphQL schema to expose new fields on Model type
4. Update mutations (createModel, updateModel) to accept new fields
5. Update models_manager.html: add form fields to modal AND columns to table
6. Update llm_gateway.py: before LiteLLM call, fetch model config, check RPM against a sliding window counter
7. Remove rate_limits.html template and its route from app.py
8. Remove rate_limits link from base.html nav (Models menu)
9. Consider adding max_rpm/max_tpd defaults to aria_models/models.yaml
10. Think about pagination when listing models (Constraint: always use pagination)
11. Run verification commands
```
