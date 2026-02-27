"""s52 — pg17 / pgvector 0.8.2 upgrade: add HNSW indexes on embedding columns

Revision ID: s52_pg17_pgvector_hnsw
Revises: s51_drop_public_schema_duplicates
Create Date: 2026-02-27

Notes:
  - HNSW indexes were unavailable / immature when the tables were created.
  - This migration adds them idempotently using CREATE INDEX IF NOT EXISTS.
  - The pg16→pg17 image bump requires a separate data migration for existing
    deployments (see S-51 ticket migration path). Fresh clones (S-49) need none.
  - pgvector extension version upgrade 0.8.0 → 0.8.2 is automatic on container
    restart when the pgvector/pgvector:0.8.2-pg17 image is used.
"""

from alembic import op

revision = "s52_pg17_pgvector_hnsw"
down_revision = "s51_drop_public_schema_duplicates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Update pgvector extension to latest installed version
    op.execute("ALTER EXTENSION vector UPDATE")

    # HNSW cosine index — semantic_memories (768-dim embeddings)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_semantic_embedding_hnsw "
        "ON aria_data.semantic_memories USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )

    # HNSW cosine index — session_messages (1536-dim embeddings, nullable)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_session_messages_embedding_hnsw "
        "ON aria_engine.session_messages USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64) "
        "WHERE embedding IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS aria_data.idx_semantic_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS aria_engine.idx_session_messages_embedding_hnsw")
