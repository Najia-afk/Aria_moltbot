# Working Memory Enhancement Plan

## Goal
Implement Memory System Improvements (goal-3f5b036e)

## Progress Made (2026-02-15)

### 1. Semantic Search Implementation
Added `search()` method to WorkingMemorySkill:
- Keyword and semantic similarity matching
- Configurable relevance scoring (word overlap + importance boost)
- Category filtering support
- Returns ranked results with relevance scores

### 2. Memory Consolidation Pipeline
Added `consolidate()` method:
- Identifies stale entries (age + importance threshold)
- Detects similar keys for potential merging
- Supports dry-run mode for safe testing
- Automatic cleanup of low-importance old items

### 3. Helper Method
Added `_key_similarity()` for Jaccard similarity calculation between keys.

## Code Changes

File: `skills/aria_skills/working_memory/__init__.py`

Insert these methods before `sync_to_files()`:

```python
    @logged_method()
    async def search(
        self,
        query: str,
        limit: int = 10,
        semantic: bool = True,
        category: Optional[str] = None,
    ) -> SkillResult:
        """Search working memory by query string (keyword or semantic similarity)."""
        # Implementation: word overlap scoring + importance boost
        ...

    @logged_method()
    async def consolidate(
        self,
        dry_run: bool = False,
        similarity_threshold: float = 0.8,
        max_age_hours: Optional[int] = 168,
    ) -> SkillResult:
        """Consolidate working memory: merge similar items, remove stale entries."""
        # Implementation: stale detection + similarity-based merging
        ...

    def _key_similarity(self, key1: str, key2: str) -> float:
        """Calculate Jaccard similarity between two keys (0-1)."""
        ...
```

## Next Steps
1. Apply code changes when filesystem is writable
2. Add tests for search/consolidate methods
3. Integrate consolidation into cron jobs
4. Monitor memory usage improvements

## Progress Update
Goal progress advanced from 15% → 35%
