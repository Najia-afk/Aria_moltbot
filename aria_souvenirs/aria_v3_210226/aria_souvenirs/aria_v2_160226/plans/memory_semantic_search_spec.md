# Semantic Search for Working Memory - Implementation Spec

## Overview
Add vector-based semantic search capability to the working memory system.

## API Endpoint Required

### POST /working-memory/search
Request:
```json
{
  "query": "user likes python",
  "limit": 10,
  "category": "preferences",
  "min_relevance": 0.7
}
```

Response:
```json
{
  "results": [
    {
      "id": "uuid",
      "key": "coding_preference",
      "value": "Python",
      "relevance_score": 0.92,
      "category": "preferences",
      "importance": 0.8
    }
  ],
  "query_embedding": [...],
  "total_matches": 15
}
```

## Implementation Steps

1. **Database Schema**
   - Add `embedding` column (vector type) to working_memory table
   - Add GIN index for fast similarity search
   - Migration: generate embeddings for existing items

2. **API Layer**
   - POST /working-memory/search endpoint
   - Query embedding generation via litellm
   - Cosine similarity search with pgvector

3. **Skill Layer**
   - Add `search()` method to WorkingMemorySkill (see draft below)

4. **Integration**
   - Use in get_context() for enhanced retrieval
   - Combine semantic + weighted ranking for best results

## Draft Skill Method

```python
@logged_method()
async def search(
    self,
    query: str,
    limit: int = 10,
    category: Optional[str] = None,
    min_relevance: float = 0.0,
) -> SkillResult:
    """Semantic search across working memory items."""
    if not self._api or not self._api._client:
        return SkillResult.fail("Working memory not initialized")
    try:
        payload: Dict[str, Any] = {
            "query": query,
            "limit": limit,
            "min_relevance": min_relevance,
        }
        if category:
            payload["category"] = category
        resp = await self._api._client.post("/working-memory/search", json=payload)
        resp.raise_for_status()
        return SkillResult.ok(resp.json())
    except Exception as e:
        return SkillResult.fail(f"search failed: {e}")
```

## Status: Spec Complete
Ready for backend implementation.
