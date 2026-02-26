"""
Strawberry GraphQL types for Aria data models.
"""

import strawberry
from strawberry.scalars import JSON
from typing import Generic, TypeVar

T = TypeVar("T")


# ── Cursor-based pagination (Relay-style) ────────────────────────────────────

@strawberry.type
class PageInfo:
    has_next_page: bool
    has_previous_page: bool
    start_cursor: str | None
    end_cursor: str | None


@strawberry.type
class ActivityEdge:
    node: "ActivityType"
    cursor: str


@strawberry.type
class ActivityConnection:
    edges: list[ActivityEdge]
    page_info: PageInfo
    total_count: int


@strawberry.type
class ThoughtEdge:
    node: "ThoughtType"
    cursor: str


@strawberry.type
class ThoughtConnection:
    edges: list[ThoughtEdge]
    page_info: PageInfo
    total_count: int


@strawberry.type
class MemoryEdge:
    node: "MemoryType"
    cursor: str


@strawberry.type
class MemoryConnection:
    edges: list[MemoryEdge]
    page_info: PageInfo
    total_count: int


@strawberry.type
class GoalEdge:
    node: "GoalType"
    cursor: str


@strawberry.type
class GoalConnection:
    edges: list[GoalEdge]
    page_info: PageInfo
    total_count: int


@strawberry.type
class SessionEdge:
    node: "SessionType"
    cursor: str


@strawberry.type
class SessionConnection:
    edges: list[SessionEdge]
    page_info: PageInfo
    total_count: int


# ── Error type ───────────────────────────────────────────────────────────────

@strawberry.type
class GQLError:
    """Structured error returned by mutations and queries."""
    message: str
    code: str = "INTERNAL_ERROR"


# ── Mutation result union types ──────────────────────────────────────────────

@strawberry.type
class DeleteResult:
    deleted: bool
    id: str


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


# ── Input types for new mutations ────────────────────────────────────────────

@strawberry.input
class ActivityInput:
    action: str
    skill: str | None = None
    details: JSON | None = None
    success: bool = True
    error_message: str | None = None


@strawberry.input
class ThoughtInput:
    content: str
    category: str = "general"
    metadata: JSON | None = None


@strawberry.input
class GoalInput:
    title: str
    description: str | None = None
    status: str = "active"
    priority: int = 3
    due_date: str | None = None
    sprint: str | None = None
    board_column: str | None = None
    assigned_to: str | None = None


@strawberry.input
class SessionInput:
    agent_id: str = "aria"
    session_type: str = "chat"
