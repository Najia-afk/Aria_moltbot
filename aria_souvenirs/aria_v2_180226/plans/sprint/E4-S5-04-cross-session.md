# S5-04: Cross-Session Context via pgvector Similarity Search
**Epic:** E4 — Session Management | **Priority:** P1 | **Points:** 5 | **Phase:** 4

## Problem
Agents lose context when starting a new session — they can't recall what was discussed in previous sessions without manual lookup. The engine needs `load_cross_session_context()` that uses pgvector similarity search to find relevant messages across all of an agent's prior sessions, providing semantic context continuity between conversations. A keyword fallback ensures the feature works before embeddings are populated.

Reference: `MASTER_PLAN.md` lines 133-135 — `chat_messages` has `embedding VECTOR(1536)` column. `aria_agents/coordinator.py` lines 300-340 — existing context building. PostgreSQL pgvector extension for approximate nearest neighbor search.

## Root Cause
The current agent system treats each session as fully isolated — there's no mechanism to carry forward insights, preferences, or decisions from prior conversations. This creates a "Groundhog Day" effect where agents repeat suggestions, re-ask clarified questions, and can't build on prior work. The `VECTOR(1536)` column in `chat_messages` is defined in the schema but unused.

## Fix
### `aria_engine/cross_session.py`
```python
"""
Cross-Session Context — semantic retrieval across conversation history.

Features:
- pgvector similarity search for relevant prior messages
- Keyword fallback when embeddings aren't populated
- Agent-scoped queries (only search agent's own sessions)
- Token budget awareness (stays within context window)
- Automatic embedding generation for new messages
- Configurable relevance threshold and result limits
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import litellm
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from aria_engine.config import EngineConfig
from aria_engine.exceptions import EngineError

logger = logging.getLogger("aria.engine.cross_session")

# Configuration
EMBEDDING_MODEL = "text-embedding-3-small"  # OpenAI, 1536 dimensions
EMBEDDING_DIMENSIONS = 1536
DEFAULT_MAX_RESULTS = 10
DEFAULT_SIMILARITY_THRESHOLD = 0.65  # Cosine similarity minimum
DEFAULT_MAX_TOKENS = 2000
APPROX_CHARS_PER_TOKEN = 4

# Keyword fallback config
KEYWORD_MIN_LENGTH = 3
KEYWORD_MAX_RESULTS = 20


async def generate_embedding(
    text_content: str,
    model: str = EMBEDDING_MODEL,
) -> List[float]:
    """
    Generate embedding vector for text using litellm.

    Args:
        text_content: Text to embed.
        model: Embedding model name.

    Returns:
        List of floats (1536 dimensions for text-embedding-3-small).

    Raises:
        EngineError: If embedding generation fails.
    """
    try:
        # Truncate to embedding model's context limit (~8191 tokens)
        truncated = text_content[:32000]

        response = await litellm.aembedding(
            model=model,
            input=[truncated],
        )

        return response.data[0]["embedding"]
    except Exception as e:
        logger.error("Embedding generation failed: %s", e)
        raise EngineError(f"Embedding generation failed: {e}") from e


class CrossSessionContext:
    """
    Retrieves relevant context from prior sessions using semantic search.

    Uses pgvector for approximate nearest neighbor search on message
    embeddings, with keyword fallback for messages without embeddings.

    Usage:
        ctx = CrossSessionContext(db_engine)

        # Get relevant context for a new message
        context = await ctx.load_context(
            agent_id="aria-devops",
            query="How did we configure the Docker deployment?",
            max_tokens=2000,
        )
        # context["messages"] → list of relevant prior messages
        # context["source"] → "vector" or "keyword"

        # Embed a new message for future retrieval
        await ctx.embed_message(message_id=42)

        # Batch embed unembedded messages
        count = await ctx.backfill_embeddings(batch_size=100)
    """

    def __init__(self, db_engine: AsyncEngine):
        self._db = db_engine
        self._embedding_available: Optional[bool] = None

    async def load_context(
        self,
        agent_id: str,
        query: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        max_results: int = DEFAULT_MAX_RESULTS,
        threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        exclude_session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Load relevant cross-session context for a query.

        Tries pgvector similarity search first. Falls back to keyword
        search if embeddings aren't populated.

        Args:
            agent_id: Agent to search history for.
            query: The query or message to find context for.
            max_tokens: Max approximate tokens to include.
            max_results: Max messages to return.
            threshold: Minimum cosine similarity score.
            exclude_session_id: Session to exclude (current session).

        Returns:
            Dict with 'messages', 'source', 'token_estimate'.
        """
        # Try vector search first
        if await self._has_embeddings(agent_id):
            try:
                embedding = await generate_embedding(query)
                messages = await self._vector_search(
                    agent_id=agent_id,
                    embedding=embedding,
                    max_results=max_results,
                    threshold=threshold,
                    exclude_session_id=exclude_session_id,
                )
                if messages:
                    messages = self._trim_to_token_budget(
                        messages, max_tokens
                    )
                    return {
                        "messages": messages,
                        "source": "vector",
                        "token_estimate": self._estimate_tokens(
                            messages
                        ),
                        "count": len(messages),
                    }
            except EngineError:
                logger.warning(
                    "Vector search failed for %s, falling back to keyword",
                    agent_id,
                )

        # Keyword fallback
        messages = await self._keyword_search(
            agent_id=agent_id,
            query=query,
            max_results=max_results,
            exclude_session_id=exclude_session_id,
        )
        messages = self._trim_to_token_budget(messages, max_tokens)

        return {
            "messages": messages,
            "source": "keyword",
            "token_estimate": self._estimate_tokens(messages),
            "count": len(messages),
        }

    async def _vector_search(
        self,
        agent_id: str,
        embedding: List[float],
        max_results: int,
        threshold: float,
        exclude_session_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Search using pgvector cosine similarity."""
        exclude_clause = ""
        params: Dict[str, Any] = {
            "agent_id": agent_id,
            "embedding": str(embedding),
            "threshold": threshold,
            "limit": max_results,
        }

        if exclude_session_id:
            exclude_clause = "AND m.session_id != :exclude_sid"
            params["exclude_sid"] = exclude_session_id

        async with self._db.begin() as conn:
            result = await conn.execute(
                text(f"""
                    SELECT
                        m.id,
                        m.session_id,
                        m.role,
                        m.content,
                        m.agent_id,
                        m.created_at,
                        s.title AS session_title,
                        1 - (m.embedding <=> :embedding::vector)
                            AS similarity
                    FROM aria_engine.chat_messages m
                    JOIN aria_engine.chat_sessions s
                        ON s.session_id = m.session_id
                    WHERE m.agent_id = :agent_id
                      AND m.embedding IS NOT NULL
                      AND 1 - (m.embedding <=> :embedding::vector)
                          > :threshold
                      {exclude_clause}
                    ORDER BY m.embedding <=> :embedding::vector
                    LIMIT :limit
                """),
                params,
            )
            rows = result.mappings().all()

        return [
            {
                "id": row["id"],
                "session_id": row["session_id"],
                "session_title": row["session_title"],
                "role": row["role"],
                "content": row["content"],
                "agent_id": row["agent_id"],
                "similarity": round(float(row["similarity"]), 3),
                "created_at": row["created_at"].isoformat(),
            }
            for row in rows
        ]

    async def _keyword_search(
        self,
        agent_id: str,
        query: str,
        max_results: int,
        exclude_session_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Fallback keyword search using ILIKE."""
        # Extract meaningful keywords
        keywords = [
            w
            for w in query.split()
            if len(w) >= KEYWORD_MIN_LENGTH
            and w.lower()
            not in {
                "the", "and", "for", "are", "but", "not",
                "you", "all", "can", "had", "her", "was",
                "one", "our", "out", "has", "its", "how",
                "did", "get", "use", "what", "when", "who",
                "will", "with", "this", "that", "from",
                "they", "been", "have", "many", "some",
                "them", "than", "each", "make", "like",
                "does", "into", "over", "such", "after",
                "could", "about", "would", "should",
            }
        ]

        if not keywords:
            return []

        # Build OR conditions for each keyword
        conditions = []
        params: Dict[str, Any] = {
            "agent_id": agent_id,
            "limit": max_results,
        }
        for i, kw in enumerate(keywords[:5]):  # Max 5 keywords
            conditions.append(f"m.content ILIKE :kw{i}")
            params[f"kw{i}"] = f"%{kw}%"

        where_keywords = " OR ".join(conditions)

        exclude_clause = ""
        if exclude_session_id:
            exclude_clause = "AND m.session_id != :exclude_sid"
            params["exclude_sid"] = exclude_session_id

        async with self._db.begin() as conn:
            result = await conn.execute(
                text(f"""
                    SELECT
                        m.id,
                        m.session_id,
                        m.role,
                        m.content,
                        m.agent_id,
                        m.created_at,
                        s.title AS session_title
                    FROM aria_engine.chat_messages m
                    JOIN aria_engine.chat_sessions s
                        ON s.session_id = m.session_id
                    WHERE m.agent_id = :agent_id
                      AND ({where_keywords})
                      {exclude_clause}
                    ORDER BY m.created_at DESC
                    LIMIT :limit
                """),
                params,
            )
            rows = result.mappings().all()

        return [
            {
                "id": row["id"],
                "session_id": row["session_id"],
                "session_title": row["session_title"],
                "role": row["role"],
                "content": row["content"],
                "agent_id": row["agent_id"],
                "similarity": None,  # Not available for keyword search
                "created_at": row["created_at"].isoformat(),
            }
            for row in rows
        ]

    async def embed_message(
        self,
        message_id: int,
    ) -> bool:
        """
        Generate and store embedding for a single message.

        Args:
            message_id: ID of the message to embed.

        Returns:
            True if embedding was stored successfully.
        """
        async with self._db.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT id, content
                    FROM aria_engine.chat_messages
                    WHERE id = :mid AND embedding IS NULL
                """),
                {"mid": message_id},
            )
            row = result.mappings().first()

        if not row:
            return False  # Already embedded or not found

        try:
            embedding = await generate_embedding(row["content"])
        except EngineError:
            return False

        async with self._db.begin() as conn:
            await conn.execute(
                text("""
                    UPDATE aria_engine.chat_messages
                    SET embedding = :emb::vector
                    WHERE id = :mid
                """),
                {"mid": message_id, "emb": str(embedding)},
            )

        return True

    async def backfill_embeddings(
        self,
        batch_size: int = 50,
        agent_id: Optional[str] = None,
    ) -> int:
        """
        Backfill embeddings for messages that don't have one.

        Processes up to batch_size messages per call. Designed to be
        called repeatedly by the scheduler until all messages are
        embedded.

        Args:
            batch_size: Max messages to process per call.
            agent_id: Optionally restrict to one agent.

        Returns:
            Number of messages successfully embedded.
        """
        agent_filter = ""
        params: Dict[str, Any] = {"limit": batch_size}
        if agent_id:
            agent_filter = "AND agent_id = :agent_id"
            params["agent_id"] = agent_id

        async with self._db.begin() as conn:
            result = await conn.execute(
                text(f"""
                    SELECT id, content
                    FROM aria_engine.chat_messages
                    WHERE embedding IS NULL
                      AND LENGTH(content) > 20
                      {agent_filter}
                    ORDER BY created_at DESC
                    LIMIT :limit
                """),
                params,
            )
            rows = result.mappings().all()

        if not rows:
            return 0

        embedded = 0
        for row in rows:
            try:
                emb = await generate_embedding(row["content"])
                async with self._db.begin() as conn:
                    await conn.execute(
                        text("""
                            UPDATE aria_engine.chat_messages
                            SET embedding = :emb::vector
                            WHERE id = :mid
                        """),
                        {"mid": row["id"], "emb": str(emb)},
                    )
                embedded += 1
            except Exception as e:
                logger.warning(
                    "Failed to embed message %d: %s", row["id"], e
                )

        logger.info(
            "Backfilled %d/%d embeddings%s",
            embedded,
            len(rows),
            f" for {agent_id}" if agent_id else "",
        )

        return embedded

    async def _has_embeddings(self, agent_id: str) -> bool:
        """Check if any messages for this agent have embeddings."""
        async with self._db.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT EXISTS (
                        SELECT 1 FROM aria_engine.chat_messages
                        WHERE agent_id = :agent_id
                          AND embedding IS NOT NULL
                        LIMIT 1
                    ) AS has_emb
                """),
                {"agent_id": agent_id},
            )
            return result.scalar()

    def _trim_to_token_budget(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: int,
    ) -> List[Dict[str, Any]]:
        """Trim messages to fit within a token budget."""
        result = []
        used_tokens = 0

        for msg in messages:
            content = msg.get("content", "")
            msg_tokens = len(content) // APPROX_CHARS_PER_TOKEN
            if used_tokens + msg_tokens > max_tokens:
                # Truncate this message to fit
                remaining_tokens = max_tokens - used_tokens
                remaining_chars = remaining_tokens * APPROX_CHARS_PER_TOKEN
                if remaining_chars > 100:
                    msg = {**msg, "content": content[:remaining_chars] + "..."}
                    result.append(msg)
                break
            result.append(msg)
            used_tokens += msg_tokens

        return result

    def _estimate_tokens(
        self,
        messages: List[Dict[str, Any]],
    ) -> int:
        """Estimate total tokens across messages."""
        return sum(
            len(m.get("content", "")) // APPROX_CHARS_PER_TOKEN
            for m in messages
        )


# ── pgvector index (add via Alembic migration) ───────────────
_VECTOR_INDEX_SQL = """
-- Approximate nearest neighbor index for embedding search
-- Using IVFFlat for good balance of speed vs accuracy
CREATE INDEX IF NOT EXISTS idx_chat_messages_embedding
    ON aria_engine.chat_messages
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Partial index for non-null embeddings
CREATE INDEX IF NOT EXISTS idx_chat_messages_agent_embedding
    ON aria_engine.chat_messages (agent_id)
    WHERE embedding IS NOT NULL;
"""
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Cross-session at engine infrastructure layer |
| 2 | .env for secrets (zero in code) | ✅ | OPENAI_API_KEY for embeddings via litellm |
| 3 | models.yaml single source of truth | ⚠️ | Embedding model hardcoded — consider adding to models.yaml |
| 4 | Docker-first testing | ✅ | Requires PostgreSQL with pgvector extension |
| 5 | aria_memories only writable path | ❌ | Embeddings stored in DB |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S5-01 (NativeSessionManager — chat_messages table)
- S1-01 (DB Schema — embedding VECTOR(1536) column)
- S1-05 (Alembic — pgvector extension and IVFFlat index)
- litellm (embedding generation)

## Verification
```bash
# 1. Module imports:
python -c "
from aria_engine.cross_session import CrossSessionContext, generate_embedding
print('OK')
"
# EXPECTED: OK

# 2. Token estimation:
python -c "
from aria_engine.cross_session import CrossSessionContext
ctx = CrossSessionContext.__new__(CrossSessionContext)
msgs = [{'content': 'A' * 400}, {'content': 'B' * 400}]
est = ctx._estimate_tokens(msgs)
print(f'Estimated tokens: {est}')  # ~200
"
# EXPECTED: Estimated tokens: 200

# 3. Token trimming:
python -c "
from aria_engine.cross_session import CrossSessionContext
ctx = CrossSessionContext.__new__(CrossSessionContext)
msgs = [
    {'content': 'A' * 4000},  # ~1000 tokens
    {'content': 'B' * 4000},  # ~1000 tokens
    {'content': 'C' * 4000},  # ~1000 tokens
]
trimmed = ctx._trim_to_token_budget(msgs, 1500)
print(f'Messages in budget: {len(trimmed)}')  # 2
"
# EXPECTED: Messages in budget: 2

# 4. Vector index SQL:
python -c "
from aria_engine.cross_session import _VECTOR_INDEX_SQL
assert 'ivfflat' in _VECTOR_INDEX_SQL
assert 'vector_cosine_ops' in _VECTOR_INDEX_SQL
print('Vector indexes OK')
"
# EXPECTED: Vector indexes OK
```

## Prompt for Agent
```
Add cross-session context retrieval using pgvector similarity search.

FILES TO READ FIRST:
- MASTER_PLAN.md (lines 133-135 — chat_messages.embedding VECTOR(1536))
- aria_engine/session_manager.py (S5-01 — message storage)
- aria_agents/coordinator.py (lines 300-340 — existing context building)
- aria_models/loader.py (litellm configuration patterns)

STEPS:
1. Read all files above
2. Create aria_engine/cross_session.py
3. Implement generate_embedding() using litellm.aembedding()
4. Implement CrossSessionContext class
5. load_context() — try vector first, keyword fallback
6. _vector_search() — pgvector cosine similarity with threshold
7. _keyword_search() — ILIKE fallback with stopword filtering
8. embed_message() — generate + store embedding for one message
9. backfill_embeddings() — batch process unembedded messages
10. _trim_to_token_budget() — stay within context window
11. Include IVFFlat index DDL in _VECTOR_INDEX_SQL
12. Run verification commands

CONSTRAINTS:
- Embedding model: text-embedding-3-small (1536 dimensions)
- Similarity threshold: 0.65 cosine minimum
- Token budget: 2000 tokens default, ~4 chars per token estimate
- Keyword fallback: max 5 keywords, skip stopwords
- IVFFlat index with lists=100 for ANN performance
- Agent-scoped: only search agent's own session history
- Exclude current session from results
```
