# src/database/models.py
"""
SQLAlchemy 2.0 Models for Aria Blue
Following mission7 DeclarativeBase pattern
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String, Text, Integer, DateTime, Boolean, JSON, Index, ForeignKey
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models"""
    pass


class Thought(Base):
    """
    Represents Aria's internal thoughts and reflections.
    Used for self-awareness, introspection, and learning.
    """
    __tablename__ = 'thoughts'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    thought_type: Mapped[str] = mapped_column(
        String(50),
        default='reflection',
        index=True
    )
    metadata: Mapped[Optional[dict]] = mapped_column(JSON, default={})
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True
    )

    __table_args__ = (
        Index('ix_thoughts_type_created', 'thought_type', 'created_at'),
    )

    def __repr__(self) -> str:
        return f"<Thought(id={self.id}, type='{self.thought_type}')>"

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'content': self.content,
            'thought_type': self.thought_type,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Goal(Base):
    """
    Represents Aria's goals and objectives.
    Tracks progress and priority of tasks.
    """
    __tablename__ = 'goals'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=1, index=True)
    status: Mapped[str] = mapped_column(
        String(50),
        default='active',
        index=True
    )
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey('goals.id'),
        nullable=True
    )
    progress: Mapped[int] = mapped_column(Integer, default=0)
    metadata: Mapped[Optional[dict]] = mapped_column(JSON, default={})
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        onupdate=datetime.utcnow
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Self-referential relationship for sub-goals
    parent = relationship('Goal', remote_side=[id], backref='sub_goals')

    __table_args__ = (
        Index('ix_goals_status_priority', 'status', 'priority'),
    )

    def __repr__(self) -> str:
        return f"<Goal(id={self.id}, title='{self.title}', status='{self.status}')>"

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'priority': self.priority,
            'status': self.status,
            'parent_id': self.parent_id,
            'progress': self.progress,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


class Interaction(Base):
    """
    Represents conversations and interactions with users.
    Stores the chat history.
    """
    __tablename__ = 'interactions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # user, assistant, system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer)
    model: Mapped[Optional[str]] = mapped_column(String(100))
    metadata: Mapped[Optional[dict]] = mapped_column(JSON, default={})
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True
    )

    __table_args__ = (
        Index('ix_interactions_session_created', 'session_id', 'created_at'),
    )

    def __repr__(self) -> str:
        return f"<Interaction(id={self.id}, role='{self.role}')>"

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'session_id': self.session_id,
            'role': self.role,
            'content': self.content,
            'tokens_used': self.tokens_used,
            'model': self.model,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Memory(Base):
    """
    Long-term memory storage for important facts and learnings.
    Used for context retrieval and personalization.
    """
    __tablename__ = 'memories'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), index=True)
    importance: Mapped[int] = mapped_column(Integer, default=1)
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    last_accessed: Mapped[Optional[datetime]] = mapped_column(DateTime)
    embedding: Mapped[Optional[list]] = mapped_column(JSON)  # For vector similarity
    metadata: Mapped[Optional[dict]] = mapped_column(JSON, default={})
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index('ix_memories_category_importance', 'category', 'importance'),
    )

    def __repr__(self) -> str:
        return f"<Memory(id={self.id}, key='{self.key}')>"

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'key': self.key,
            'value': self.value,
            'category': self.category,
            'importance': self.importance,
            'access_count': self.access_count,
            'last_accessed': self.last_accessed.isoformat() if self.last_accessed else None,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class SoulState(Base):
    """
    Represents Aria's emotional and cognitive state.
    Used for personality consistency and mood tracking.
    """
    __tablename__ = 'soul_states'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mood: Mapped[str] = mapped_column(String(50), default='neutral')
    energy: Mapped[int] = mapped_column(Integer, default=100)  # 0-100
    curiosity: Mapped[int] = mapped_column(Integer, default=50)  # 0-100
    focus: Mapped[int] = mapped_column(Integer, default=50)  # 0-100
    creativity: Mapped[int] = mapped_column(Integer, default=50)  # 0-100
    context: Mapped[Optional[dict]] = mapped_column(JSON, default={})
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True
    )

    def __repr__(self) -> str:
        return f"<SoulState(id={self.id}, mood='{self.mood}', energy={self.energy})>"

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'mood': self.mood,
            'energy': self.energy,
            'curiosity': self.curiosity,
            'focus': self.focus,
            'creativity': self.creativity,
            'context': self.context,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class AuditLog(Base):
    """
    Audit trail for all significant actions.
    Following mission7's Prediction pattern for logging.
    """
    __tablename__ = 'audit_logs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), index=True)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer)
    user_id: Mapped[Optional[str]] = mapped_column(String(255))
    details: Mapped[Optional[dict]] = mapped_column(JSON, default={})
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True
    )

    __table_args__ = (
        Index('ix_audit_logs_entity', 'entity_type', 'entity_id'),
        Index('ix_audit_logs_action_created', 'action', 'created_at'),
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action='{self.action}')>"

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'action': self.action,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'user_id': self.user_id,
            'details': self.details,
            'ip_address': self.ip_address,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
