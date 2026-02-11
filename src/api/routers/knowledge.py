"""
Knowledge graph endpoints — entities, relations, traversal, search, query logging.
"""

import json as json_lib
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from db.models import KnowledgeEntity, KnowledgeRelation, KnowledgeQueryLog
from deps import get_db

router = APIRouter(tags=["Knowledge Graph"])


# ── Pydantic schemas for input validation ─────────────────────────────────────

class EntityCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    type: str = Field(..., min_length=1, max_length=100)
    properties: dict = Field(default_factory=dict)

class RelationCreate(BaseModel):
    from_entity: uuid.UUID
    to_entity: uuid.UUID
    relation_type: str = Field(..., min_length=1, max_length=100)
    properties: dict = Field(default_factory=dict)


# ── S4-05: Query logging helper ──────────────────────────────────────────────

async def _log_query(db: AsyncSession, query_type: str, params: dict, result_count: int, source: str = "api"):
    """Log a knowledge graph query for analytics."""
    try:
        log = KnowledgeQueryLog(
            id=uuid.uuid4(),
            query_type=query_type,
            params=params,
            result_count=result_count,
            source=source,
        )
        db.add(log)
        await db.commit()
    except Exception:
        await db.rollback()  # Restore session to usable state


# ── S4-07: Sync skills endpoint ──────────────────────────────────────────────

@router.post("/knowledge-graph/sync-skills")
async def sync_skills():
    """Trigger skill graph sync (ORM-based, idempotent)."""
    from graph_sync import sync_skill_graph
    try:
        stats = await sync_skill_graph()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Sync failed: {exc}")
    return {"status": "ok", "stats": stats}


@router.get("/knowledge-graph")
async def get_knowledge_graph(
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    entities = (await db.execute(
        select(KnowledgeEntity).order_by(KnowledgeEntity.created_at.desc())
        .limit(limit).offset(offset)
    )).scalars().all()

    # Relations with entity names via subquery / manual join
    from sqlalchemy.orm import aliased
    E1 = aliased(KnowledgeEntity)
    E2 = aliased(KnowledgeEntity)
    relations_result = await db.execute(
        select(
            KnowledgeRelation,
            E1.name.label("from_name"), E1.type.label("from_type"),
            E2.name.label("to_name"), E2.type.label("to_type"),
        )
        .join(E1, KnowledgeRelation.from_entity == E1.id)
        .join(E2, KnowledgeRelation.to_entity == E2.id)
        .order_by(KnowledgeRelation.created_at.desc())
        .limit(limit).offset(offset)
    )
    relation_rows = relations_result.all()

    return {
        "entities": [e.to_dict() for e in entities],
        "relations": [
            {
                **r[0].to_dict(),
                "from_name": r[1], "from_type": r[2],
                "to_name": r[3], "to_type": r[4],
            }
            for r in relation_rows
        ],
        "stats": {
            "entity_count": len(entities),
            "relation_count": len(relation_rows),
        },
    }


@router.get("/knowledge-graph/entities")
async def get_knowledge_entities(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    type: str = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(KnowledgeEntity).order_by(KnowledgeEntity.created_at.desc()).limit(limit).offset(offset)
    if type:
        stmt = stmt.where(KnowledgeEntity.type == type)
    result = await db.execute(stmt)
    return {"entities": [e.to_dict() for e in result.scalars().all()]}


@router.get("/knowledge-graph/relations")
async def get_knowledge_relations(
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy.orm import aliased
    E1 = aliased(KnowledgeEntity)
    E2 = aliased(KnowledgeEntity)
    result = await db.execute(
        select(
            KnowledgeRelation,
            E1.name.label("from_name"), E1.type.label("from_type"),
            E2.name.label("to_name"), E2.type.label("to_type"),
        )
        .join(E1, KnowledgeRelation.from_entity == E1.id)
        .join(E2, KnowledgeRelation.to_entity == E2.id)
        .order_by(KnowledgeRelation.created_at.desc())
        .limit(limit)
    )
    return {
        "relations": [
            {
                **r[0].to_dict(),
                "from_name": r[1], "from_type": r[2],
                "to_name": r[3], "to_type": r[4],
            }
            for r in result.all()
        ]
    }


@router.post("/knowledge-graph/entities")
async def create_knowledge_entity(body: EntityCreate, db: AsyncSession = Depends(get_db)):
    entity = KnowledgeEntity(
        id=uuid.uuid4(),
        name=body.name,
        type=body.type,
        properties=body.properties,
    )
    db.add(entity)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"Entity creation failed: {exc}")
    return {"id": str(entity.id), "created": True}


@router.post("/knowledge-graph/relations")
async def create_knowledge_relation(body: RelationCreate, db: AsyncSession = Depends(get_db)):
    relation = KnowledgeRelation(
        id=uuid.uuid4(),
        from_entity=body.from_entity,
        to_entity=body.to_entity,
        relation_type=body.relation_type,
        properties=body.properties,
    )
    db.add(relation)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"Relation creation failed: {exc}")
    return {"id": str(relation.id), "created": True}


# ── S4-01: Delete auto-generated graph data ──────────────────────────────────

@router.delete("/knowledge-graph/auto-generated")
async def delete_auto_generated(db: AsyncSession = Depends(get_db)):
    """Delete all entities (+ cascaded relations) where properties.auto_generated = true."""
    # Find auto-generated entities
    stmt = select(KnowledgeEntity).where(
        KnowledgeEntity.properties["auto_generated"].as_boolean() == True  # noqa: E712
    )
    result = await db.execute(stmt)
    entities = result.scalars().all()
    count = len(entities)

    if count > 0:
        # Delete relations first (both directions), then entities
        entity_ids = [e.id for e in entities]
        await db.execute(
            delete(KnowledgeRelation).where(
                or_(
                    KnowledgeRelation.from_entity.in_(entity_ids),
                    KnowledgeRelation.to_entity.in_(entity_ids),
                )
            )
        )
        # Also delete relations tagged auto_generated
        await db.execute(
            delete(KnowledgeRelation).where(
                KnowledgeRelation.properties["auto_generated"].as_boolean() == True  # noqa: E712
            )
        )
        await db.execute(
            delete(KnowledgeEntity).where(
                KnowledgeEntity.properties["auto_generated"].as_boolean() == True  # noqa: E712
            )
        )
        await db.commit()

    return {"deleted_entities": count, "status": "ok"}


# ── S4-02: Graph traversal (BFS) ─────────────────────────────────────────────

@router.get("/knowledge-graph/traverse")
async def graph_traverse(
    start: str = Query(..., description="Starting entity ID or name"),
    relation_type: Optional[str] = Query(None, description="Filter by relation type"),
    max_depth: int = Query(3, ge=1, le=10),
    direction: str = Query("outgoing", regex="^(outgoing|incoming|both)$"),
    db: AsyncSession = Depends(get_db),
):
    """BFS traversal from a starting entity."""
    # Resolve start entity by ID or name
    start_entity = None
    try:
        start_uuid = uuid.UUID(start)
        result = await db.execute(select(KnowledgeEntity).where(KnowledgeEntity.id == start_uuid))
        start_entity = result.scalar_one_or_none()
    except ValueError:
        pass
    if not start_entity:
        result = await db.execute(select(KnowledgeEntity).where(KnowledgeEntity.name == start))
        start_entity = result.scalar_one_or_none()
    if not start_entity:
        return {"error": f"Entity not found: {start}", "nodes": [], "edges": []}

    # BFS
    visited: set[str] = set()
    queue: deque[tuple[uuid.UUID, int]] = deque()
    queue.append((start_entity.id, 0))
    visited.add(str(start_entity.id))

    nodes: list[dict] = [start_entity.to_dict()]
    edges: list[dict] = []

    while queue:
        current_id, depth = queue.popleft()
        if depth >= max_depth:
            continue

        # Build relation query based on direction
        stmts = []
        if direction in ("outgoing", "both"):
            stmt = select(KnowledgeRelation).where(KnowledgeRelation.from_entity == current_id)
            if relation_type:
                stmt = stmt.where(KnowledgeRelation.relation_type == relation_type)
            stmts.append(("outgoing", stmt))
        if direction in ("incoming", "both"):
            stmt = select(KnowledgeRelation).where(KnowledgeRelation.to_entity == current_id)
            if relation_type:
                stmt = stmt.where(KnowledgeRelation.relation_type == relation_type)
            stmts.append(("incoming", stmt))

        for dir_label, stmt in stmts:
            result = await db.execute(stmt)
            for rel in result.scalars().all():
                edge_data = rel.to_dict()
                edges.append(edge_data)
                next_id = rel.to_entity if dir_label == "outgoing" else rel.from_entity
                next_id_str = str(next_id)
                if next_id_str not in visited:
                    visited.add(next_id_str)
                    # Fetch the node
                    node_result = await db.execute(select(KnowledgeEntity).where(KnowledgeEntity.id == next_id))
                    node = node_result.scalar_one_or_none()
                    if node:
                        nodes.append(node.to_dict())
                        queue.append((next_id, depth + 1))

    await _log_query(db, "traverse", {"start": start, "relation_type": relation_type, "max_depth": max_depth, "direction": direction}, len(nodes))
    return {"nodes": nodes, "edges": edges, "traversal_depth": max_depth, "total_nodes": len(nodes), "total_edges": len(edges)}


# ── S4-02: Graph search (ILIKE) ──────────────────────────────────────────────

@router.get("/knowledge-graph/search")
async def graph_search(
    q: str = Query(..., min_length=1, description="Search query"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    limit: int = Query(25, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """ILIKE text search for entities matching a query string."""
    pattern = f"%{q}%"
    stmt = select(KnowledgeEntity).where(
        or_(
            KnowledgeEntity.name.ilike(pattern),
            KnowledgeEntity.properties["description"].astext.ilike(pattern),
        )
    )
    if entity_type:
        stmt = stmt.where(KnowledgeEntity.type == entity_type)
    stmt = stmt.order_by(KnowledgeEntity.name).limit(limit)

    result = await db.execute(stmt)
    entities = [e.to_dict() for e in result.scalars().all()]

    await _log_query(db, "search", {"q": q, "entity_type": entity_type}, len(entities))
    return {"results": entities, "query": q, "count": len(entities)}


# ── S4-02: Skill-for-task discovery ──────────────────────────────────────────

@router.get("/knowledge-graph/skill-for-task")
async def find_skill_for_task(
    task: str = Query(..., min_length=1, description="Task description"),
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """Find the best skill for a given task by matching tool/skill descriptions."""
    pattern = f"%{task}%"

    # Search skills by name/description
    skill_stmt = select(KnowledgeEntity).where(
        KnowledgeEntity.type == "skill",
        or_(
            KnowledgeEntity.name.ilike(pattern),
            KnowledgeEntity.properties["description"].astext.ilike(pattern),
        ),
    ).limit(limit)
    skill_result = await db.execute(skill_stmt)
    skill_matches = skill_result.scalars().all()

    # Search tools by name/description, then trace back to skill
    tool_stmt = select(KnowledgeEntity).where(
        KnowledgeEntity.type == "tool",
        or_(
            KnowledgeEntity.name.ilike(pattern),
            KnowledgeEntity.properties["description"].astext.ilike(pattern),
        ),
    ).limit(20)
    tool_result = await db.execute(tool_stmt)
    tool_matches = tool_result.scalars().all()

    # For each matching tool, find the parent skill via 'provides' relation
    tool_skill_ids: set[str] = set()
    for tool in tool_matches:
        rel_result = await db.execute(
            select(KnowledgeRelation).where(
                KnowledgeRelation.to_entity == tool.id,
                KnowledgeRelation.relation_type == "provides",
            )
        )
        for rel in rel_result.scalars().all():
            tool_skill_ids.add(str(rel.from_entity))

    # Fetch those parent skills
    indirect_skills = []
    if tool_skill_ids:
        indirect_result = await db.execute(
            select(KnowledgeEntity).where(
                KnowledgeEntity.id.in_([uuid.UUID(sid) for sid in tool_skill_ids])
            )
        )
        indirect_skills = indirect_result.scalars().all()

    # Merge and deduplicate
    seen: set[str] = set()
    candidates: list[dict] = []
    for skill in skill_matches:
        sid = str(skill.id)
        if sid not in seen:
            seen.add(sid)
            candidates.append({
                **skill.to_dict(),
                "match_type": "direct",
                "relevance": "high",
            })
    for skill in indirect_skills:
        sid = str(skill.id)
        if sid not in seen:
            seen.add(sid)
            candidates.append({
                **skill.to_dict(),
                "match_type": "via_tool",
                "relevance": "medium",
            })

    result_data = {
        "task": task,
        "candidates": candidates[:limit],
        "count": len(candidates[:limit]),
        "tools_searched": len(tool_matches),
    }
    await _log_query(db, "skill_for_task", {"task": task}, len(candidates[:limit]))
    return result_data


# ── S4-05: Query log endpoint ────────────────────────────────────────────────

@router.get("/knowledge-graph/query-log")
async def get_query_log(
    limit: int = Query(50, ge=1, le=200),
    query_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get recent knowledge graph query log entries."""
    stmt = select(KnowledgeQueryLog).order_by(KnowledgeQueryLog.created_at.desc()).limit(limit)
    if query_type:
        stmt = stmt.where(KnowledgeQueryLog.query_type == query_type)
    result = await db.execute(stmt)
    logs = [log.to_dict() for log in result.scalars().all()]
    return {"logs": logs, "count": len(logs)}

