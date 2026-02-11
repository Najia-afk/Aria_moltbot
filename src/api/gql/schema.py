"""
Root Strawberry GraphQL schema — wired to FastAPI via GraphQLRouter.
"""

from typing import Optional

import strawberry
from strawberry.fastapi import GraphQLRouter

from .resolvers import (
    resolve_activities,
    resolve_goals,
    resolve_knowledge_entities,
    resolve_knowledge_relations,
    resolve_memories,
    resolve_memory,
    resolve_sessions,
    resolve_stats,
    resolve_thoughts,
    resolve_update_goal,
    resolve_upsert_memory,
)
from .types import (
    ActivityType,
    GoalType,
    GoalUpdateInput,
    KnowledgeEntityType,
    KnowledgeRelationType,
    MemoryInput,
    MemoryType,
    SessionType,
    StatsType,
    ThoughtType,
)


@strawberry.type
class Query:
    @strawberry.field
    async def activities(
        self, limit: int = 25, offset: int = 0, action: Optional[str] = None,
    ) -> list[ActivityType]:
        return await resolve_activities(limit=limit, offset=offset, action=action)

    @strawberry.field
    async def thoughts(
        self, limit: int = 20, offset: int = 0, category: Optional[str] = None,
    ) -> list[ThoughtType]:
        return await resolve_thoughts(limit=limit, offset=offset, category=category)

    @strawberry.field
    async def memories(
        self, limit: int = 20, offset: int = 0, category: Optional[str] = None,
    ) -> list[MemoryType]:
        return await resolve_memories(limit=limit, offset=offset, category=category)

    @strawberry.field
    async def memory(self, key: str) -> Optional[MemoryType]:
        return await resolve_memory(key=key)

    @strawberry.field
    async def goals(
        self, limit: int = 25, offset: int = 0, status: Optional[str] = None,
    ) -> list[GoalType]:
        return await resolve_goals(limit=limit, offset=offset, status=status)

    @strawberry.field
    async def knowledge_entities(
        self, limit: int = 25, offset: int = 0, entity_type: Optional[str] = None,
    ) -> list[KnowledgeEntityType]:
        return await resolve_knowledge_entities(limit=limit, offset=offset, entity_type=entity_type)

    @strawberry.field
    async def knowledge_relations(self, limit: int = 25, offset: int = 0) -> list[KnowledgeRelationType]:
        return await resolve_knowledge_relations(limit=limit, offset=offset)

    @strawberry.field
    async def sessions(
        self, limit: int = 25, offset: int = 0, status: Optional[str] = None,
    ) -> list[SessionType]:
        return await resolve_sessions(limit=limit, offset=offset, status=status)

    @strawberry.field
    async def stats(self) -> StatsType:
        return await resolve_stats()


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def upsert_memory(self, input: MemoryInput) -> MemoryType:
        return await resolve_upsert_memory(input=input)

    @strawberry.mutation
    async def update_goal(self, goal_id: str, input: GoalUpdateInput) -> GoalType:
        return await resolve_update_goal(goal_id=goal_id, input=input)


schema = strawberry.Schema(query=Query, mutation=Mutation)
graphql_app = GraphQLRouter(schema)
