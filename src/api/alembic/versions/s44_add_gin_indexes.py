"""S-44: Add GIN indexes for JSONB search and pg_trgm extension.

Revision ID: s44_gin_indexes
Revises: s37_drop_orphans
"""
from alembic import op

revision = "s44_gin_indexes"
down_revision = "s42_add_fk"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE INDEX IF NOT EXISTS idx_activity_details_gin ON activity_log USING gin (details)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_thoughts_content_trgm ON thoughts USING gin (content gin_trgm_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_memories_value_gin ON memories USING gin (value)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_kg_properties_gin ON knowledge_entities USING gin (properties)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_activity_details_gin")
    op.execute("DROP INDEX IF EXISTS idx_thoughts_content_trgm")
    op.execute("DROP INDEX IF EXISTS idx_memories_value_gin")
    op.execute("DROP INDEX IF EXISTS idx_kg_properties_gin")
