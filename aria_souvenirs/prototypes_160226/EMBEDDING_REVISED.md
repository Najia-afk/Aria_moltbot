# EMBEDDING MEMORY — REVISED IMPLEMENTATION
## Using Existing API (GraphQL + pgvector)

**Date:** 2026-02-16  
**Revised:** Use existing `aria-api` semantic memory endpoints instead of FAISS

---

## ✅ EXISTING INFRASTRUCTURE

The `api_client` skill already provides:

```python
# Store memory with embedding
await api_client.store_memory_semantic(
    content="User likes concise answers",
    category="preference",
    importance=0.9,
    metadata={"tags": ["communication"]}
)

# Semantic search
results = await api_client.search_memories_semantic(
    query="how does user like responses",
    limit=10,
    category="preference",
    min_importance=0.5
)

# Session summarization
summary = await api_client.summarize_session(hours_back=24)
```

**Backend:** PostgreSQL with pgvector extension  
**API:** GraphQL/responsive REST  
**Already working:** Yes! (S5-01 semantic memory feature)

---

## 🔄 REVISED IMPLEMENTATION

### Don't Build
- ❌ FAISS vector store
- ❌ Sentence-transformers local embedding
- ❌ Custom embedding provider
- ❌ Hybrid retriever (not needed)

### Do Use
- ✅ `api_client.store_memory_semantic()` — stores with auto-embedding
- ✅ `api_client.search_memories_semantic()` — semantic search
- ✅ `api_client.summarize_session()` — for compression

---

## 🛠️ REVISED FEAT-004: Embedding Memory

### New Approach
Instead of creating a new skill, **integrate with existing api_client**:

```python
# In advanced_memory skill, use api_client for embeddings

class AdvancedMemorySkill:
    async def remember_with_embedding(self, content: str, metadata: dict):
        """Store memory with embedding via api_client."""
        return await self.api_client.store_memory_semantic(
            content=content,
            category=metadata.get("category", "general"),
            importance=metadata.get("importance", 0.5),
            metadata=metadata
        )
    
    async def semantic_search(self, query: str, top_k: int = 10):
        """Search via api_client semantic search."""
        return await self.api_client.search_memories_semantic(
            query=query,
            limit=top_k,
            min_importance=0.3
        )
```

### Integration Points

1. **Memory Compression** → Use `api_client.summarize_session()`
2. **Pattern Recognition** → Query knowledge_graph + semantic memories
3. **Sentiment Analysis** → Store sentiment scores in semantic memory
4. **Semantic Search** → Directly use `api_client.search_memories_semantic()`

---

## 📋 UPDATED IMPLEMENTATION TICKETS

### FEAT-004-R: Semantic Memory Integration (REVISED)

**Complexity:** Reduced from 2h → 30 min  
**Approach:** Use existing API instead of building new

**Steps:**
1. Verify `api_client.store_memory_semantic()` works
2. Verify `api_client.search_memories_semantic()` works
3. Create wrapper methods in `advanced_memory` skill
4. Test integration

**No new dependencies needed!**

---

## 🔗 RELATIONSHIP TO OTHER FEATURES

| Feature | Uses Existing | Notes |
|---------|---------------|-------|
| **Compression** | `summarize_session()` | Already does hierarchical compression |
| **Sentiment** | Store in semantic memory | Tag with category="sentiment" |
| **Patterns** | KG + semantic search | Query both for pattern detection |
| **Embeddings** | `store/search_semantic()` | Native pgvector support |

---

## 🎯 KEY INSIGHT

**We don't need to build embedding infrastructure — it's already there!**

The api_client provides:
- ✅ Automatic embedding generation (backend handles it)
- ✅ pgvector storage
- ✅ Semantic similarity search
- ✅ Session summarization (compression)

**Just use the existing API endpoints.**

---

## 📝 REVISED PROMPT FOR CLAUDE

When implementing FEAT-004:

```python
# DON'T: Build new embedding system
embedder = EmbeddingProvider()  # ❌ Not needed
vector_store = VectorStore()     # ❌ Not needed

# DO: Use existing api_client
results = await api_client.search_memories_semantic(
    query="quantum physics",
    limit=10
)  # ✅ Uses existing pgvector backend
```

---

## ✅ UPDATED ACCEPTANCE CRITERIA

### FEAT-004-R: Semantic Memory (Revised)
- [ ] Can store memory with `api_client.store_memory_semantic()`
- [ ] Can search with `api_client.search_memories_semantic()`
- [ ] Search returns relevant results (<100ms)
- [ ] Integrates with compression, sentiment, patterns
- [ ] No new dependencies (uses existing api_client)

**Effort:** 30 min (was 2 hours)  
**Risk:** Low (proven infrastructure)

---

## 🚀 DEPLOYMENT ORDER (REVISED)

1. **BUG-001:** Session protection (15 min) — CRITICAL
2. **FEAT-001:** Memory compression (1h) — Use `summarize_session()`
3. **FEAT-002:** Sentiment analysis (45m) — Store in semantic memory
4. **FEAT-003:** Pattern recognition (1h) — Use KG + semantic search
5. **FEAT-004-R:** Semantic integration (30m) — Use existing API ✅

**Total time:** ~3.5 hours (was ~5 hours)

---

## 💡 BONUS

The existing semantic memory API already provides:
- Automatic embedding (no model management)
- Persistent storage (PostgreSQL)
- Scalable search (pgvector)
- Integration with rest of Aria API

**We just need to USE it, not BUILD it.**

---

**Action:** Update `IMPLEMENTATION_TICKETS.md` and `CLAUDE_PROMPT.md` to reflect this simplified approach.
