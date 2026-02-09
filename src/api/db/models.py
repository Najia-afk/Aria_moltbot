"""
SQLAlchemy 2.0 ORM models for Aria Brain (aria_warehouse).

Canonical source of truth for all database tables.
Driver: psycopg 3 via SQLAlchemy async.
"""
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean, DateTime, Float, Integer, Numeric, String, Text, Index, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import inspect as sa_inspect


# ── Base ─────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """Shared base for all Aria ORM models."""

    def to_dict(self) -> dict:
        """Serialize model instance to a JSON-friendly dict.

        Uses DB column names as keys (e.g. ``metadata`` not ``metadata_json``).
        """
        result: dict[str, Any] = {}
        mapper = sa_inspect(type(self))
        for attr in mapper.column_attrs:
            col_name = attr.columns[0].name          # DB column name
            val = getattr(self, attr.key)             # Python attribute value
            if isinstance(val, datetime):
                result[col_name] = val.isoformat()
            elif isinstance(val, uuid_mod.UUID):
                result[col_name] = str(val)
            elif isinstance(val, Decimal):
                result[col_name] = float(val)
            else:
                result[col_name] = val
        return result


# ── Core domain ──────────────────────────────────────────────────────────────

class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    category: Mapped[str] = mapped_column(String(100), server_default=text("'general'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


Index("idx_memories_key", Memory.key)
Index("idx_memories_category", Memory.category)
Index("idx_memories_updated", Memory.updated_at.desc())


class Thought(Base):
    __tablename__ = "thoughts"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), server_default=text("'general'"))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


Index("idx_thoughts_category", Thought.category)
Index("idx_thoughts_created", Thought.created_at.desc())


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    goal_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), server_default=text("'pending'"))
    priority: Mapped[int] = mapped_column(Integer, server_default=text("2"))
    progress: Mapped[float] = mapped_column(Numeric(5, 2), server_default=text("0"))
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


Index("idx_goals_status", Goal.status)
Index("idx_goals_priority", Goal.priority.desc())


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    skill: Mapped[str | None] = mapped_column(String(100))
    details: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    success: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


Index("idx_activity_action", ActivityLog.action)
Index("idx_activity_skill", ActivityLog.skill)
Index("idx_activity_created", ActivityLog.created_at.desc())


# ── Social / Community ───────────────────────────────────────────────────────

class SocialPost(Base):
    __tablename__ = "social_posts"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    platform: Mapped[str] = mapped_column(String(50), server_default=text("'moltbook'"))
    post_id: Mapped[str | None] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(String(50), server_default=text("'public'"))
    reply_to: Mapped[str | None] = mapped_column(String(100))
    url: Mapped[str | None] = mapped_column(Text)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, server_default=text("'{}'::jsonb"))


Index("idx_posts_platform", SocialPost.platform)
Index("idx_posts_posted", SocialPost.posted_at.desc())


# ── Scheduling / Operations ──────────────────────────────────────────────────

class HourlyGoal(Base):
    __tablename__ = "hourly_goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hour_slot: Mapped[int] = mapped_column(Integer, nullable=False)
    goal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default=text("'pending'"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


# ── Knowledge Graph ──────────────────────────────────────────────────────────

class KnowledgeEntity(Base):
    __tablename__ = "knowledge_entities"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    properties: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


Index("idx_kg_entity_name", KnowledgeEntity.name)


class KnowledgeRelation(Base):
    __tablename__ = "knowledge_relations"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    from_entity: Mapped[Any] = mapped_column(UUID(as_uuid=True), nullable=False)
    to_entity: Mapped[Any] = mapped_column(UUID(as_uuid=True), nullable=False)
    relation_type: Mapped[str] = mapped_column(Text, nullable=False)
    properties: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


Index("idx_kg_relation_from", KnowledgeRelation.from_entity)
Index("idx_kg_relation_to", KnowledgeRelation.to_entity)


# ── Performance / Review ─────────────────────────────────────────────────────

class PerformanceLog(Base):
    __tablename__ = "performance_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_period: Mapped[str] = mapped_column(String(20), nullable=False)
    successes: Mapped[str | None] = mapped_column(Text)
    failures: Mapped[str | None] = mapped_column(Text)
    improvements: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


class PendingComplexTask(Base):
    __tablename__ = "pending_complex_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), server_default=text("'medium'"))
    status: Mapped[str] = mapped_column(String(20), server_default=text("'pending'"))
    result: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ── Heartbeat ────────────────────────────────────────────────────────────────

class HeartbeatLog(Base):
    __tablename__ = "heartbeat_log"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    beat_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), server_default=text("'healthy'"))
    details: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


Index("idx_heartbeat_created", HeartbeatLog.created_at.desc())


# ── OpenClaw Scheduling ─────────────────────────────────────────────────────

class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(50), server_default=text("'main'"))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    schedule_kind: Mapped[str] = mapped_column(String(20), server_default=text("'cron'"))
    schedule_expr: Mapped[str] = mapped_column(String(50), nullable=False)
    session_target: Mapped[str | None] = mapped_column(String(50))
    wake_mode: Mapped[str | None] = mapped_column(String(50))
    payload_kind: Mapped[str | None] = mapped_column(String(50))
    payload_text: Mapped[str | None] = mapped_column(Text)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(String(20))
    last_duration_ms: Mapped[int | None] = mapped_column(Integer)
    run_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    success_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    fail_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    created_at_ms: Mapped[int | None] = mapped_column(Integer)
    updated_at_ms: Mapped[int | None] = mapped_column(Integer)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


Index("idx_jobs_name", ScheduledJob.name)
Index("idx_jobs_enabled", ScheduledJob.enabled)
Index("idx_jobs_next_run", ScheduledJob.next_run_at)


# ── Security ─────────────────────────────────────────────────────────────────

class SecurityEvent(Base):
    __tablename__ = "security_events"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    threat_level: Mapped[str] = mapped_column(String(20), nullable=False)
    threat_type: Mapped[str] = mapped_column(String(100), nullable=False)
    threat_patterns: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    input_preview: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(100))
    user_id: Mapped[str | None] = mapped_column(String(100))
    blocked: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    details: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


Index("idx_security_threat_level", SecurityEvent.threat_level)
Index("idx_security_threat_type", SecurityEvent.threat_type)
Index("idx_security_created", SecurityEvent.created_at.desc())
Index("idx_security_blocked", SecurityEvent.blocked)


# ── Schedule Tick ────────────────────────────────────────────────────────────

class ScheduleTick(Base):
    __tablename__ = "schedule_tick"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_tick: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tick_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    heartbeat_interval: Mapped[int] = mapped_column(Integer, server_default=text("3600"))
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    jobs_total: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    jobs_successful: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    jobs_failed: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    last_job_name: Mapped[str | None] = mapped_column(String(255))
    last_job_status: Mapped[str | None] = mapped_column(String(50))
    next_job_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


# ── Operations: Sessions / Usage ─────────────────────────────────────────────

class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False)
    session_type: Mapped[str] = mapped_column(String(50), server_default=text("'interactive'"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    messages_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    tokens_used: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), server_default=text("0"))
    status: Mapped[str] = mapped_column(String(50), server_default=text("'active'"))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, server_default=text("'{}'::jsonb"))


Index("idx_agent_sessions_agent", AgentSession.agent_id)
Index("idx_agent_sessions_started", AgentSession.started_at.desc())
Index("idx_agent_sessions_status", AgentSession.status)


class ModelUsage(Base):
    __tablename__ = "model_usage"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(50))
    input_tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    output_tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), server_default=text("0"))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    error_message: Mapped[str | None] = mapped_column(Text)
    session_id: Mapped[Any | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


Index("idx_model_usage_model", ModelUsage.model)
Index("idx_model_usage_created", ModelUsage.created_at.desc())
Index("idx_model_usage_session", ModelUsage.session_id)


class RateLimit(Base):
    __tablename__ = "rate_limits"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    skill: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    last_action: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    action_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    last_post: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


Index("idx_rate_limits_skill", RateLimit.skill)


class ApiKeyRotation(Base):
    __tablename__ = "api_key_rotations"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    service: Mapped[str] = mapped_column(String(100), nullable=False)
    rotated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    reason: Mapped[str | None] = mapped_column(Text)
    rotated_by: Mapped[str] = mapped_column(String(100), server_default=text("'system'"))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, server_default=text("'{}'::jsonb"))


# ── Agent Performance (pheromone scoring) ─────────────────────────────────

class AgentPerformance(Base):
    __tablename__ = "agent_performance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    token_cost: Mapped[float | None] = mapped_column(Numeric(10, 6))
    pheromone_score: Mapped[float] = mapped_column(Numeric(5, 3), server_default=text("0.500"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


Index("idx_agent_perf_agent", AgentPerformance.agent_id)
Index("idx_agent_perf_task", AgentPerformance.task_type)
Index("idx_agent_perf_created", AgentPerformance.created_at.desc())


# ── Working Memory ───────────────────────────────────────────────────────────

class WorkingMemory(Base):
    __tablename__ = "working_memory"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    importance: Mapped[float] = mapped_column(Float, server_default=text("0.5"))
    ttl_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str | None] = mapped_column(String(100))
    checkpoint_id: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    access_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))


Index("idx_wm_category", WorkingMemory.category)
Index("idx_wm_key", WorkingMemory.key)
Index("idx_wm_importance", WorkingMemory.importance.desc())
Index("idx_wm_checkpoint", WorkingMemory.checkpoint_id)
