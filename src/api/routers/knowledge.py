"""
Knowledge graph endpoints — entities + relations.
"""

import json as json_lib
import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import KnowledgeEntity, KnowledgeRelation
from deps import get_db

router = APIRouter(tags=["Knowledge Graph"])


@router.get("/knowledge-graph")
async def get_knowledge_graph(db: AsyncSession = Depends(get_db)):
    entities = (await db.execute(
        select(KnowledgeEntity).order_by(KnowledgeEntity.created_at.desc())
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
    limit: int = 100,
    type: str = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(KnowledgeEntity).order_by(KnowledgeEntity.created_at.desc()).limit(limit)
    if type:
        stmt = stmt.where(KnowledgeEntity.type == type)
    result = await db.execute(stmt)
    return {"entities": [e.to_dict() for e in result.scalars().all()]}


@router.get("/knowledge-graph/relations")
async def get_knowledge_relations(limit: int = 100, db: AsyncSession = Depends(get_db)):
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
async def create_knowledge_entity(request: Request, db: AsyncSession = Depends(get_db)):
    data = await request.json()
    entity = KnowledgeEntity(
        id=uuid.uuid4(),
        name=data.get("name"),
        type=data.get("type"),
        properties=data.get("properties", {}),
    )
    db.add(entity)
    await db.commit()
    return {"id": str(entity.id), "created": True}


@router.post("/knowledge-graph/relations")
async def create_knowledge_relation(request: Request, db: AsyncSession = Depends(get_db)):
    data = await request.json()
    relation = KnowledgeRelation(
        id=uuid.uuid4(),
        from_entity=uuid.UUID(data.get("from_entity")),
        to_entity=uuid.UUID(data.get("to_entity")),
        relation_type=data.get("relation_type"),
        properties=data.get("properties", {}),
    )
    db.add(relation)
    await db.commit()
    return {"id": str(relation.id), "created": True}
