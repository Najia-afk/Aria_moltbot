"""
Strawberry GraphQL types for Aria data models.
"""

import strawberry
from strawberry.scalars import JSON


@strawberry.type
class ActivityType:
    id: str
    action: str
    skill: str | None
    details: JSON | None
    success: bool
    error_message: str | None
    created_at: str | None


@strawberry.type
class ThoughtType:
    id: str
    category: str
    content: str
    metadata: JSON | None
    created_at: str | None


@strawberry.type
class MemoryType:
    id: str
    key: str
    value: JSON | None
    category: str
    created_at: str | None
    updated_at: str | None


@strawberry.type
class GoalType:
    id: str
    goal_id: str
    title: str
    description: str | None
    status: str
    priority: int
    progress: float
    due_date: str | None
    created_at: str | None
    completed_at: str | None
    # Sprint Board fields (S3-08)
    sprint: str | None = None
    board_column: str | None = None
    position: int = 0
    assigned_to: str | None = None
    tags: JSON | None = None
    updated_at: str | None = None


@strawberry.type
class KnowledgeEntityType:
    id: str
    name: str
    entity_type: str
    properties: JSON | None
    created_at: str | None
    updated_at: str | None


@strawberry.type
class KnowledgeRelationType:
    id: str
    from_entity: str
    to_entity: str
    relation_type: str
    properties: JSON | None
    from_name: str | None = None
    to_name: str | None = None
    created_at: str | None


@strawberry.type
class SessionType:
    id: str
    agent_id: str
    session_type: str
    started_at: str | None
    ended_at: str | None
    messages_count: int
    tokens_used: int
    cost_usd: float
    status: str


@strawberry.type
class ModelUsageType:
    id: str
    model: str
    provider: str | None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int | None
    success: bool
    source: str
    created_at: str | None


@strawberry.type
class StatsType:
    activities_count: int
    thoughts_count: int
    memories_count: int
    goals_count: int
    last_activity: str | None


@strawberry.input
class MemoryInput:
    key: str
    value: JSON
    category: str = "general"


@strawberry.input
class GoalUpdateInput:
    status: str | None = None
    progress: float | None = None
    priority: int | None = None


# S4-08: Knowledge Graph query types

@strawberry.type
class GraphTraversalNodeType:
    id: str
    name: str
    entity_type: str
    properties: JSON | None


@strawberry.type
class GraphTraversalEdgeType:
    id: str
    from_entity: str
    to_entity: str
    relation_type: str
    properties: JSON | None


@strawberry.type 
class GraphTraversalResult:
    nodes: list[GraphTraversalNodeType]
    edges: list[GraphTraversalEdgeType]
    total_nodes: int
    total_edges: int
    traversal_depth: int


@strawberry.type
class SkillCandidate:
    id: str
    name: str
    entity_type: str
    properties: JSON | None
    match_type: str
    relevance: str


@strawberry.type
class SkillForTaskResult:
    task: str
    candidates: list[SkillCandidate]
    count: int
    tools_searched: int
