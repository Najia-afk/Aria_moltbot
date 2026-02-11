# S2-07: Update AriaAPIClient with Pagination Support
**Epic:** E2 — Pagination | **Priority:** P1 | **Points:** 3 | **Phase:** 1

## Problem
`aria_skills/api_client/__init__.py` (1013 lines) has methods like `get_goals(limit=100)`, `get_activities(limit=100)`, etc. After S2-06 adds pagination to the API, these methods need to support `page` parameter and handle the new `{items, total, page, limit, pages}` response format.

## Root Cause
The API client was written before pagination existed. All list methods just pass `limit` and return raw response. After S2-06, responses change from `[item1, item2, ...]` to `{items: [...], total: N, page: 1, ...}`.

## Fix

### File: `aria_skills/api_client/__init__.py`
Update all list methods to accept `page` param and pass it to the API.

Example for `get_goals`:
BEFORE:
```python
    async def get_goals(
        self, 
        limit: int = 100, 
        status: Optional[str] = None
    ) -> SkillResult:
        """Get goals."""
        try:
            url = f"/goals?limit={limit}"
            if status:
                url += f"&status={status}"
            resp = await self._client.get(url)
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
```
AFTER:
```python
    async def get_goals(
        self, 
        limit: int = 25, 
        page: int = 1,
        status: Optional[str] = None
    ) -> SkillResult:
        """Get goals (paginated)."""
        try:
            url = f"/goals?limit={limit}&page={page}"
            if status:
                url += f"&status={status}"
            resp = await self._client.get(url)
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
```

Apply to ALL list methods:
- `get_activities(limit, page)`
- `get_goals(limit, page, status)`
- `get_thoughts(limit, page)`
- `get_memories(limit, page, category)`
- `get_social_posts(limit, page, platform)`
- `get_sessions(limit, page, status)`
- `get_security_events(limit, page, threat_level, blocked_only)`
- `get_model_usage(limit, page)`
- `recall(key, category, limit, page)` (working memory)

Also add a convenience method:
```python
    async def get_all_pages(self, method_name: str, **kwargs) -> SkillResult:
        """Fetch all pages of a paginated endpoint."""
        all_items = []
        page = 1
        while True:
            result = await getattr(self, method_name)(page=page, **kwargs)
            if not result.success:
                return result
            data = result.data
            all_items.extend(data.get("items", []))
            if page >= data.get("pages", 1):
                break
            page += 1
        return SkillResult.ok({"items": all_items, "total": len(all_items)})
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | api_client is Layer 4 — correct layer for this change |
| 2 | .env for secrets (zero in code) | ❌ | No secrets involved |
| 3 | models.yaml single source of truth | ❌ | No model references |
| 4 | Docker-first testing | ✅ | Test via Docker |
| 5 | aria_memories only writable path | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul files touched |

## Dependencies
- **S2-06 must complete first** — this ticket updates the client to match the new paginated API format.

## Verification
```bash
# 1. Verify page param exists in get_goals:
grep -A5 'def get_goals' aria_skills/api_client/__init__.py | grep 'page'
# EXPECTED: page: int = 1

# 2. Verify page param in URL construction:
grep 'page=' aria_skills/api_client/__init__.py | head -10
# EXPECTED: Multiple lines with &page={page}

# 3. Verify get_all_pages helper exists:
grep -n 'get_all_pages' aria_skills/api_client/__init__.py
# EXPECTED: async def get_all_pages

# 4. Run tests:
cd src/api && python -m pytest -x -q
```

## Prompt for Agent
```
You are updating the Aria API client to support pagination.

FILES TO READ FIRST:
- aria_skills/api_client/__init__.py (full file — 1013 lines)
- src/api/pagination.py (created in S2-06 — response format reference)

STEPS:
1. Read api_client/__init__.py completely
2. Add `page: int = 1` parameter to ALL list methods (9 methods)
3. Add `&page={page}` to URL construction in each method
4. Change default limit from 100 to 25 (match API defaults)
5. Add `get_all_pages()` convenience method
6. Run verification commands

CONSTRAINTS: api_client layer only. No direct DB access. No secrets.
```
