"""
GraphQL resolvers — read/write operations for key Aria data types.
"""

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import aliased

from db.models import (
    ActivityLog,
    AgentSession,
    Goal,
    KnowledgeEntity,
    KnowledgeRelation,
    Memory,
    ModelUsage,
    SkillGraphEntity,
    SkillGraphRelation,
    Thought,
)
from db.session import AsyncSessionLocal
from .types import (
    ActivityType,
    GoalType,
    GoalUpdateInput,
    GraphTraversalEdgeType,
    GraphTraversalNodeType,
    GraphTraversalResult,
    KnowledgeEntityType,
    KnowledgeRelationType,
    MemoryInput,
    MemoryType,
    ModelUsageType,
    SessionType,
    SkillCandidate,
    SkillForTaskResult,
    StatsType,
    ThoughtType,
)


async def _get_session():
    async with AsyncSessionLocal() as session:
        yield session


# ── Query resolvers ──────────────────────────────────────────────────────────

async def resolve_activities(limit: int = 25, offset: int = 0, action: str | None = None) -> list[ActivityType]:
    async with AsyncSessionLocal() as db:
        stmt = select(ActivityLog).order_by(ActivityLog.created_at.desc()).offset(offset).limit(limit)
        if action:
            stmt = stmt.where(ActivityLog.action == action)
        result = await db.execute(stmt)
        return [
            ActivityType(
                id=str(a.id), action=a.action, skill=a.skill,
                details=a.details, success=a.success,
                error_message=a.error_message,
                created_at=a.created_at.isoformat() if a.created_at else None,
            )
            for a in result.scalars().all()
        ]


async def resolve_thoughts(limit: int = 20, offset: int = 0, category: str | None = None) -> list[ThoughtType]:
    async with AsyncSessionLocal() as db:
        stmt = select(Thought).order_by(Thought.created_at.desc()).offset(offset).limit(limit)
        if category:
            stmt = stmt.where(Thought.category == category)
        result = await db.execute(stmt)
        return [
            ThoughtType(
                id=str(t.id), category=t.category, content=t.content,
                metadata=t.metadata_json,
                created_at=t.created_at.isoformat() if t.created_at else None,
            )
            for t in result.scalars().all()
        ]


async def resolve_memories(limit: int = 20, offset: int = 0, category: str | None = None) -> list[MemoryType]:
    async with AsyncSessionLocal() as db:
        stmt = select(Memory).order_by(Memory.updated_at.desc()).offset(offset).limit(limit)
        if category:
            stmt = stmt.where(Memory.category == category)
        result = await db.execute(stmt)
        return [
            MemoryType(
                id=str(m.id), key=m.key, value=m.value, category=m.category,
                created_at=m.created_at.isoformat() if m.created_at else None,
                updated_at=m.updated_at.isoformat() if m.updated_at else None,
            )
            for m in result.scalars().all()
        ]


async def resolve_memory(key: str) -> MemoryType | None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Memory).where(Memory.key == key))
        m = result.scalar_one_or_none()
        if not m:
            return None
        return MemoryType(
            id=str(m.id), key=m.key, value=m.value, category=m.category,
            created_at=m.created_at.isoformat() if m.created_at else None,
            updated_at=m.updated_at.isoformat() if m.updated_at else None,
        )


async def resolve_goals(limit: int = 25, offset: int = 0, status: str | None = None) -> list[GoalType]:
    async with AsyncSessionLocal() as db:
        stmt = select(Goal).order_by(Goal.priority.asc(), Goal.created_at.desc()).offset(offset).limit(limit)
        if status:
            stmt = stmt.where(Goal.status == status)
        result = await db.execute(stmt)
        return [
            GoalType(
                id=str(g.id), goal_id=g.goal_id, title=g.title,
                description=g.description, status=g.status,
                priority=g.priority, progress=float(g.progress or 0),
                due_date=g.due_date.isoformat() if g.due_date else None,
                created_at=g.created_at.isoformat() if g.created_at else None,
                completed_at=g.completed_at.isoformat() if g.completed_at else None,
                sprint=g.sprint, board_column=g.board_column,
                position=g.position or 0, assigned_to=g.assigned_to,
                tags=g.tags,
                updated_at=g.updated_at.isoformat() if g.updated_at else None,
            )
            for g in result.scalars().all()
        ]


async def resolve_knowledge_entities(
    limit: int = 25, offset: int = 0, entity_type: str | None = None,
) -> list[KnowledgeEntityType]:
    async with AsyncSessionLocal() as db:
        stmt = select(KnowledgeEntity).order_by(KnowledgeEntity.created_at.desc()).offset(offset).limit(limit)
        if entity_type:
            stmt = stmt.where(KnowledgeEntity.type == entity_type)
        result = await db.execute(stmt)
        return [
            KnowledgeEntityType(
                id=str(e.id), name=e.name, entity_type=e.type,
                properties=e.properties,
                created_at=e.created_at.isoformat() if e.created_at else None,
                updated_at=e.updated_at.isoformat() if e.updated_at else None,
            )
            for e in result.scalars().all()
        ]


async def resolve_knowledge_relations(limit: int = 25, offset: int = 0) -> list[KnowledgeRelationType]:
    async with AsyncSessionLocal() as db:
        E1 = aliased(KnowledgeEntity)
        E2 = aliased(KnowledgeEntity)
        result = await db.execute(
            select(
                KnowledgeRelation,
                E1.name.label("from_name"),
                E2.name.label("to_name"),
            )
            .join(E1, KnowledgeRelation.from_entity == E1.id)
            .join(E2, KnowledgeRelation.to_entity == E2.id)
            .order_by(KnowledgeRelation.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return [
            KnowledgeRelationType(
                id=str(r[0].id),
                from_entity=str(r[0].from_entity),
                to_entity=str(r[0].to_entity),
                relation_type=r[0].relation_type,
                properties=r[0].properties,
                from_name=r[1], to_name=r[2],
                created_at=r[0].created_at.isoformat() if r[0].created_at else None,
            )
            for r in result.all()
        ]


async def resolve_sessions(limit: int = 25, offset: int = 0, status: str | None = None) -> list[SessionType]:
    async with AsyncSessionLocal() as db:
        stmt = select(AgentSession).order_by(AgentSession.started_at.desc()).offset(offset).limit(limit)
        if status:
            stmt = stmt.where(AgentSession.status == status)
        result = await db.execute(stmt)
        return [
            SessionType(
                id=str(s.id), agent_id=s.agent_id, session_type=s.session_type,
                started_at=s.started_at.isoformat() if s.started_at else None,
                ended_at=s.ended_at.isoformat() if s.ended_at else None,
                messages_count=s.messages_count, tokens_used=s.tokens_used,
                cost_usd=float(s.cost_usd) if s.cost_usd else 0,
                status=s.status,
            )
            for s in result.scalars().all()
        ]


async def resolve_stats() -> StatsType:
    async with AsyncSessionLocal() as db:
        act = (await db.execute(select(func.count(ActivityLog.id)))).scalar() or 0
        th = (await db.execute(select(func.count(Thought.id)))).scalar() or 0
        mem = (await db.execute(select(func.count(Memory.id)))).scalar() or 0
        gl = (await db.execute(select(func.count(Goal.id)))).scalar() or 0
        last = (await db.execute(select(func.max(ActivityLog.created_at)))).scalar()
        return StatsType(
            activities_count=act, thoughts_count=th,
            memories_count=mem, goals_count=gl,
            last_activity=last.isoformat() if last else None,
        )


# ── Mutation resolvers ───────────────────────────────────────────────────────

async def resolve_upsert_memory(input: MemoryInput) -> MemoryType:
    async with AsyncSessionLocal() as db:
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy import text as sa_text
        stmt = pg_insert(Memory).values(
            key=input.key,
            value=input.value,
            category=input.category,
        ).on_conflict_do_update(
            index_elements=["key"],
            set_={"value": input.value, "category": input.category, "updated_at": sa_text("NOW()")},
        ).returning(Memory)
        result = await db.execute(stmt)
        m = result.scalar_one()
        await db.commit()
        return MemoryType(
            id=str(m.id), key=m.key, value=m.value, category=m.category,
            created_at=m.created_at.isoformat() if m.created_at else None,
            updated_at=m.updated_at.isoformat() if m.updated_at else None,
        )


async def resolve_update_goal(goal_id: str, input: GoalUpdateInput) -> GoalType:
    async with AsyncSessionLocal() as db:
        values: dict = {}
        if input.status is not None:
            values["status"] = input.status
            if input.status == "completed":
                from sqlalchemy import text as sa_text
                values["completed_at"] = sa_text("NOW()")
        if input.progress is not None:
            values["progress"] = input.progress
        if input.priority is not None:
            values["priority"] = input.priority
        if values:
            try:
                uid = uuid.UUID(goal_id)
                await db.execute(update(Goal).where(Goal.id == uid).values(**values))
            except ValueError:
                await db.execute(update(Goal).where(Goal.goal_id == goal_id).values(**values))
            await db.commit()
        # Fetch updated
        try:
            uid = uuid.UUID(goal_id)
            g = (await db.execute(select(Goal).where(Goal.id == uid))).scalar_one()
        except ValueError:
            g = (await db.execute(select(Goal).where(Goal.goal_id == goal_id))).scalar_one()
        return GoalType(
            id=str(g.id), goal_id=g.goal_id, title=g.title,
            description=g.description, status=g.status,
            priority=g.priority, progress=float(g.progress or 0),
            due_date=g.due_date.isoformat() if g.due_date else None,
            created_at=g.created_at.isoformat() if g.created_at else None,
            completed_at=g.completed_at.isoformat() if g.completed_at else None,
            sprint=g.sprint, board_column=g.board_column,
            position=g.position or 0, assigned_to=g.assigned_to,
            tags=g.tags,
            updated_at=g.updated_at.isoformat() if g.updated_at else None,
        )


# ── S4-08: Graph traversal + skill-for-task resolvers ────────────────────────

async def resolve_graph_traverse(
    start: str,
    relation_type: str | None = None,
    max_depth: int = 3,
    direction: str = "outgoing",
) -> GraphTraversalResult:
    from collections import deque
    async with AsyncSessionLocal() as db:
        start_entity = None
        try:
            start_uuid = uuid.UUID(start)
            result = await db.execute(select(SkillGraphEntity).where(SkillGraphEntity.id == start_uuid))
            start_entity = result.scalar_one_or_none()
        except ValueError:
            pass
        if not start_entity:
            result = await db.execute(select(SkillGraphEntity).where(SkillGraphEntity.name == start))
            start_entity = result.scalar_one_or_none()
        if not start_entity:
            return GraphTraversalResult(nodes=[], edges=[], total_nodes=0, total_edges=0, traversal_depth=max_depth)

        visited: set[str] = set()
        queue: deque[tuple] = deque()
        queue.append((start_entity.id, 0))
        visited.add(str(start_entity.id))

        nodes = [GraphTraversalNodeType(
            id=str(start_entity.id), name=start_entity.name,
            entity_type=start_entity.type, properties=start_entity.properties,
        )]
        edges_list: list[GraphTraversalEdgeType] = []

        while queue:
            current_id, depth = queue.popleft()
            if depth >= max_depth:
                continue
            stmts = []
            if direction in ("outgoing", "both"):
                stmt = select(SkillGraphRelation).where(SkillGraphRelation.from_entity == current_id)
                if relation_type:
                    stmt = stmt.where(SkillGraphRelation.relation_type == relation_type)
                stmts.append(("outgoing", stmt))
            if direction in ("incoming", "both"):
                stmt = select(SkillGraphRelation).where(SkillGraphRelation.to_entity == current_id)
                if relation_type:
                    stmt = stmt.where(SkillGraphRelation.relation_type == relation_type)
                stmts.append(("incoming", stmt))

            for dir_label, s in stmts:
                result = await db.execute(s)
                for rel in result.scalars().all():
                    edges_list.append(GraphTraversalEdgeType(
                        id=str(rel.id), from_entity=str(rel.from_entity),
                        to_entity=str(rel.to_entity), relation_type=rel.relation_type,
                        properties=rel.properties,
                    ))
                    next_id = rel.to_entity if dir_label == "outgoing" else rel.from_entity
                    if str(next_id) not in visited:
                        visited.add(str(next_id))
                        nr = await db.execute(select(SkillGraphEntity).where(SkillGraphEntity.id == next_id))
                        node = nr.scalar_one_or_none()
                        if node:
                            nodes.append(GraphTraversalNodeType(
                                id=str(node.id), name=node.name,
                                entity_type=node.type, properties=node.properties,
                            ))
                            queue.append((next_id, depth + 1))

        return GraphTraversalResult(
            nodes=nodes, edges=edges_list,
            total_nodes=len(nodes), total_edges=len(edges_list),
            traversal_depth=max_depth,
        )


async def resolve_skill_for_task(task: str, limit: int = 5) -> SkillForTaskResult:
    from sqlalchemy import or_
    async with AsyncSessionLocal() as db:
        pattern = f"%{task}%"
        skill_stmt = select(SkillGraphEntity).where(
            SkillGraphEntity.type == "skill",
            or_(
                SkillGraphEntity.name.ilike(pattern),
                SkillGraphEntity.properties["description"].astext.ilike(pattern),
            ),
        ).limit(limit)
        skill_result = await db.execute(skill_stmt)
        skill_matches = skill_result.scalars().all()

        tool_stmt = select(SkillGraphEntity).where(
            SkillGraphEntity.type == "tool",
            or_(
                SkillGraphEntity.name.ilike(pattern),
                SkillGraphEntity.properties["description"].astext.ilike(pattern),
            ),
        ).limit(20)
        tool_result = await db.execute(tool_stmt)
        tool_matches = tool_result.scalars().all()

        tool_skill_ids: set[str] = set()
        for tool in tool_matches:
            rel_result = await db.execute(
                select(SkillGraphRelation).where(
                    SkillGraphRelation.to_entity == tool.id,
                    SkillGraphRelation.relation_type == "provides",
                )
            )
            for rel in rel_result.scalars().all():
                tool_skill_ids.add(str(rel.from_entity))

        indirect_skills = []
        if tool_skill_ids:
            indirect_result = await db.execute(
                select(SkillGraphEntity).where(
                    SkillGraphEntity.id.in_([uuid.UUID(sid) for sid in tool_skill_ids])
                )
            )
            indirect_skills = indirect_result.scalars().all()

        seen: set[str] = set()
        candidates: list[SkillCandidate] = []
        for sk in skill_matches:
            sid = str(sk.id)
            if sid not in seen:
                seen.add(sid)
                candidates.append(SkillCandidate(
                    id=sid, name=sk.name, entity_type=sk.type,
                    properties=sk.properties, match_type="direct", relevance="high",
                ))
        for sk in indirect_skills:
            sid = str(sk.id)
            if sid not in seen:
                seen.add(sid)
                candidates.append(SkillCandidate(
                    id=sid, name=sk.name, entity_type=sk.type,
                    properties=sk.properties, match_type="via_tool", relevance="medium",
                ))

        return SkillForTaskResult(
            task=task, candidates=candidates[:limit],
            count=len(candidates[:limit]), tools_searched=len(tool_matches),
        )
