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
from typing import Any

import litellm
from sqlalchemy import select, update, exists, literal, func, or_
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
) -> list[float]:
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
        self._embedding_available: bool | None = None

    async def load_context(
        self,
        agent_id: str,
        query: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        max_results: int = DEFAULT_MAX_RESULTS,
        threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        exclude_session_id: str | None = None,
    ) -> dict[str, Any]:
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
        embedding: list[float],
        max_results: int,
        threshold: float,
        exclude_session_id: str | None,
    ) -> list[dict[str, Any]]:
        """Search using pgvector cosine similarity."""
        from db.models import EngineChatMessage, EngineChatSession

        similarity = (
            literal(1) - EngineChatMessage.embedding.cosine_distance(embedding)
        ).label("similarity")

        query = (
            select(
                EngineChatMessage.id,
                EngineChatMessage.session_id,
                EngineChatMessage.role,
                EngineChatMessage.content,
                EngineChatMessage.agent_id,
                EngineChatMessage.created_at,
                EngineChatSession.title.label("session_title"),
                similarity,
            )
            .join(
                EngineChatSession,
                EngineChatSession.id == EngineChatMessage.session_id,
            )
            .where(
                EngineChatMessage.agent_id == agent_id,
                EngineChatMessage.embedding.isnot(None),
                (literal(1) - EngineChatMessage.embedding.cosine_distance(embedding)) > threshold,
            )
        )

        if exclude_session_id:
            query = query.where(
                EngineChatMessage.session_id != exclude_session_id
            )

        query = (
            query
            .order_by(EngineChatMessage.embedding.cosine_distance(embedding))
            .limit(max_results)
        )

        async with self._db.begin() as conn:
            result = await conn.execute(query)
            rows = result.all()

        return [
            {
                "id": row.id,
                "session_id": row.session_id,
                "session_title": row.session_title,
                "role": row.role,
                "content": row.content,
                "agent_id": row.agent_id,
                "similarity": round(float(row.similarity), 3),
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]

    async def _keyword_search(
        self,
        agent_id: str,
        query: str,
        max_results: int,
        exclude_session_id: str | None,
    ) -> list[dict[str, Any]]:
        """Fallback keyword search using ILIKE."""
        from db.models import EngineChatMessage, EngineChatSession

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
        conditions = [
            EngineChatMessage.content.ilike(f"%{kw}%")
            for kw in keywords[:5]  # Max 5 keywords
        ]

        stmt = (
            select(
                EngineChatMessage.id,
                EngineChatMessage.session_id,
                EngineChatMessage.role,
                EngineChatMessage.content,
                EngineChatMessage.agent_id,
                EngineChatMessage.created_at,
                EngineChatSession.title.label("session_title"),
            )
            .join(
                EngineChatSession,
                EngineChatSession.id == EngineChatMessage.session_id,
            )
            .where(
                EngineChatMessage.agent_id == agent_id,
                or_(*conditions),
            )
        )

        if exclude_session_id:
            stmt = stmt.where(
                EngineChatMessage.session_id != exclude_session_id
            )

        stmt = stmt.order_by(EngineChatMessage.created_at.desc()).limit(max_results)

        async with self._db.begin() as conn:
            result = await conn.execute(stmt)
            rows = result.all()

        return [
            {
                "id": row.id,
                "session_id": row.session_id,
                "session_title": row.session_title,
                "role": row.role,
                "content": row.content,
                "agent_id": row.agent_id,
                "similarity": None,  # Not available for keyword search
                "created_at": row.created_at.isoformat(),
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
        from db.models import EngineChatMessage

        async with self._db.begin() as conn:
            result = await conn.execute(
                select(EngineChatMessage.id, EngineChatMessage.content).where(
                    EngineChatMessage.id == message_id,
                    EngineChatMessage.embedding.is_(None),
                )
            )
            row = result.first()

        if not row:
            return False  # Already embedded or not found

        try:
            emb = await generate_embedding(row.content)
        except EngineError:
            return False

        async with self._db.begin() as conn:
            await conn.execute(
                update(EngineChatMessage)
                .where(EngineChatMessage.id == message_id)
                .values(embedding=emb)
            )

        return True

    async def backfill_embeddings(
        self,
        batch_size: int = 50,
        agent_id: str | None = None,
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
        from db.models import EngineChatMessage

        stmt = (
            select(EngineChatMessage.id, EngineChatMessage.content)
            .where(
                EngineChatMessage.embedding.is_(None),
                func.length(EngineChatMessage.content) > 20,
            )
        )
        if agent_id:
            stmt = stmt.where(EngineChatMessage.agent_id == agent_id)
        stmt = stmt.order_by(EngineChatMessage.created_at.desc()).limit(batch_size)

        async with self._db.begin() as conn:
            result = await conn.execute(stmt)
            rows = result.all()

        if not rows:
            return 0

        embedded = 0
        for row in rows:
            try:
                emb = await generate_embedding(row.content)
                async with self._db.begin() as conn:
                    await conn.execute(
                        update(EngineChatMessage)
                        .where(EngineChatMessage.id == row.id)
                        .values(embedding=emb)
                    )
                embedded += 1
            except Exception as e:
                logger.warning(
                    "Failed to embed message %d: %s", row.id, e
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
        from db.models import EngineChatMessage

        async with self._db.begin() as conn:
            result = await conn.execute(
                select(
                    exists().where(
                        EngineChatMessage.agent_id == agent_id,
                        EngineChatMessage.embedding.isnot(None),
                    )
                )
            )
            return result.scalar()

    def _trim_to_token_budget(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int,
    ) -> list[dict[str, Any]]:
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
        messages: list[dict[str, Any]],
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
