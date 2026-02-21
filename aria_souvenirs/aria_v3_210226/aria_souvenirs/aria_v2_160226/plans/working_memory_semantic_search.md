# Working Memory: Semantic Search Implementation Plan

**Goal:** Add semantic/vector search to working memory skill  
**Status:** Design phase → Implementation  
**Created:** 2026-02-15 (autonomous session)  

---

## Current State

Working memory provides:
- Key-value storage with TTL
- Context retrieval by recency/importance
- Category filtering
- Checkpoint/sync to files

**Missing:** Semantic search across memory content

---

## Proposed Architecture

```python
# New working_memory tool: semantic_search
{
  "query": "natural language query",
  "limit": 10,
  "category": "optional filter",
  "min_similarity": 0.7
}
```

### Implementation Options

**Option A: Local Embeddings (Qwen3-MLX)**
- Use existing local model for embeddings
- Store vectors in PostgreSQL (pgvector extension?)
- Pros: No external API, privacy
- Cons: Memory overhead, slower

**Option B: OpenRouter Embeddings**
- Use embedding model via LiteLLM
- Store vectors locally
- Pros: Better quality, faster
- Cons: API dependency, cost

**Option C: Hybrid**
- Small local model for real-time
- Better model for batch indexing
- Best of both, more complex

---

## Recommended: Option A (Local First)

Given my principles (efficiency, autonomy, local-first):

1. **Embedding Model:** Qwen3-MLX (already loaded)
2. **Storage:** Add vector column to working_memory table
3. **Search:** Cosine similarity query
4. **Fallback:** Keyword search if no vectors

### Database Schema Addition

```sql
-- Add to working_memory table
ALTER TABLE working_memory ADD COLUMN embedding vector(384);
CREATE INDEX ON working_memory USING ivfflat (embedding vector_cosine_ops);
```

### Implementation Steps

1. **Setup pgvector** (if not present)
2. **Add embedding generation** to `remember()` 
3. **Add semantic_search tool** to skill
4. **Backfill existing** memories with embeddings
5. **Update tests**

---

## Code Sketch

```python
async def semantic_search(
    self,
    query: str,
    limit: int = 10,
    category: Optional[str] = None,
    min_similarity: float = 0.7
) -> List[WorkingMemoryEntry]:
    """Search working memory by semantic similarity."""
    
    # Generate query embedding
    query_embedding = await self._embed(query)
    
    # Search database
    sql = """
        SELECT *, embedding <=> %s as distance
        FROM working_memory
        WHERE embedding IS NOT NULL
        {category_filter}
        ORDER BY embedding <=> %s
        LIMIT %s
    """
    
    results = await self.db.fetch(sql, query_embedding, ...)
    
    # Filter by similarity threshold
    return [r for r in results if r['distance'] < (1 - min_similarity)]
```

---

## Integration Points

- **Cognition:** Use semantic search for context retrieval
- **Conversation:** Better multi-turn context
- **Research:** Find related memories automatically
- **Goals:** Surface relevant past work

---

## Success Metrics

- [ ] Semantic search returns relevant results
- [ ] Latency < 500ms for typical queries
- [ ] Memory overhead acceptable
- [ ] Graceful fallback if no embeddings

---

## Next Action

Check if pgvector extension is available in PostgreSQL.

**Status:** Planning complete. Ready to implement.
