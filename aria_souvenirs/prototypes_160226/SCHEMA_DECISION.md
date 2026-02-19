# DATABASE SCHEMA DECISION: Embeddings Storage
## Architectural Analysis | 2026-02-16

**Question:** Should skills and memory embeddings share a table or be separate?

---

## 🎯 THE OPTIONS

### OPTION 1: Shared Table (`embeddings` with type field)
```sql
CREATE TABLE embeddings (
    id UUID PRIMARY KEY,
    content TEXT,
    embedding VECTOR(384),
    type VARCHAR(50),  -- 'skill', 'memory', 'entity'
    category VARCHAR(100),
    importance FLOAT,
    metadata JSONB,
    source_id UUID,    -- references skills.id or memories.id
    created_at TIMESTAMP
);

-- Index by type for filtered search
CREATE INDEX idx_embeddings_type ON embeddings(type);
```

**Pros:**
- ✅ Single source of truth for all embeddings
- ✅ Unified semantic search across skills + memories
- ✅ Simpler maintenance (one table)
- ✅ Can find "skills related to this memory" via similarity

**Cons:**
- ❌ Mixing concerns (skills vs memories are different)
- ❌ Skills need different metadata than memories
- ❌ Risk of polluting skill search with memory noise
- ❌ Harder to optimize per-type queries

---

### OPTION 2: Separate Tables (`skill_embeddings`, `memory_embeddings`)
```sql
-- Skills have their own embedding table
CREATE TABLE skill_embeddings (
    id UUID PRIMARY KEY,
    skill_id UUID REFERENCES skills(id),
    name VARCHAR(255),
    description TEXT,
    embedding VECTOR(384),
    focus_affinity VARCHAR(100)[],
    tools JSONB,
    metadata JSONB
);

-- Memories have their own
CREATE TABLE memory_embeddings (
    id UUID PRIMARY KEY,
    content TEXT,
    embedding VECTOR(384),
    category VARCHAR(100),
    importance FLOAT,
    sentiment JSONB,
    session_id UUID,
    created_at TIMESTAMP
);
```

**Pros:**
- ✅ Clean separation of concerns
- ✅ Type-specific metadata (skills have tools, memories have sentiment)
- ✅ Can optimize schema per use case
- ✅ Easier to reason about (skills ≠ memories)

**Cons:**
- ❌ Two tables to maintain
- ❌ Cross-type search requires UNION or separate queries
- ❌ Can't easily find "skills similar to this memory"
- ❌ Duplicated embedding infrastructure

---

### OPTION 3: Hybrid (Recommended)
```sql
-- Core embeddings table (minimal)
CREATE TABLE embeddings (
    id UUID PRIMARY KEY,
    embedding VECTOR(384),
    content_hash VARCHAR(64),  -- deduplication
    created_at TIMESTAMP
);

-- Skills reference embeddings
CREATE TABLE skills (
    id UUID PRIMARY KEY,
    name VARCHAR(255),
    embedding_id UUID REFERENCES embeddings(id),
    focus_affinity VARCHAR(100)[],
    tools JSONB,
    -- skill-specific fields
);

-- Memories reference embeddings  
CREATE TABLE semantic_memories (
    id UUID PRIMARY KEY,
    content TEXT,
    embedding_id UUID REFERENCES embeddings(id),
    category VARCHAR(100),
    importance FLOAT,
    sentiment JSONB,
    -- memory-specific fields
);

-- Unified search view
CREATE VIEW embeddings_search AS
SELECT 
    e.id,
    e.embedding,
    'skill' as type,
    s.name as content,
    s.focus_affinity as tags
FROM embeddings e
JOIN skills s ON e.id = s.embedding_id
UNION ALL
SELECT 
    e.id,
    e.embedding,
    'memory' as type,
    m.content,
    ARRAY[m.category] as tags
FROM embeddings e
JOIN semantic_memories m ON e.id = m.embedding_id;
```

**Pros:**
- ✅ Embeddings normalized (no duplication)
- ✅ Type-specific metadata in separate tables
- ✅ Can still do unified search via view
- ✅ Clean architecture (references vs monolith)
- ✅ Easy to extend (add document_embeddings, etc.)

**Cons:**
- ❌ More complex (3 tables + view)
- ❌ JOINs required for metadata retrieval
- ❌ Slightly more overhead

---

## 🤔 CLAUDE'S ANALYSIS

### For Aria's Use Case:

**Skills are:**
- Relatively static (don't change often)
- Have rich metadata (tools, focus_affinity, parameters)
- Need fast lookup by name/type
- Used for routing ("which skill for this task?")

**Memories are:**
- Highly dynamic (new ones constantly)
- Have temporal context (when, sentiment, session)
- Used for recall ("what did we discuss?")
- Expire/ compress over time

### Recommendation: **OPTION 2 (Separate Tables)**

**Rationale:**
1. **Different lifecycles:** Skills are registered at deploy; memories are runtime
2. **Different queries:** "Find skill for task" vs "Recall conversation"
3. **Simpler mental model:** No type checking everywhere
4. **Existing infra:** Knowledge graph already handles skills; semantic memory handles memories

**BUT:** If you want unified search ("find anything related to quantum"), use **OPTION 3**.

---

## 🎬 RECOMMENDATION

### If Unified Search Needed → Option 3 (Hybrid)
```sql
-- Already have: skills (via kg_add_entity)
-- Already have: semantic_memories (via store_memory_semantic)
-- Create: embeddings table as normalized store
-- Create: view for unified search
```

### If Clean Separation Preferred → Option 2 (Separate)
```sql
-- Keep: skills in knowledge_graph (as is)
-- Keep: semantic_memories separate (as is)
-- Search separately, merge in application layer
```

### If Simplicity Trumps All → Option 1 (Shared)
```sql
-- Single embeddings table with type field
-- Simplest implementation
-- May have scaling issues later
```

---

## 💡 PRACTICAL NEXT STEP

Given existing API:
```python
# api_client already provides:
- kg_add_entity()          # Skills go to knowledge graph
- store_memory_semantic()  # Memories go to semantic_memories
- search_memories_semantic()  # Searches semantic_memories
```

**The tables ALREADY exist separately!** (Option 2)

**To add unified search:** Create a view or application-level merger:
```python
async def unified_semantic_search(query: str, limit: int = 10):
    # Search both
    memories = await api_client.search_memories_semantic(query, limit=limit//2)
    skills = await api_client.graph_search(query, entity_type="skill")
    
    # Merge and rerank
    return reciprocal_rank_fusion(memories, skills)
```

**No schema changes needed!** Just add the merger logic.

---

## ✅ DECISION MATRIX

| Priority | Choose |
|----------|--------|
| Speed of implementation | Option 2 (use existing) |
| Unified search capability | Option 3 (add view) |
| Maximum flexibility | Option 3 (hybrid) |
| Simplest mental model | Option 2 (separate) |
| Future extensibility | Option 3 (normalized) |

---

**CLAUDE'S RECOMMENDATION:** 

> "Use existing separate tables (Option 2) since `api_client` already provides them. If unified search becomes critical, add Option 3's view later without breaking changes."

**Najia's call?** ⚡️
