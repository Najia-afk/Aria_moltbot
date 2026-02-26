"""
Memories endpoints — CRUD with upsert by key + semantic memory (S5-01).
"""

import json as json_lib
import logging
import math
import os
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Memory, SemanticMemory
from deps import get_db
from pagination import paginate_query, build_paginated_response
from schemas.requests import CreateMemory, CreateSemanticMemory, SearchByVector, SummarizeSession, UpdateMemory

# LiteLLM connection for embeddings
LITELLM_URL = os.environ.get("LITELLM_URL", "http://litellm:4000")
LITELLM_KEY = os.environ.get("LITELLM_MASTER_KEY", "")

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Memories"])

_NOISE_NAME_MARKERS = (
    "[test]",
    "pytest",
    "goal_test",
    "skill_test",
    "test_entry",
    "live test goal",
    "test goal",
    "testing skill functionality",
    "creative pulse ingestion test",
    "creative pulse full visualization test",
    "pulse-exp-",
    "live test post",
    "moltbook test",
    "abc123",
    "post 42",
    "x: 1",
    "\"x\": 1",
    "{\"x\": 1}",
    "{\"x\":1}",
    "x; 1",
)


def _contains_noise_name(text: str) -> bool:
    normalized = (text or "").lower()
    if any(marker in normalized for marker in _NOISE_NAME_MARKERS):
        return True
    if any(prefix in normalized for prefix in ("test-", "test_", "goal-test", "goal_test", "skill-test", "skill_test")):
        return True
    # token-aware fallback for standalone "test"
    return bool(re.search(r"\btest\b", normalized))


def _is_noise_activity_for_summary(action: str | None, skill: str | None, details: dict | None) -> bool:
    action_s = (action or "").lower()
    skill_s = (skill or "").lower()
    details_s = json_lib.dumps(details or {}, default=str).lower()

    hay = f"{action_s} {skill_s} {details_s}"
    if _contains_noise_name(hay):
        return True

    if action_s in {"heartbeat", "cron_execution"}:
        return True

    return "health_check" in hay


def _is_noise_memory_payload(
    key: str | None = None,
    value: str | None = None,
    content: str | None = None,
    summary: str | None = None,
    source: str | None = None,
    metadata: dict | None = None,
) -> bool:
    hay = " ".join(
        [
            key or "",
            str(value or ""),
            content or "",
            summary or "",
            source or "",
            json_lib.dumps(metadata or {}, default=str),
        ]
    )
    if _contains_noise_name(hay):
        return True

    key_s = (key or "").lower().strip()
    source_s = (source or "").lower().strip()
    if key_s.startswith(("test-", "test_", "goal-test", "goal_test", "skill-test", "skill_test")):
        return True
    if key_s.startswith("lookup-") and any(token in hay.lower() for token in ("\"x\": 1", "{\"x\":1}", "x: 1")):
        return True
    if source_s in {"pytest", "test", "test_runner", "sandbox_test"}:
        return True

    return False


@router.get("/memories")
async def get_memories(
    page: int = 1,
    limit: int = 25,
    category: str = None,
    db: AsyncSession = Depends(get_db),
):
    base = select(Memory).order_by(Memory.updated_at.desc())
    if category:
        base = base.where(Memory.category == category)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt, _ = paginate_query(base, page, limit)
    rows = (await db.execute(stmt)).scalars().all()
    items = [m.to_dict() for m in rows]
    return build_paginated_response(items, total, page, limit)


@router.post("/memories")
async def create_or_update_memory(
    body: CreateMemory, db: AsyncSession = Depends(get_db)
):
    key = body.key
    value = body.value
    category = body.category
    if _is_noise_memory_payload(key=key, value=str(value), metadata={"category": category}):
        return {"stored": False, "skipped": True, "reason": "test_or_noise_payload"}

    # Try update first
    result = await db.execute(select(Memory).where(Memory.key == key))
    existing = result.scalar_one_or_none()

    if existing:
        existing.value = value
        existing.category = category
        await db.commit()
        return {"id": str(existing.id), "key": key, "upserted": True}

    memory = Memory(key=key, value=value, category=category)
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    return {"id": str(memory.id), "key": key, "upserted": True}


# ===========================================================================
# Semantic Memory (S5-01 — pgvector)
# Must be registered BEFORE /memories/{key} to avoid route collision
# ===========================================================================

async def generate_embedding(text: str) -> list[float]:
    """Generate embedding via LiteLLM embedding endpoint."""
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{LITELLM_URL}/v1/embeddings",
            json={"model": "nomic-embed-text", "input": text},
            headers={"Authorization": f"Bearer {LITELLM_KEY}"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]


@router.get("/memories/semantic/stats")
async def semantic_memory_stats(db: AsyncSession = Depends(get_db)):
    """Return aggregate statistics for the semantic memory store."""
    from sqlalchemy import case, cast, String, text as sa_text

    total = (await db.execute(
        select(func.count()).select_from(SemanticMemory)
    )).scalar() or 0

    # Breakdown by category
    cat_rows = (await db.execute(
        select(SemanticMemory.category, func.count())
        .group_by(SemanticMemory.category)
        .order_by(func.count().desc())
    )).all()
    by_category = {r[0] or "general": r[1] for r in cat_rows}

    # Breakdown by source
    src_rows = (await db.execute(
        select(SemanticMemory.source, func.count())
        .group_by(SemanticMemory.source)
        .order_by(func.count().desc())
    )).all()
    by_source = {r[0] or "unknown": r[1] for r in src_rows}

    # Average importance
    avg_imp = (await db.execute(
        select(func.avg(SemanticMemory.importance))
    )).scalar()

    # Most recent and oldest
    newest = (await db.execute(
        select(func.max(SemanticMemory.created_at))
    )).scalar()
    oldest = (await db.execute(
        select(func.min(SemanticMemory.created_at))
    )).scalar()

    # Most accessed
    top_accessed = (await db.execute(
        select(SemanticMemory.summary, SemanticMemory.category, SemanticMemory.access_count)
        .where(SemanticMemory.access_count > 0)
        .order_by(SemanticMemory.access_count.desc())
        .limit(10)
    )).all()

    return {
        "total": total,
        "by_category": by_category,
        "by_source": by_source,
        "avg_importance": round(avg_imp or 0, 3),
        "newest": newest.isoformat() if newest else None,
        "oldest": oldest.isoformat() if oldest else None,
        "top_accessed": [
            {"summary": r[0], "category": r[1], "access_count": r[2]}
            for r in top_accessed
        ],
    }


@router.get("/memories/semantic")
async def list_semantic_memories(
    category: str = None,
    source: str = None,
    limit: int = 50,
    page: int = 1,
    min_importance: float = 0.0,
    db: AsyncSession = Depends(get_db),
):
    """List semantic memories with optional category/source filter. No embedding query needed."""
    base = select(SemanticMemory).order_by(SemanticMemory.created_at.desc())
    if category:
        base = base.where(SemanticMemory.category == category)
    if source:
        base = base.where(SemanticMemory.source == source)
    if min_importance > 0:
        base = base.where(SemanticMemory.importance >= min_importance)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt, _ = paginate_query(base, page, limit)
    rows = (await db.execute(stmt)).scalars().all()
    items = [m.to_dict() for m in rows]
    return build_paginated_response(items, total, page, limit)


@router.post("/memories/semantic")
async def store_semantic_memory(
    body: CreateSemanticMemory,
    db: AsyncSession = Depends(get_db),
):
    """Store a memory with its vector embedding for semantic search."""
    content = body.content

    category = body.category
    importance = body.importance
    source = body.source
    summary = body.summary or content[:100]
    metadata = body.metadata
    if _is_noise_memory_payload(content=content, summary=summary, source=source, metadata=metadata):
        return {"stored": False, "skipped": True, "reason": "test_or_noise_payload"}

    try:
        embedding = await generate_embedding(content)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Embedding generation failed: {e}")

    memory = SemanticMemory(
        content=content,
        summary=summary,
        category=category,
        embedding=embedding,
        importance=importance,
        source=source,
        metadata_json={"original_length": len(content), **(metadata or {})},
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    return {"id": str(memory.id), "stored": True}


@router.get("/memories/search")
async def search_memories(
    query: str,
    limit: int = 5,
    category: str = None,
    min_importance: float = 0.0,
    db: AsyncSession = Depends(get_db),
):
    """Search memories by semantic similarity using pgvector cosine distance."""
    try:
        query_embedding = await generate_embedding(query)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Embedding generation failed: {e}")

    distance_col = SemanticMemory.embedding.cosine_distance(query_embedding).label("distance")
    stmt = select(SemanticMemory, distance_col).order_by("distance").limit(limit)

    if category:
        stmt = stmt.where(SemanticMemory.category == category)
    if min_importance > 0:
        stmt = stmt.where(SemanticMemory.importance >= min_importance)

    result = await db.execute(stmt)
    memories = []
    for mem, dist in result.all():
        mem.accessed_at = func.now()
        mem.access_count += 1
        d = mem.to_dict()
        d["similarity"] = round(1 - dist, 4)
        memories.append(d)
    await db.commit()
    return {"memories": memories, "query": query}


@router.post("/memories/search-by-vector")
async def search_memories_by_vector(
    body: SearchByVector,
    db: AsyncSession = Depends(get_db),
):
    """Search memories by a pre-computed embedding vector (pgvector cosine distance).

    Used by the EmbeddingSentimentClassifier when it already has an embedding
    and wants to skip the redundant server-side embedding generation.
    """
    embedding = body.embedding

    category = body.category
    limit = body.limit
    min_importance = body.min_importance

    distance_col = SemanticMemory.embedding.cosine_distance(embedding).label("distance")
    stmt = select(SemanticMemory, distance_col).order_by("distance").limit(limit)

    if category:
        stmt = stmt.where(SemanticMemory.category == category)
    if min_importance > 0:
        stmt = stmt.where(SemanticMemory.importance >= min_importance)

    result = await db.execute(stmt)
    memories = []
    for mem, dist in result.all():
        d = mem.to_dict()
        d["similarity"] = 0.0 if (dist is None or math.isnan(dist)) else round(1 - dist, 4)
        memories.append(d)

    return {"memories": memories, "count": len(memories)}


@router.post("/memories/summarize-session")
async def summarize_session(
    body: SummarizeSession,
    db: AsyncSession = Depends(get_db),
):
    """Summarize recent activity into an episodic semantic memory (S5-03)."""
    hours_back = body.hours_back

    from db.models import ActivityLog
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)

    stmt = (
        select(ActivityLog)
        .where(ActivityLog.created_at >= cutoff)
        .order_by(ActivityLog.created_at.desc())
        .limit(100)
    )
    result = await db.execute(stmt)
    activities = [
        item
        for item in result.scalars().all()
        if not _is_noise_activity_for_summary(item.action, item.skill, item.details if isinstance(item.details, dict) else {})
    ]

    if not activities:
        return {"summary": "No recent activities to summarize.", "decisions": [], "stored": False}

    activity_text = "\n".join(
        f"- [{a.action}] {a.skill or 'system'}: {json_lib.dumps(a.details) if a.details else ''}"
        for a in activities[:50]
    )

    # Build summary via LLM
    import httpx
    prompt = (
        "Summarize this work session in 2-3 sentences. Extract:\n"
        "1. What was the main task?\n2. What was decided?\n"
        "3. What was the emotional tone? (frustrated/satisfied/neutral)\n"
        "4. Any unresolved issues?\n\n"
        f"Activities:\n{activity_text}\n\n"
        'Format: JSON with keys: summary, decisions (list), tone, unresolved (list)'
    )
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{LITELLM_URL}/v1/chat/completions",
                json={
                    "model": "kimi",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 500,
                    "temperature": 0.3,
                },
                headers={"Authorization": f"Bearer {LITELLM_KEY}"},
                timeout=60,
            )
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"]
            # Try to parse JSON from response
            import re
            json_match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
            if json_match:
                parsed = json_lib.loads(json_match.group())
            else:
                parsed = {"summary": raw.strip(), "decisions": [], "tone": "neutral", "unresolved": []}
    except Exception as e:
        parsed = {"summary": f"Session with {len(activities)} activities (auto-summary failed: {e})",
                  "decisions": [], "tone": "neutral", "unresolved": []}

    summary_text = parsed.get("summary", "No summary available")
    decisions = parsed.get("decisions", [])

    # Store episodic summary as semantic memory
    stored_ids = []
    try:
        emb = await generate_embedding(summary_text)
        mem = SemanticMemory(
            content=summary_text,
            summary=summary_text[:100],
            category="episodic",
            embedding=emb,
            importance=0.7,
            source="conversation_summary",
            metadata_json={"hours_back": hours_back, "activity_count": len(activities), "tone": parsed.get("tone")},
        )
        db.add(mem)
        await db.flush()
        stored_ids.append(str(mem.id))
    except Exception as e:
        logger.error("Failed to store conversation summary: %s", e)

    for decision in decisions:
        if isinstance(decision, str) and decision.strip():
            try:
                emb = await generate_embedding(decision)
                dmem = SemanticMemory(
                    content=decision,
                    summary=decision[:100],
                    category="decision",
                    embedding=emb,
                    importance=0.8,
                    source="conversation_summary",
                )
                db.add(dmem)
                await db.flush()
                stored_ids.append(str(dmem.id))
            except Exception as e:
                logger.error("Failed to store decision memory: %s", e)

    await db.commit()
    return {"summary": summary_text, "decisions": decisions, "stored": bool(stored_ids), "ids": stored_ids}


# ===========================================================================
# Key-value memory by key (MUST be after /memories/search to avoid collision)
# ===========================================================================


@router.get("/memories/{key}")
async def get_memory_by_key(key: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Memory).where(Memory.key == key))
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory.to_dict()


@router.delete("/memories/{key}")
async def delete_memory(key: str, db: AsyncSession = Depends(get_db)):
    await db.execute(delete(Memory).where(Memory.key == key))
    await db.commit()
    return {"deleted": True, "key": key}


@router.patch("/memories/{key}")
async def update_memory(key: str, body: UpdateMemory, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Memory).where(Memory.key == key))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Memory not found")
    updates = body.model_dump(exclude_unset=True)
    for k, value in updates.items():
        setattr(row, k, value)
    await db.commit()
    await db.refresh(row)
    return row.to_dict()
