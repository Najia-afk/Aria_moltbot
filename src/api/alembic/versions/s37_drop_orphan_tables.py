"""S-37: drop 9 orphan tables

Revision ID: s37_drop_orphans
Revises:
Create Date: 2025-01-01
"""
from alembic import op

revision = "s37_drop_orphans"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    orphans = [
        "bubble_monetization", "model_cost_reference", "model_discovery_log",
        "moltbook_users", "opportunities", "secops_work",
        "spending_alerts", "spending_log", "yield_positions",
    ]
    for table in orphans:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")


def downgrade():
    # Restore from aria_memories/archive/ backups if needed
    pass
