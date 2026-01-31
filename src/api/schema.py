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


class HeartbeatLog(Base):
    __tablename__ = "heartbeat_log"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    beat_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), server_default=text("'healthy'"))
    details: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


Index("idx_heartbeat_created", HeartbeatLog.created_at.desc())


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
