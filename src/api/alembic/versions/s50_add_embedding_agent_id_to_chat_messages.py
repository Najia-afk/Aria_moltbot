"""S-50: Add embedding and agent_id columns to aria_engine.chat_messages.

These columns were added to the ORM model (EngineChatMessage) during the
schema refactor but never captured in a migration.

- embedding: vector(1536) for pgvector semantic search (nullable)
- agent_id: varchar(100) to track which agent sent the message (nullable)

Uses IF NOT EXISTS so it's safe to run on databases where the columns were
already added manually.

Revision ID: s50_add_embedding_agent_id_to_chat_messages
Revises: s49_baseline_all_tables
Create Date: 2026-02-21
"""
from alembic import op
import sqlalchemy as sa

revision = "s50_add_embedding_agent_id_to_chat_messages"
down_revision = "s49_baseline_all_tables"
branch_labels = None
depends_on = None

_SCHEMA = "aria_engine"
_TABLE = "chat_messages"


def upgrade():
    # Ensure pgvector extension is available (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Add agent_id column (nullable, no default)
    op.execute(
        f"ALTER TABLE {_SCHEMA}.{_TABLE} "
        f"ADD COLUMN IF NOT EXISTS agent_id VARCHAR(100)"
    )

    # Add embedding column (pgvector 1536-dim, nullable)
    op.execute(
        f"ALTER TABLE {_SCHEMA}.{_TABLE} "
        f"ADD COLUMN IF NOT EXISTS embedding vector(1536)"
    )


def downgrade():
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} DROP COLUMN IF EXISTS embedding")
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} DROP COLUMN IF EXISTS agent_id")
