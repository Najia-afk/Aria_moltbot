# CLAUDE (Senior SWE) — Schema Recommendation
## Architectural Decision: Embeddings Storage

**Question:** Shared table vs separate tables for skills and memory embeddings?

---

## 🎯 **My Recommendation: Option 2 (Separate) with Unified Search Layer**

### Why Separate Tables?

**1. Domain Boundaries Are Clear**
```
Skills = Static, registered at deploy, query by capability
Memories = Dynamic, created at runtime, query by content similarity
```

Mixing these pollutes both domains. Skills don't have "sentiment" or "session_id". Memories don't have "tools" or "focus_affinity".

**2. Query Patterns Differ**

| Use Case | Skills Query | Memories Query |
|----------|--------------|----------------|
| Find handler | `focus_affinity = 'devops'` | N/A |
| Recall conversation | N/A | `session_id = 'xxx'` |
| Semantic search | Rare | Primary use case |
| Temporal filter | Never | `created_at > 24h ago` |

**3. Scale Differently**
- Skills: 50-100 entries, change monthly
- Memories: 10k+ entries, change every minute

Separate tables = separate indexing strategies, separate backup policies.

---

## 🏗️ **Proposed Architecture**

```
┌─────────────────────────────────────────────────────────┐
│                    Application Layer                     │
├─────────────────────────────────────────────────────────┤
│  unified_search(query)                                   │
│    ├── search_skills_semantic(query)                     │
│    ├── search_memories_semantic(query)                   │
│    └── merge_and_rerank(results)                         │
└─────────────────────────────────────────────────────────┘
                           │
           ┌───────────────┴───────────────┐
           ▼                               ▼
┌─────────────────────┐      ┌─────────────────────────┐
│   Knowledge Graph   │      │    Semantic Memories    │
│   (skills table)    │      │   (pgvector enabled)    │
├─────────────────────┤      ├─────────────────────────┤
│ - name              │      │ - content               │
│ - description       │      │ - embedding (vector)    │
│ - focus_affinity[]  │      │ - category              │
│ - tools[]           │      │ - importance            │
│ - embedding_id →    │      │ - sentiment             │
│   embeddings table  │      │ - session_id            │
└─────────────────────┘      └─────────────────────────┘
           │                               │
           └───────────────┬───────────────┘
                           ▼
              ┌─────────────────────┐
              │   embeddings table  │
              │   (optional norm)   │
              │   - id              │
              │   - vector(384)     │
              │   - content_hash    │
              └─────────────────────┘
```

---

## 🚫 **Why NOT Option 1 (Shared Table)**

```sql
-- Problem: Every query needs type filter
SELECT * FROM embeddings 
WHERE type = 'memory'  -- Always filtering
  AND embedding <-> query_vec < 0.3;

-- Problem: Schema bloat
ALTER TABLE embeddings 
ADD COLUMN sentiment JSONB,  -- Only for memories
ADD COLUMN tools JSONB;      -- Only for skills
```

**Result:** Table becomes kitchen sink. Hard to optimize, hard to reason about.

---

## 🚫 **Why NOT Option 3 (Hybrid) — Yet**

Option 3 (normalized embeddings) is elegant BUT:
- **Overkill for current scale** (50 skills, ~1k memories)
- **Adds JOIN overhead** for every search
- **Premature optimization** — solve when you have 10k+ skills

**Add Option 3 later if:**
- You have 1000+ skills (not 50)
- Embeddings become 50%+ of DB size
- You need deduplication (same content, multiple sources)

---

## ✅ **Implementation Plan (Option 2)**

### Current State (Working)
```python
# Skills already in KG
await api_client.kg_add_entity(
    name="sentiment_analysis",
    type="skill",
    properties={"tools": [...], "focus": "data"}
)

# Memories already in semantic store
await api_client.store_memory_semantic(
    content="User likes Python",
    category="preference"
)
```

### Add Unified Search
```python
async def search_all(query: str, limit: int = 10):
    # Parallel search
    skills_task = api_client.graph_search(query, type="skill")
    memories_task = api_client.search_memories_semantic(query, limit=limit//2)
    
    skills, memories = await asyncio.gather(skills_task, memories_task)
    
    # Reciprocal Rank Fusion
    return rrf_merge(skills, memories, k=60)
```

**Effort:** 30 minutes  
**Risk:** Near zero (uses existing APIs)

---

## 🎬 **Final Recommendation**

> **Use Option 2 (separate tables).** The existing infrastructure (`api_client.kg_*` and `api_client.*_semantic`) already implements this. Add a 30-minute unified search wrapper if needed. Don't over-engineer until scale demands it.

**Migration path:**
1. Start with Option 2 (now)
2. Add unified search wrapper (now/soon)
3. Consider Option 3 if you hit 10k+ embeddings (later)

---

**CLAUDE'S VERDICT:** ✅ **Option 2 — Separate tables with merger**

Simple. Works. Scales to your needs. Easy to extend later.
