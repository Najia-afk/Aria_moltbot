"""S-46: Add expression index on agent_sessions metadata->>'openclaw_session_id'.

This index was defined in the SQLAlchemy model but missing from the actual
database.  session_manager's _mark_ended_in_pg() relies on it for fast lookups.

Revision ID: s46_openclaw_sid_idx
Revises: s44_gin_indexes
"""
from alembic import op

revision = "s46_openclaw_sid_idx"
down_revision = "s44_gin_indexes"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_sessions_openclaw_sid "
        "ON agent_sessions ((metadata ->> 'openclaw_session_id'))"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_agent_sessions_openclaw_sid")
