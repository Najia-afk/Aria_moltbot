"""
SQLAlchemy schema for Aria Brain (aria_warehouse).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text, Index, text
from sqlalchemy.schema import CreateIndex, CreateTable
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


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


class HourlyGoal(Base):
    __tablename__ = "hourly_goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hour_slot: Mapped[int] = mapped_column(Integer, nullable=False)
    goal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default=text("'pending'"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


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


class HeartbeatLog(Base):
    __tablename__ = "heartbeat_log"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    beat_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), server_default=text("'healthy'"))
    details: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


Index("idx_heartbeat_created", HeartbeatLog.created_at.desc())


class ScheduledJob(Base):
    """
    Scheduled jobs synced from OpenClaw cron system.
    Source: /root/.openclaw/cron/jobs.json in clawdbot container
    """
    __tablename__ = "scheduled_jobs"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # UUID from OpenClaw
    agent_id: Mapped[str] = mapped_column(String(50), server_default=text("'main'"))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    schedule_kind: Mapped[str] = mapped_column(String(20), server_default=text("'cron'"))
    schedule_expr: Mapped[str] = mapped_column(String(50), nullable=False)  # Cron expression
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
    created_at_ms: Mapped[int | None] = mapped_column(Integer)  # OpenClaw timestamp
    updated_at_ms: Mapped[int | None] = mapped_column(Integer)  # OpenClaw timestamp
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


Index("idx_jobs_name", ScheduledJob.name)
Index("idx_jobs_enabled", ScheduledJob.enabled)
Index("idx_jobs_next_run", ScheduledJob.next_run_at)


class SecurityEvent(Base):
    """
    Security events logged by the input_guard skill.
    Tracks prompt injection attempts, malicious inputs, rate limit violations.
    """
    __tablename__ = "security_events"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    threat_level: Mapped[str] = mapped_column(String(20), nullable=False)  # NONE, LOW, MEDIUM, HIGH, CRITICAL
    threat_type: Mapped[str] = mapped_column(String(100), nullable=False)  # prompt_injection, sql_injection, etc.
    threat_patterns: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))  # List of matched patterns
    input_preview: Mapped[str | None] = mapped_column(Text)  # First 500 chars of input (sanitized)
    source: Mapped[str | None] = mapped_column(String(100))  # api, chat, skill, etc.
    user_id: Mapped[str | None] = mapped_column(String(100))  # User/session identifier
    blocked: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))  # Was the request blocked?
    details: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))  # Additional context
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


Index("idx_security_threat_level", SecurityEvent.threat_level)
Index("idx_security_threat_type", SecurityEvent.threat_type)
Index("idx_security_created", SecurityEvent.created_at.desc())
Index("idx_security_blocked", SecurityEvent.blocked)


class ScheduleTick(Base):
    """
    Scheduler heartbeat status with job statistics.
    Tracks last tick time and aggregated job stats from OpenClaw.
    """
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


def _as_async_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url


async def ensure_schema(database_url: str) -> None:
    async_url = _as_async_url(database_url)
    engine = create_async_engine(async_url, future=True)
    try:
        async with engine.begin() as conn:
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
            for table in Base.metadata.sorted_tables:
                await conn.execute(CreateTable(table, if_not_exists=True))
                for index in table.indexes:
                    await conn.execute(CreateIndex(index, if_not_exists=True))
    finally:
        await engine.dispose()
