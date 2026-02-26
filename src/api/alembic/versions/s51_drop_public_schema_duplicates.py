"""S-51: Drop duplicate public-schema tables.

After S-49 the runtime bootstrapper (`ensure_schema()` in session.py) creates
all tables in the correct `aria_data` / `aria_engine` schemas.  However the
S-49 baseline created everything in `public` as well, leaving duplicates.

This migration drops:
  - All 26 aria_data tables from public (memories, goals, thoughts, etc.)
  - The 6 old `engine_*` prefixed tables from public
  - The rate_limits/api_key_rotations/scheduled_jobs/schedule_tick public copies

Keeps: alembic_version, extensions, pg_* catalog tables.
Uses DROP TABLE IF EXISTS CASCADE to be idempotent.

Revision ID: s51_drop_public_schema_duplicates
Revises: s50_add_embedding_agent_id_to_chat_messages
Create Date: 2026-02-24
"""

from alembic import op

# revision identifiers
revision = "s51_drop_public_schema_duplicates"
down_revision = "s50_add_embedding_agent_id_to_chat_messages"
branch_labels = None
depends_on = None

# ── Tables to drop from public ─────────────────────────────────
# These all have authoritative copies in aria_data or aria_engine schemas.
PUBLIC_TABLES_TO_DROP = [
    # aria_data duplicates
    "memories",
    "thoughts",
    "goals",
    "activity_log",
    "social_posts",
    "hourly_goals",
    "knowledge_entities",
    "knowledge_relations",
    "skill_graph_entities",
    "skill_graph_relations",
    "knowledge_query_log",
    "performance_log",
    "pending_complex_tasks",
    "heartbeat_log",
    "security_events",
    "agent_sessions",
    "session_messages",
    "sentiment_events",
    "model_usage",
    "agent_performance",
    "working_memory",
    "skill_status",
    "semantic_memories",
    "lessons_learned",
    "improvement_proposals",
    "skill_invocations",
    # aria_engine duplicates (old engine_* prefix tables)
    "engine_chat_sessions",
    "engine_chat_messages",
    "engine_cron_jobs",
    "engine_agent_state",
    "engine_config",
    "engine_agent_tools",
    # aria_engine duplicates (new names, may exist in public from s49)
    "scheduled_jobs",
    "schedule_tick",
    "rate_limits",
    "api_key_rotations",
]


def upgrade() -> None:
    """Drop all duplicate public-schema tables."""
    for table in PUBLIC_TABLES_TO_DROP:
        op.execute(f'DROP TABLE IF EXISTS public."{table}" CASCADE')


def downgrade() -> None:
    """No-op: we cannot recreate the dropped tables with their data.

    To restore, use the rollback script:
      scripts/rollback_public_schema_drop.sql
    """
    pass
