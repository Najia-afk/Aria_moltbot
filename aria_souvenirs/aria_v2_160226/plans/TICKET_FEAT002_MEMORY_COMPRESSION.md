# Sprint Ticket: FEAT-002 — Memory Compression Wrapper
**Priority:** P1 | **Points:** 2 | **Phase:** 2  
**Estimate:** 30 minutes

## Problem
Context windows grow unbounded. Old memories consume tokens without proportional value. Token usage for context exceeds 4000 tokens when it should be <2000.

## Root Cause
`working_memory` has no compression layer. The prototype (`memory_compression.py`, 491 lines) builds a full 3-tier compression system from scratch — but the API already provides `summarize_session()` which does LLM-based compression.

## Architecture Decision
**Wrap existing API, don't rebuild.** Per `EMBEDDING_REVISED.md`:
- Use `api_client.summarize_session(hours_back=N)` for session compression
- Use `api_client.store_memory_semantic()` to store compressed results
- Keep it thin — a wrapper skill, not a compression engine

## Implementation

### File: `aria_skills/memory_compression/__init__.py` (NEW)

```python
"""Memory compression — wraps api_client.summarize_session() for episodic memory."""
from datetime import datetime, timezone
from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.registry import SkillRegistry


@SkillRegistry.register
class MemoryCompressionSkill(BaseSkill):
    """Compress session history into episodic semantic memories."""

    def __init__(self, config: SkillConfig | None = None):
        super().__init__(config or SkillConfig(name="memory_compression"))
        self._api = None

    @property
    def name(self) -> str:
        return "memory_compression"

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
    async def compress_session(self, hours_back: int = 6, **kwargs) -> SkillResult:
        """
        Compress recent session activity into a semantic memory summary.
        Uses api_client.summarize_session() which LLM-summarizes activities
        from the last N hours and stores as episodic semantic memory.

        Args:
            hours_back: How many hours of activity to compress (default: 6).
        """
        hours_back = int(kwargs.get("hours_back", hours_back))
        if hours_back < 1:
            hours_back = 1
        if hours_back > 48:
            hours_back = 48

        if self._api is None:
            return SkillResult.fail("api_client not available")

        try:
            result = await self._api.summarize_session(hours_back=hours_back)
            if not result:
                return SkillResult.ok({
                    "compressed": False,
                    "reason": "No activities to compress in the last {} hours".format(hours_back),
                })

            return SkillResult.ok({
                "compressed": True,
                "hours_back": hours_back,
                "summary": result if isinstance(result, str) else str(result),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            return SkillResult.fail(f"Compression failed: {e}")

    @logged_method()
    async def get_context_budget(self, max_tokens: int = 2000, **kwargs) -> SkillResult:
        """
        Retrieve working memory context within a token budget.
        Uses api_client.get_working_memory_context() with weighted relevance.

        Args:
            max_tokens: Maximum tokens for context (default: 2000).
        """
        max_tokens = int(kwargs.get("max_tokens", max_tokens))
        if self._api is None:
            return SkillResult.fail("api_client not available")

        try:
            # Fetch weighted context
            context = await self._api.get_working_memory_context(
                limit=20,
                weight_recency=0.4,
                weight_importance=0.4,
                weight_access=0.2,
                touch_access=True,
            )

            items = context if isinstance(context, list) else context.get("items", []) if isinstance(context, dict) else []

            # Estimate tokens (rough: 1 token ≈ 4 chars)
            total_chars = 0
            selected = []
            for item in items:
                val = str(item.get("value", "")) if isinstance(item, dict) else str(item)
                chars = len(val)
                if total_chars + chars > max_tokens * 4:
                    break
                total_chars += chars
                selected.append(item)

            return SkillResult.ok({
                "items_count": len(selected),
                "total_available": len(items),
                "estimated_tokens": total_chars // 4,
                "budget": max_tokens,
                "items": selected,
            })
        except Exception as e:
            return SkillResult.fail(f"Context retrieval failed: {e}")

    async def close(self) -> None:
        self._status = SkillStatus.UNAVAILABLE
```

### File: `aria_skills/memory_compression/skill.json` (NEW)

```json
{
  "name": "memory_compression",
  "canonical_name": "aria-memory-compression",
  "version": "1.0.0",
  "description": "Compress session history into episodic semantic memories",
  "layer": "L2",
  "focus_affinity": ["data", "memory"],
  "tools": [
    {
      "name": "compress_session",
      "description": "LLM-summarize recent activity into semantic memory",
      "parameters": {
        "hours_back": {"type": "integer", "required": false, "description": "Hours of activity to compress (default: 6)"}
      }
    },
    {
      "name": "get_context_budget",
      "description": "Retrieve working memory within a token budget",
      "parameters": {
        "max_tokens": {"type": "integer", "required": false, "description": "Max tokens for context (default: 2000)"}
      }
    }
  ],
  "dependencies": ["api_client"],
  "rate_limit": {"max_per_minute": 10}
}
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | YES | Uses api_client only, no direct DB |
| 2 | .env for secrets | N/A | api_client handles URL from env |
| 3 | models.yaml source of truth | N/A | LLM call handled by backend |
| 4 | Docker-first testing | YES | Requires aria-api running |
| 5 | aria_memories only writable | YES | Stores via API |
| 6 | No soul modification | N/A | |

## Dependencies
- BUG-001 (general stability)
- `api_client` must be available
- `aria-api` must be running (for `summarize_session`)

## Verification
```bash
# 1. Files exist:
ls aria_skills/memory_compression/__init__.py aria_skills/memory_compression/skill.json

# 2. Import works:
python3 -c "from aria_skills.memory_compression import MemoryCompressionSkill; print('OK')"
# EXPECTED: OK
```
