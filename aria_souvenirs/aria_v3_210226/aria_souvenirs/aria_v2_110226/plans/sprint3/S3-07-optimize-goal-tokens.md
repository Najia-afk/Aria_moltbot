# S3-07: Optimize Goal Token Usage for Aria
**Epic:** E6 — Token Optimization | **Priority:** P1 | **Points:** 3 | **Phase:** 2

## Problem
Aria calls `get_goals(limit=100)` returning ~5000 tokens when she just needs current sprint status (~200 tokens).

## Root Cause
No lightweight goal status endpoint was available. S3-02 adds sprint-summary; this ticket wires it into Aria's cognitive loop.

## Fix

### File: `aria_mind/TOOLS.md`
Add sprint tools documentation:
```yaml
# Sprint Status (token-efficient — ~200 tokens vs ~5000)
aria-sprint-manager.sprint_status({})
aria-sprint-manager.sprint_report({})
```

### File: `aria_mind/cognition.py`
Find goal checks and replace full `get_goals()` with `get_sprint_summary()`:
```python
sprint_result = await api_client.get_sprint_summary()
```

### File: `aria_mind/heartbeat.py`
Cache sprint context in working memory:
```python
await api_client.remember(key="current_sprint", value=summary, category="sprint", importance=0.8, ttl_hours=1)
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Uses api_client |
| 2 | .env | ❌ | No secrets |
| 3 | models.yaml | ❌ | No model names |
| 4 | Docker-first | ✅ | Test in Docker |
| 5 | aria_memories | ✅ | Working memory via API |
| 6 | No soul mod | ❌ | No soul files |

## Dependencies
- S3-02 (sprint-summary API), S3-04 (PO skill), S3-05 (api_client methods)

## Verification
```bash
grep 'sprint_status\|sprint_summary' aria_mind/TOOLS.md
# EXPECTED: documented
curl -s http://localhost:8000/api/goals/sprint-summary | wc -c
# EXPECTED: < 500 bytes
```

## Prompt for Agent
```
Optimize Aria's goal checking to use sprint_summary instead of full goal list.
FILES: aria_mind/TOOLS.md, cognition.py, heartbeat.py, api_client/__init__.py
```
