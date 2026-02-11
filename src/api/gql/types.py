"""
Strawberry GraphQL types for Aria data models.
"""

from typing import Optional
import strawberry
from strawberry.scalars import JSON


@strawberry.type
class ActivityType:
    id: str
    action: str
    skill: Optional[str]
    details: Optional[JSON]
    success: bool
    error_message: Optional[str]
    created_at: Optional[str]


@strawberry.type
class ThoughtType:
    id: str
    category: str
    content: str
    metadata: Optional[JSON]
    created_at: Optional[str]


@strawberry.type
class MemoryType:
    id: str
    key: str
    value: Optional[JSON]
    category: str
    created_at: Optional[str]
    updated_at: Optional[str]


@strawberry.type
class GoalType:
    id: str
    goal_id: str
    title: str
    description: Optional[str]
    status: str
    priority: int
    progress: float
    due_date: Optional[str]
    created_at: Optional[str]
    completed_at: Optional[str]
    # Sprint Board fields (S3-08)
    sprint: Optional[str] = None
    board_column: Optional[str] = None
    position: int = 0
    assigned_to: Optional[str] = None
    tags: Optional[JSON] = None
    updated_at: Optional[str] = None


@strawberry.type
class KnowledgeEntityType:
    id: str
    name: str
    entity_type: str
    properties: Optional[JSON]
    created_at: Optional[str]
    updated_at: Optional[str]


@strawberry.type
class KnowledgeRelationType:
    id: str
    from_entity: str
    to_entity: str
    relation_type: str
    properties: Optional[JSON]
    from_name: Optional[str] = None
    to_name: Optional[str] = None
    created_at: Optional[str]


@strawberry.type
class SessionType:
    id: str
    agent_id: str
    session_type: str
    started_at: Optional[str]
    ended_at: Optional[str]
    messages_count: int
    tokens_used: int
    cost_usd: float
    status: str


@strawberry.type
class ModelUsageType:
    id: str
    model: str
    provider: Optional[str]
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: Optional[int]
    success: bool
    source: str
    created_at: Optional[str]


@strawberry.type
class StatsType:
    activities_count: int
    thoughts_count: int
    memories_count: int
    goals_count: int
    last_activity: Optional[str]


@strawberry.input
class MemoryInput:
    key: str
    value: JSON
    category: str = "general"


@strawberry.input
class GoalUpdateInput:
    status: Optional[str] = None
    progress: Optional[float] = None
    priority: Optional[int] = None


# S4-08: Knowledge Graph query types

@strawberry.type
class GraphTraversalNodeType:
    id: str
    name: str
    entity_type: str
    properties: Optional[JSON]


@strawberry.type
class GraphTraversalEdgeType:
    id: str
    from_entity: str
    to_entity: str
    relation_type: str
    properties: Optional[JSON]


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
    properties: Optional[JSON]
    match_type: str
    relevance: str


@strawberry.type
class SkillForTaskResult:
    task: str
    candidates: list[SkillCandidate]
    count: int
    tools_searched: int
