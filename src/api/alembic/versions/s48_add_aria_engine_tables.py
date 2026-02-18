"""Add aria engine tables for standalone runtime.

Creates 6 tables for the aria_engine package:
- engine_chat_sessions: Chat session lifecycle
- engine_chat_messages: Individual messages within sessions
- engine_cron_jobs: Scheduled job definitions and state
- engine_agent_state: Per-agent runtime state
- engine_config: Key-value configuration store
- engine_agent_tools: Agent-to-tool mappings

Revision ID: s48
Revises: s47
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers
revision = "s48_add_aria_engine_tables"
down_revision = "s47_create_sentiment_events"
branch_labels = None
depends_on = None


def upgrade():
    # Engine chat sessions
    op.create_table(
        "engine_chat_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("agent_id", sa.String(100), nullable=False, server_default="main"),
        sa.Column("session_type", sa.String(50), nullable=False, server_default="interactive"),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("system_prompt", sa.Text, nullable=True),
        sa.Column("model", sa.String(200), nullable=True),
        sa.Column("temperature", sa.Float, server_default="0.7"),
        sa.Column("max_tokens", sa.Integer, server_default="4096"),
        sa.Column("context_window", sa.Integer, server_default="50"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("message_count", sa.Integer, server_default="0"),
        sa.Column("total_tokens", sa.Integer, server_default="0"),
        sa.Column("total_cost", sa.Numeric(10, 6), server_default="0"),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_ecs_agent", "engine_chat_sessions", ["agent_id"])
    op.create_index("idx_ecs_status", "engine_chat_sessions", ["status"])
    op.create_index("idx_ecs_created", "engine_chat_sessions", ["created_at"])

    # Engine chat messages
    op.create_table(
        "engine_chat_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("engine_chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("thinking", sa.Text, nullable=True),
        sa.Column("tool_calls", JSONB, nullable=True),
        sa.Column("tool_results", JSONB, nullable=True),
        sa.Column("model", sa.String(200), nullable=True),
        sa.Column("tokens_input", sa.Integer, nullable=True),
        sa.Column("tokens_output", sa.Integer, nullable=True),
        sa.Column("cost", sa.Numeric(10, 6), nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_ecm_session", "engine_chat_messages", ["session_id"])
    op.create_index("idx_ecm_role", "engine_chat_messages", ["role"])
    op.create_index("idx_ecm_created", "engine_chat_messages", ["created_at"])

    # Engine cron jobs
    op.create_table(
        "engine_cron_jobs",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("schedule", sa.String(100), nullable=False),
        sa.Column("agent_id", sa.String(100), server_default="main"),
        sa.Column("enabled", sa.Boolean, server_default="true"),
        sa.Column("payload_type", sa.String(50), server_default="prompt"),
        sa.Column("payload", sa.Text, nullable=False),
        sa.Column("session_mode", sa.String(50), server_default="isolated"),
        sa.Column("max_duration_seconds", sa.Integer, server_default="300"),
        sa.Column("retry_count", sa.Integer, server_default="0"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(20), nullable=True),
        sa.Column("last_duration_ms", sa.Integer, nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("run_count", sa.Integer, server_default="0"),
        sa.Column("success_count", sa.Integer, server_default="0"),
        sa.Column("fail_count", sa.Integer, server_default="0"),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_ecj_enabled", "engine_cron_jobs", ["enabled"])
    op.create_index("idx_ecj_next_run", "engine_cron_jobs", ["next_run_at"])

    # Engine agent state
    op.create_table(
        "engine_agent_state",
        sa.Column("agent_id", sa.String(100), primary_key=True),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("temperature", sa.Float, server_default="0.7"),
        sa.Column("max_tokens", sa.Integer, server_default="4096"),
        sa.Column("system_prompt", sa.Text, nullable=True),
        sa.Column("focus_type", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), server_default="idle"),
        sa.Column("current_session_id", UUID(as_uuid=True), nullable=True),
        sa.Column("current_task", sa.Text, nullable=True),
        sa.Column("consecutive_failures", sa.Integer, server_default="0"),
        sa.Column("pheromone_score", sa.Numeric(5, 3), server_default="0.500"),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # Engine config (key-value store)
    op.create_table(
        "engine_config",
        sa.Column("key", sa.String(200), primary_key=True),
        sa.Column("value", JSONB, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_by", sa.String(100), server_default="system"),
    )

    # Engine agent tools
    op.create_table(
        "engine_agent_tools",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("agent_id", sa.String(100), nullable=False),
        sa.Column("skill_name", sa.String(100), nullable=False),
        sa.Column("function_name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("parameters", JSONB, server_default="{}"),
        sa.Column("enabled", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_eat_agent", "engine_agent_tools", ["agent_id"])


def downgrade():
    op.drop_table("engine_agent_tools")
    op.drop_table("engine_config")
    op.drop_table("engine_agent_state")
    op.drop_table("engine_cron_jobs")
    op.drop_table("engine_chat_messages")
    op.drop_table("engine_chat_sessions")
