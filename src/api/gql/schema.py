"""
Root Strawberry GraphQL schema — wired to FastAPI via GraphQLRouter.
S-29: Expanded mutations, cursor-based pagination, error handling.
"""


import strawberry
from strawberry.fastapi import GraphQLRouter

from .resolvers import (
    resolve_activities,
    resolve_activities_connection,
    resolve_create_activity,
    resolve_create_goal,
    resolve_create_session,
    resolve_create_thought,
    resolve_delete_activity,
    resolve_delete_goal,
    resolve_delete_memory,
    resolve_delete_session,
    resolve_delete_thought,
    resolve_goals,
    resolve_goals_connection,
    resolve_graph_traverse,
    resolve_knowledge_entities,
    resolve_knowledge_relations,
    resolve_memories,
    resolve_memories_connection,
    resolve_memory,
    resolve_sessions,
    resolve_sessions_connection,
    resolve_skill_for_task,
    resolve_stats,
    resolve_thoughts,
    resolve_thoughts_connection,
    resolve_update_goal,
    resolve_upsert_memory,
)
from .types import (
    ActivityConnection,
    ActivityInput,
    ActivityType,
    DeleteResult,
    GoalConnection,
    GoalInput,
    GoalType,
    GoalUpdateInput,
    GraphTraversalResult,
    KnowledgeEntityType,
    KnowledgeRelationType,
    MemoryConnection,
    MemoryInput,
    MemoryType,
    SessionConnection,
    SessionInput,
    SessionType,
    SkillForTaskResult,
    StatsType,
    ThoughtConnection,
    ThoughtInput,
    ThoughtType,
)


@strawberry.type
class Query:
    # ── Offset-based queries (backward compat) ───────────────────────────
    @strawberry.field
    async def activities(
        self, limit: int = 25, offset: int = 0, action: str | None = None,
    ) -> list[ActivityType]:
        return await resolve_activities(limit=limit, offset=offset, action=action)

    @strawberry.field
    async def thoughts(
        self, limit: int = 20, offset: int = 0, category: str | None = None,
    ) -> list[ThoughtType]:
        return await resolve_thoughts(limit=limit, offset=offset, category=category)

    @strawberry.field
    async def memories(
        self, limit: int = 20, offset: int = 0, category: str | None = None,
    ) -> list[MemoryType]:
        return await resolve_memories(limit=limit, offset=offset, category=category)

    @strawberry.field
    async def memory(self, key: str) -> MemoryType | None:
        return await resolve_memory(key=key)

    @strawberry.field
    async def goals(
        self, limit: int = 25, offset: int = 0, status: str | None = None,
    ) -> list[GoalType]:
        return await resolve_goals(limit=limit, offset=offset, status=status)

    @strawberry.field
    async def knowledge_entities(
        self, limit: int = 25, offset: int = 0, entity_type: str | None = None,
    ) -> list[KnowledgeEntityType]:
        return await resolve_knowledge_entities(limit=limit, offset=offset, entity_type=entity_type)

    @strawberry.field
    async def knowledge_relations(self, limit: int = 25, offset: int = 0) -> list[KnowledgeRelationType]:
        return await resolve_knowledge_relations(limit=limit, offset=offset)

    @strawberry.field
    async def sessions(
        self, limit: int = 25, offset: int = 0, status: str | None = None,
    ) -> list[SessionType]:
        return await resolve_sessions(limit=limit, offset=offset, status=status)

    @strawberry.field
    async def stats(self) -> StatsType:
        return await resolve_stats()

    # S4-08: Knowledge graph traversal + skill discovery
    @strawberry.field
    async def graph_traverse(
        self, start: str, relation_type: str | None = None,
        max_depth: int = 3, direction: str = "outgoing",
    ) -> GraphTraversalResult:
        return await resolve_graph_traverse(
            start=start, relation_type=relation_type,
            max_depth=max_depth, direction=direction,
        )

    @strawberry.field
    async def skill_for_task(
        self, task: str, limit: int = 5,
    ) -> SkillForTaskResult:
        return await resolve_skill_for_task(task=task, limit=limit)

    # ── Cursor-based pagination queries (S-29) ───────────────────────────
    @strawberry.field
    async def activities_connection(
        self, first: int = 25, after: str | None = None, action: str | None = None,
    ) -> ActivityConnection:
        return await resolve_activities_connection(first=first, after=after, action=action)

    @strawberry.field
    async def thoughts_connection(
        self, first: int = 20, after: str | None = None, category: str | None = None,
    ) -> ThoughtConnection:
        return await resolve_thoughts_connection(first=first, after=after, category=category)

    @strawberry.field
    async def memories_connection(
        self, first: int = 20, after: str | None = None, category: str | None = None,
    ) -> MemoryConnection:
        return await resolve_memories_connection(first=first, after=after, category=category)

    @strawberry.field
    async def goals_connection(
        self, first: int = 25, after: str | None = None, status: str | None = None,
    ) -> GoalConnection:
        return await resolve_goals_connection(first=first, after=after, status=status)

    @strawberry.field
    async def sessions_connection(
        self, first: int = 25, after: str | None = None, status: str | None = None,
    ) -> SessionConnection:
        return await resolve_sessions_connection(first=first, after=after, status=status)


@strawberry.type
class Mutation:
    # ── Existing mutations ───────────────────────────────────────────────
    @strawberry.mutation
    async def upsert_memory(self, input: MemoryInput) -> MemoryType:
        return await resolve_upsert_memory(input=input)

    @strawberry.mutation
    async def update_goal(self, goal_id: str, input: GoalUpdateInput) -> GoalType:
        return await resolve_update_goal(goal_id=goal_id, input=input)

    # ── New mutations (S-29) ─────────────────────────────────────────────
    @strawberry.mutation
    async def delete_memory(self, key: str) -> DeleteResult:
        return await resolve_delete_memory(key=key)

    @strawberry.mutation
    async def create_goal(self, input: GoalInput) -> GoalType:
        return await resolve_create_goal(input=input)

    @strawberry.mutation
    async def delete_goal(self, goal_id: str) -> DeleteResult:
        return await resolve_delete_goal(goal_id=goal_id)

    @strawberry.mutation
    async def create_activity(self, input: ActivityInput) -> ActivityType:
        return await resolve_create_activity(input=input)

    @strawberry.mutation
    async def delete_activity(self, activity_id: str) -> DeleteResult:
        return await resolve_delete_activity(activity_id=activity_id)

    @strawberry.mutation
    async def create_thought(self, input: ThoughtInput) -> ThoughtType:
        return await resolve_create_thought(input=input)

    @strawberry.mutation
    async def delete_thought(self, thought_id: str) -> DeleteResult:
        return await resolve_delete_thought(thought_id=thought_id)

    @strawberry.mutation
    async def create_session(self, input: SessionInput) -> SessionType:
        return await resolve_create_session(input=input)

    @strawberry.mutation
    async def delete_session(self, session_id: str) -> DeleteResult:
        return await resolve_delete_session(session_id=session_id)


schema = strawberry.Schema(query=Query, mutation=Mutation)
graphql_app = GraphQLRouter(schema)
