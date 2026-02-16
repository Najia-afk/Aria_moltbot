# Sprint Ticket: FEAT-003 — Unified Semantic Search Wrapper
**Priority:** P2 | **Points:** 1 | **Phase:** 2  
**Estimate:** 20 minutes

## Problem
Skills and memories are searched through separate API calls. No unified search exists that queries both the skill graph and semantic memories, then merges results with ranking.

## Architecture Decision
Per `CLAUDE_SCHEMA_ADVICE.md` — **Option 2 (separate tables) with unified search wrapper.** The infrastructure already exists:
- `api_client.graph_search(q, entity_type)` — knowledge/skill graph ILIKE search
- `api_client.search_memories_semantic(query, limit)` — pgvector cosine similarity

We only need a thin merge layer using Reciprocal Rank Fusion (RRF).

## Implementation

### File: `aria_skills/unified_search/__init__.py` (NEW)

```python
"""Unified search — merges skill graph + semantic memory results."""
import asyncio
from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.registry import SkillRegistry


def _rrf_merge(results_lists: list[list[dict]], k: int = 60) -> list[dict]:
    """Reciprocal Rank Fusion: merge multiple ranked lists into one."""
    scores: dict[str, float] = {}
    items: dict[str, dict] = {}

    for result_list in results_lists:
        for rank, item in enumerate(result_list):
            item_id = str(item.get("id", item.get("name", id(item))))
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank + 1)
            if item_id not in items:
                items[item_id] = item

    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [items[iid] for iid in sorted_ids if iid in items]


@SkillRegistry.register
class UnifiedSearchSkill(BaseSkill):
    """Search across skill graph + semantic memories with RRF merge."""

    def __init__(self, config: SkillConfig | None = None):
        super().__init__(config or SkillConfig(name="unified_search"))
        self._api = None

    @property
    def name(self) -> str:
        return "unified_search"

    async def initialize(self) -> None:
        try:
            from aria_skills.api_client import AriaAPIClient
            self._api = AriaAPIClient()
            self._status = SkillStatus.READY
        except ImportError:
            self._status = SkillStatus.UNAVAILABLE

    async def health_check(self) -> SkillResult:
        if self._api is None:
            return SkillResult.fail("api_client not available")
        return SkillResult.ok({"status": "healthy"})

    @logged_method()
    async def search(self, query: str = "", limit: int = 10, **kwargs) -> SkillResult:
        """
        Search across skill graph and semantic memories, merge with RRF.

        Args:
            query: Search text.
            limit: Max results (split between sources).
        """
        query = query or kwargs.get("query", "")
        if not query:
            return SkillResult.fail("query is required")
        limit = int(kwargs.get("limit", limit))

        if self._api is None:
            return SkillResult.fail("api_client not available")

        try:
            # Parallel search across both sources
            skills_task = self._search_skills(query, limit)
            memories_task = self._search_memories(query, limit)
            skills_results, memory_results = await asyncio.gather(
                skills_task, memories_task, return_exceptions=True
            )

            # Handle partial failures gracefully
            skills_list = skills_results if isinstance(skills_results, list) else []
            memory_list = memory_results if isinstance(memory_results, list) else []

            merged = _rrf_merge([skills_list, memory_list])[:limit]

            return SkillResult.ok({
                "query": query,
                "results": merged,
                "total": len(merged),
                "sources": {
                    "skills": len(skills_list),
                    "memories": len(memory_list),
                },
            })
        except Exception as e:
            return SkillResult.fail(f"Search failed: {e}")

    async def _search_skills(self, query: str, limit: int) -> list[dict]:
        """Search skill graph entities."""
        try:
            result = await self._api.graph_search(q=query, limit=limit)
            if isinstance(result, dict):
                return result.get("entities", result.get("results", []))
            return result if isinstance(result, list) else []
        except Exception:
            return []

    async def _search_memories(self, query: str, limit: int) -> list[dict]:
        """Search semantic memories."""
        try:
            result = await self._api.search_memories_semantic(query=query, limit=limit)
            if isinstance(result, dict):
                return result.get("memories", result.get("results", []))
            return result if isinstance(result, list) else []
        except Exception:
            return []

    async def close(self) -> None:
        self._status = SkillStatus.UNAVAILABLE
```

### File: `aria_skills/unified_search/skill.json` (NEW)

```json
{
  "name": "unified_search",
  "canonical_name": "aria-unified-search",
  "version": "1.0.0",
  "description": "Search across skill graph + semantic memories with RRF merge",
  "layer": "L2",
  "focus_affinity": ["data", "memory"],
  "tools": [
    {
      "name": "search",
      "description": "Unified search across skills and memories",
      "parameters": {
        "query": {"type": "string", "required": true},
        "limit": {"type": "integer", "required": false, "description": "Max results (default: 10)"}
      }
    }
  ],
  "dependencies": ["api_client"],
  "rate_limit": {"max_per_minute": 30}
}
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | YES | Uses api_client only |
| 2 | .env for secrets | N/A | |
| 3 | models.yaml source of truth | N/A | |
| 4 | Docker-first testing | YES | Requires aria-api |
| 5 | aria_memories only writable | YES | Read-only search |
| 6 | No soul modification | N/A | |

## Dependencies
None — uses existing api_client methods.

## Verification
```bash
# 1. Import works:
python3 -c "from aria_skills.unified_search import UnifiedSearchSkill; print('OK')"
# EXPECTED: OK

# 2. RRF function works:
python3 -c "
from aria_skills.unified_search import _rrf_merge
r = _rrf_merge([[{'id':'a','name':'Skill A'},{'id':'b'}],[{'id':'b','name':'Memory B'},{'id':'c'}]])
print([x.get('id') for x in r])
"
# EXPECTED: ['b', 'a', 'c']  (b appears in both lists, ranked highest)
```
