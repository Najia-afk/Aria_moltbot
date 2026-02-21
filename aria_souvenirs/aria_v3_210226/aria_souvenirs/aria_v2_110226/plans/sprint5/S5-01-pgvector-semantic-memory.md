# S5-01: Add pgvector Semantic Memory Layer
**Epic:** E12 — Memory v2 | **Priority:** P0 | **Points:** 8 | **Phase:** 4

## Problem
Aria's memory is key-value based (JSONB in PostgreSQL). She can recall exact keys but cannot search by meaning. When she needs to find "that conversation about cron noise," she has no way to semantically query her memories.

Sprint 4's knowledge graph helps for structured skill/entity relationships, but unstructured memories (conversations, decisions, learnings) remain unsearchable by similarity.

## Root Cause
No vector embedding storage exists. PostgreSQL 16 supports pgvector, but no table uses it.

## Fix

### Step 1: Enable pgvector extension
**File: Alembic migration**
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Step 2: Add semantic memory table
**File: `src/api/db/models.py`**
```python
from pgvector.sqlalchemy import Vector

class SemanticMemory(Base):
    __tablename__ = "semantic_memories"
    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    content: Mapped[str] = mapped_column(Text, nullable=False)  # The actual memory text
    summary: Mapped[str] = mapped_column(Text)  # One-line summary for display
    category: Mapped[str] = mapped_column(String(50), server_default=text("'general'"))  # episodic, procedural, semantic, decision
    embedding: Mapped[Any] = mapped_column(Vector(768), nullable=False)  # nomic-embed-text or similar
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, server_default=text("'{}'::jsonb"))
    importance: Mapped[float] = mapped_column(Float, server_default=text("0.5"))  # 0-1 importance score
    source: Mapped[str] = mapped_column(String(100))  # conversation, heartbeat, goal, error, etc.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # Last retrieval time
    access_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    
    __table_args__ = (
        Index("idx_semantic_embedding", "embedding", postgresql_using="ivfflat",
              postgresql_ops={"embedding": "vector_cosine_ops"}),
        Index("idx_semantic_category", "category"),
        Index("idx_semantic_importance", "importance"),
        Index("idx_semantic_created", "created_at"),
    )
```

### Step 3: Add embedding generation endpoint
**File: `src/api/routers/memories.py`** (new or extend existing)
```python
@router.post("/memories/semantic")
async def store_semantic_memory(
    content: str,
    category: str = "general",
    importance: float = 0.5,
    source: str = "api",
    summary: str = None,
    db: AsyncSession = Depends(get_db),
):
    """Store a memory with its vector embedding."""
    # Generate embedding via LiteLLM
    embedding = await generate_embedding(content)
    
    memory = SemanticMemory(
        content=content,
        summary=summary or content[:100],
        category=category,
        embedding=embedding,
        importance=importance,
        source=source,
        metadata_={"original_length": len(content)},
    )
    db.add(memory)
    await db.commit()
    return {"id": str(memory.id), "stored": True}


@router.get("/memories/search")
async def search_memories(
    query: str,
    limit: int = 5,
    category: str = None,
    min_importance: float = 0.0,
    db: AsyncSession = Depends(get_db),
):
    """Search memories by semantic similarity."""
    query_embedding = await generate_embedding(query)
    
    stmt = select(
        SemanticMemory,
        SemanticMemory.embedding.cosine_distance(query_embedding).label("distance")
    ).order_by("distance").limit(limit)
    
    if category:
        stmt = stmt.where(SemanticMemory.category == category)
    if min_importance > 0:
        stmt = stmt.where(SemanticMemory.importance >= min_importance)
    
    result = await db.execute(stmt)
    memories = []
    for mem, dist in result.all():
        # Update access stats
        mem.accessed_at = func.now()
        mem.access_count += 1
        memories.append({
            **mem.to_dict(),
            "similarity": 1 - dist,  # Convert distance to similarity
        })
    await db.commit()
    return {"memories": memories, "query": query}


async def generate_embedding(text: str) -> list[float]:
    """Generate embedding via LiteLLM embedding endpoint."""
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{LITELLM_URL}/embeddings",
            json={"model": "nomic-embed-text", "input": text},
            headers={"Authorization": f"Bearer {LITELLM_KEY}"},
            timeout=30,
        )
        return resp.json()["data"][0]["embedding"]
```

### Step 4: Add api_client methods
**File: `aria_skills/api_client/__init__.py`**
```python
async def store_memory_semantic(self, content: str, category: str = "general",
                                 importance: float = 0.5, source: str = "aria") -> SkillResult:
    """Store a memory with vector embedding for semantic search."""
    return await self.post("/memories/semantic", json={
        "content": content, "category": category,
        "importance": importance, "source": source,
    })

async def search_memories(self, query: str, limit: int = 5,
                           category: str = None) -> SkillResult:
    """Search memories by semantic similarity."""
    params = {"query": query, "limit": limit}
    if category:
        params["category"] = category
    return await self.get("/memories/search", params=params)
```

### Step 5: Add embedding model to models.yaml
```yaml
nomic-embed-text:
  provider: ollama
  type: embedding
  dimensions: 768
  purpose: semantic memory search
  cost: 0  # local model
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | DB model + API + api_client |
| 2 | .env secrets | ✅ | LITELLM_KEY from env |
| 3 | models.yaml | ✅ | Embedding model in SSOT |
| 4 | Docker-first | ✅ | Test in Docker, pgvector in Dockerfile |
| 5 | aria_memories | ❌ | DB storage |
| 6 | No soul mod | ❌ | No soul files |

## Dependencies
- pgvector extension must be available in PostgreSQL container
- nomic-embed-text (or similar) must be available via LiteLLM/Ollama

## Verification
```bash
# 1. Extension loaded:
docker exec aria-db psql -U aria -d aria -c "SELECT * FROM pg_extension WHERE extname='vector';"
# EXPECTED: 1 row

# 2. Table exists:
docker exec aria-db psql -U aria -d aria -c "\d semantic_memories"
# EXPECTED: table with embedding column

# 3. Store a memory:
curl -s -X POST 'http://localhost:8000/api/memories/semantic' \
  -H 'Content-Type: application/json' \
  -d '{"content": "Fixed cron noise by setting delivery to none", "category": "procedural", "importance": 0.8}'
# EXPECTED: {"id": "...", "stored": true}

# 4. Search by meaning:
curl -s 'http://localhost:8000/api/memories/search?query=cron+spam+fix&limit=3'
# EXPECTED: returns the cron memory with high similarity
```

## Prompt for Agent
```
Add pgvector semantic memory to Aria.

FILES TO READ:
- src/api/db/models.py (add SemanticMemory model)
- src/api/routers/ (add/extend memories router)
- aria_skills/api_client/__init__.py (add methods)
- aria_models/models.yaml (add embedding model)
- Dockerfile (ensure pgvector)

STEPS:
1. Enable pgvector extension (Alembic migration)
2. Create SemanticMemory model with Vector(768) column + IVFFlat index
3. Add POST /memories/semantic + GET /memories/search endpoints
4. Generate embeddings via LiteLLM /embeddings endpoint
5. Add api_client methods
6. Add nomic-embed-text to models.yaml
7. Verify with curl tests

CONSTRAINTS: 5-layer. Local embedding model (zero cost). models.yaml SSOT.
```
