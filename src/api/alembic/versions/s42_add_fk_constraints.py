"""S-42: Add FK constraints and fix defaults.

Revision ID: s42_add_fk
Revises:
Create Date: 2025-01-01
"""
from alembic import op

revision = "s42_add_fk"
down_revision = "s37_drop_orphans"
branch_labels = None
depends_on = None


def upgrade():
    # Clean orphan rows first
    op.execute("""
        DELETE FROM knowledge_relations
        WHERE from_entity NOT IN (SELECT id FROM knowledge_entities)
           OR to_entity NOT IN (SELECT id FROM knowledge_entities)
    """)
    op.create_foreign_key("fk_kr_from_entity", "knowledge_relations", "knowledge_entities", ["from_entity"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("fk_kr_to_entity", "knowledge_relations", "knowledge_entities", ["to_entity"], ["id"], ondelete="CASCADE")

    op.execute("""
        UPDATE model_usage SET session_id = NULL
        WHERE session_id IS NOT NULL AND session_id NOT IN (SELECT id FROM agent_sessions)
    """)
    op.create_foreign_key("fk_mu_session", "model_usage", "agent_sessions", ["session_id"], ["id"], ondelete="SET NULL")

    op.execute("""
        UPDATE social_posts SET reply_to = NULL
        WHERE reply_to IS NOT NULL AND reply_to NOT IN (SELECT post_id FROM social_posts)
    """)
    op.create_foreign_key("fk_sp_reply_to", "social_posts", "social_posts", ["reply_to"], ["post_id"], ondelete="SET NULL")

    op.alter_column("working_memory", "updated_at", server_default="NOW()")
    op.execute("UPDATE working_memory SET updated_at = created_at WHERE updated_at IS NULL")


def downgrade():
    op.drop_constraint("fk_kr_from_entity", "knowledge_relations", type_="foreignkey")
    op.drop_constraint("fk_kr_to_entity", "knowledge_relations", type_="foreignkey")
    op.drop_constraint("fk_mu_session", "model_usage", type_="foreignkey")
    op.drop_constraint("fk_sp_reply_to", "social_posts", type_="foreignkey")
