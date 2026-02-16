"""S-47: Ensure sentiment_events table and indexes exist.

The table was defined in ORM models but had no dedicated migration.
This migration creates it idempotently for production reliability.

Revision ID: s47_create_sentiment_events
Revises: s46_openclaw_sid_idx
"""
from alembic import op

revision = "s47_create_sentiment_events"
down_revision = "s46_openclaw_sid_idx"
branch_labels = None
depends_on = None


def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute("""
        CREATE TABLE IF NOT EXISTS sentiment_events (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            message_id UUID NOT NULL REFERENCES session_messages(id) ON DELETE CASCADE,
            session_id UUID REFERENCES agent_sessions(id) ON DELETE SET NULL,
            external_session_id VARCHAR(120),
            sentiment_label VARCHAR(20) NOT NULL,
            primary_emotion VARCHAR(50),
            valence FLOAT NOT NULL,
            arousal FLOAT NOT NULL,
            dominance FLOAT NOT NULL,
            confidence FLOAT NOT NULL,
            importance FLOAT DEFAULT 0.3,
            metadata JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_sentiment_event_message UNIQUE (message_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_sentiment_events_message ON sentiment_events (message_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sentiment_events_session ON sentiment_events (session_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sentiment_events_external ON sentiment_events (external_session_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sentiment_events_label ON sentiment_events (sentiment_label)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sentiment_events_created ON sentiment_events (created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sentiment_events_session_created ON sentiment_events (session_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sentiment_events_label_created ON sentiment_events (sentiment_label, created_at DESC)")


def downgrade():
    op.execute("DROP TABLE IF EXISTS sentiment_events CASCADE")
