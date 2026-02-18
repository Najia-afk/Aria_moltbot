# S2-02: Context Window Manager
**Epic:** E1 — Engine Core | **Priority:** P0 | **Points:** 5 | **Phase:** 2

## Problem
The LLM's context window is finite. When a conversation grows beyond the token budget, we need intelligent eviction — not just "drop the oldest." OpenClaw managed context opaquely; we have no control over which messages stay and which get dropped. We need a `ContextManager` that builds an optimal message list within a token budget, using importance scoring to decide what to keep.

Reference: `aria_mind/cognition.py` lines 240-260 (`_build_context`) simply appends the last 5 short-term memories — no token counting, no importance weighting, no sliding window.

## Root Cause
OpenClaw held the conversation history and fed it to the LLM, but the Python side never had visibility into token counts or the ability to influence which messages stayed in context. The `EngineChatSession.context_window` column (S1-05) stores the max number of messages, but there's no token-aware manager that respects model-specific limits. Without this, long conversations will either overflow the context (causing LLM errors) or truncate important early messages (losing identity/instructions).

## Fix
### `aria_engine/context_manager.py`
```python
"""
Context Window Manager — Sliding window with importance-based eviction.

Builds an optimal message list within a token budget by:
1. Always including: system prompt, first user message (establishes identity)
2. Always including: last N messages (recent context)
3. Scoring middle messages by importance and keeping highest-scored within budget
4. Token counting via litellm.token_counter (model-aware)

The goal: maximize context quality within the token budget.
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from aria_engine.config import EngineConfig

logger = logging.getLogger("aria.engine.context")


# ── Importance scores by role ─────────────────────────────────────────────────
# Higher = more important to keep in context
IMPORTANCE_SCORES: Dict[str, int] = {
    "system": 100,
    "tool": 80,
    "user": 60,
    "assistant": 40,
}

# Minimum number of recent messages to always include (tail)
MIN_RECENT_MESSAGES = 4

# Fallback tokens-per-message estimate when counting fails
FALLBACK_TOKENS_PER_MESSAGE = 150


@dataclass
class ScoredMessage:
    """A message with its importance score and token count."""
    index: int
    message: Dict[str, Any]
    role: str
    tokens: int
    importance: int
    is_pinned: bool = False  # pinned = must include (system, first msg, recent)

    @property
    def priority(self) -> Tuple[bool, int, int]:
        """Sort key: pinned first, then by importance, then by recency (index)."""
        return (self.is_pinned, self.importance, self.index)


class ContextManager:
    """
    Manages the conversation context window with token-aware eviction.

    Usage:
        ctx = ContextManager(config)

        # Build context from raw message list:
        messages = ctx.build_context(
            all_messages=full_history,
            max_tokens=8192,
            model="qwen3-30b-mlx",
        )

        # Or build from DB session:
        messages = await ctx.build_context_from_session(
            db=db_session,
            session_id=session_id,
            system_prompt="You are Aria...",
            max_tokens=8192,
            model="qwen3-30b-mlx",
        )
    """

    def __init__(self, config: EngineConfig):
        self.config = config

    def build_context(
        self,
        all_messages: List[Dict[str, Any]],
        max_tokens: int = 8192,
        model: str = "gpt-4",
        reserve_tokens: int = 1024,
    ) -> List[Dict[str, Any]]:
        """
        Build an optimal message list within the token budget.

        Args:
            all_messages: Full conversation history (list of {role, content, ...}).
            max_tokens: Maximum tokens allowed for the context window.
            model: Model name for accurate token counting.
            reserve_tokens: Tokens reserved for the model's response.

        Returns:
            Filtered and ordered list of messages fitting within the budget.
        """
        if not all_messages:
            return []

        budget = max_tokens - reserve_tokens
        if budget <= 0:
            logger.warning("Token budget <= 0 after reserve. Returning system prompt only.")
            return [m for m in all_messages if m.get("role") == "system"][:1]

        # ── Score and tokenize all messages ───────────────────────────────
        scored: List[ScoredMessage] = []
        for i, msg in enumerate(all_messages):
            role = msg.get("role", "user")
            tokens = self._count_tokens(msg, model)
            importance = self._compute_importance(msg, i, len(all_messages))
            is_pinned = self._is_pinned(msg, i, len(all_messages))

            scored.append(ScoredMessage(
                index=i,
                message=msg,
                role=role,
                tokens=tokens,
                importance=importance,
                is_pinned=is_pinned,
            ))

        # ── Phase 1: Always include pinned messages ───────────────────────
        pinned = [s for s in scored if s.is_pinned]
        unpinned = [s for s in scored if not s.is_pinned]

        pinned_tokens = sum(s.tokens for s in pinned)

        if pinned_tokens >= budget:
            # Even pinned messages exceed budget — include what fits
            logger.warning(
                "Pinned messages (%d tokens) exceed budget (%d). Truncating.",
                pinned_tokens, budget,
            )
            result: List[ScoredMessage] = []
            used = 0
            for s in pinned:
                if used + s.tokens <= budget:
                    result.append(s)
                    used += s.tokens
                else:
                    break
            result.sort(key=lambda s: s.index)
            return [s.message for s in result]

        # ── Phase 2: Fill remaining budget with highest-importance unpinned ─
        remaining_budget = budget - pinned_tokens
        unpinned.sort(key=lambda s: (s.importance, s.index), reverse=True)

        selected_unpinned: List[ScoredMessage] = []
        used_unpinned = 0
        for s in unpinned:
            if used_unpinned + s.tokens <= remaining_budget:
                selected_unpinned.append(s)
                used_unpinned += s.tokens

        # ── Phase 3: Combine and sort by original order ───────────────────
        final = pinned + selected_unpinned
        final.sort(key=lambda s: s.index)

        total_tokens = sum(s.tokens for s in final)
        logger.debug(
            "Context: %d/%d messages, %d/%d tokens (budget=%d, reserve=%d)",
            len(final), len(all_messages), total_tokens, max_tokens,
            budget, reserve_tokens,
        )

        return [s.message for s in final]

    async def build_context_from_session(
        self,
        db,
        session_id,
        system_prompt: Optional[str] = None,
        max_tokens: int = 8192,
        model: str = "gpt-4",
        reserve_tokens: int = 1024,
        max_messages: int = 200,
    ) -> List[Dict[str, Any]]:
        """
        Build context by loading messages from the database.

        Args:
            db: AsyncSession instance.
            session_id: UUID of the session.
            system_prompt: System prompt to prepend (if not already in DB).
            max_tokens: Token budget.
            model: Model for token counting.
            reserve_tokens: Tokens reserved for response.
            max_messages: Maximum messages to load from DB.

        Returns:
            Optimized message list.
        """
        from db.models import EngineChatMessage
        from sqlalchemy import select

        result = await db.execute(
            select(EngineChatMessage)
            .where(EngineChatMessage.session_id == session_id)
            .order_by(EngineChatMessage.created_at.asc())
            .limit(max_messages)
        )
        rows = result.scalars().all()

        all_messages: List[Dict[str, Any]] = []

        # Prepend system prompt if provided
        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})

        # Convert DB rows to message dicts
        for row in rows:
            msg: Dict[str, Any] = {"role": row.role, "content": row.content}
            if row.tool_calls:
                msg["tool_calls"] = row.tool_calls
            if row.role == "tool" and row.tool_results:
                msg["tool_call_id"] = row.tool_results.get("tool_call_id", "")
            all_messages.append(msg)

        return self.build_context(
            all_messages=all_messages,
            max_tokens=max_tokens,
            model=model,
            reserve_tokens=reserve_tokens,
        )

    def _count_tokens(self, message: Dict[str, Any], model: str) -> int:
        """
        Count tokens in a message using litellm's token counter.

        Falls back to a rough estimate if litellm fails.
        """
        try:
            from litellm import token_counter
            # litellm.token_counter expects a list of messages
            count = token_counter(model=model, messages=[message])
            return count
        except Exception:
            # Fallback: rough estimate (4 chars ≈ 1 token)
            content = message.get("content", "")
            if isinstance(content, str):
                return max(len(content) // 4, 1)
            return FALLBACK_TOKENS_PER_MESSAGE

    def _compute_importance(
        self, message: Dict[str, Any], index: int, total: int
    ) -> int:
        """
        Compute importance score for a message.

        Factors:
        - Role-based base score (system=100, tool=80, user=60, assistant=40)
        - Boost for messages with tool_calls or tool results (+20)
        - Boost for longer messages that contain substantive content (+10)
        - Recency boost for messages in the last quarter (+15)
        """
        role = message.get("role", "user")
        score = IMPORTANCE_SCORES.get(role, 30)

        # Boost tool-related messages (they carry execution context)
        if message.get("tool_calls") or message.get("tool_call_id"):
            score += 20

        # Boost substantive messages (>200 chars)
        content = message.get("content", "")
        if isinstance(content, str) and len(content) > 200:
            score += 10

        # Recency boost: last quarter of conversation gets +15
        if total > 0 and index >= total * 0.75:
            score += 15

        return score

    def _is_pinned(self, message: Dict[str, Any], index: int, total: int) -> bool:
        """
        Determine if a message must always be included.

        Pinned messages:
        - System prompt (role=system)
        - First user message (establishes identity/topic)
        - Last MIN_RECENT_MESSAGES messages (recent context)
        """
        role = message.get("role", "user")

        # System prompts are always pinned
        if role == "system":
            return True

        # First user message (establishes the conversation topic)
        if index == 0 or (index == 1 and role == "user"):
            return True

        # Last N messages are always pinned
        if total > 0 and index >= total - MIN_RECENT_MESSAGES:
            return True

        return False

    def estimate_tokens(
        self, messages: List[Dict[str, Any]], model: str = "gpt-4"
    ) -> int:
        """
        Estimate total tokens for a list of messages.

        Useful for checking whether a context fits before sending to LLM.
        """
        return sum(self._count_tokens(m, model) for m in messages)

    def get_window_stats(
        self, all_messages: List[Dict[str, Any]], model: str = "gpt-4"
    ) -> Dict[str, Any]:
        """
        Get statistics about the context window.

        Returns:
            Dict with total_messages, total_tokens, role_breakdown, etc.
        """
        role_counts: Dict[str, int] = {}
        role_tokens: Dict[str, int] = {}
        total_tokens = 0

        for msg in all_messages:
            role = msg.get("role", "unknown")
            tokens = self._count_tokens(msg, model)
            total_tokens += tokens
            role_counts[role] = role_counts.get(role, 0) + 1
            role_tokens[role] = role_tokens.get(role, 0) + tokens

        return {
            "total_messages": len(all_messages),
            "total_tokens": total_tokens,
            "role_counts": role_counts,
            "role_tokens": role_tokens,
        }
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | ContextManager accesses DB via ORM for build_context_from_session |
| 2 | .env for secrets (zero in code) | ❌ | No secrets — uses litellm token_counter only |
| 3 | models.yaml single source of truth | ✅ | Model name passed to token_counter for accurate counting |
| 4 | Docker-first testing | ✅ | Pure Python logic + litellm dependency |
| 5 | aria_memories only writable path | ❌ | No file writes — reads messages, returns list |
| 6 | No soul modification | ❌ | No soul access — receives system prompt as parameter |

## Dependencies
- S1-01 must complete first (aria_engine package)
- S1-05 must complete first (EngineChatMessage ORM model for build_context_from_session)
- S2-01 should complete first (ChatEngine._build_context calls ContextManager)

## Verification
```bash
# 1. Module imports:
python -c "from aria_engine.context_manager import ContextManager, ScoredMessage, IMPORTANCE_SCORES; print('OK')"
# EXPECTED: OK

# 2. Importance scoring:
python -c "
from aria_engine.context_manager import ContextManager, IMPORTANCE_SCORES
assert IMPORTANCE_SCORES['system'] == 100
assert IMPORTANCE_SCORES['tool'] == 80
assert IMPORTANCE_SCORES['user'] == 60
assert IMPORTANCE_SCORES['assistant'] == 40
print('Scores OK')
"
# EXPECTED: Scores OK

# 3. Context building with budget:
python -c "
from aria_engine.config import EngineConfig
from aria_engine.context_manager import ContextManager

ctx = ContextManager(EngineConfig())
messages = [
    {'role': 'system', 'content': 'You are Aria.'},
    {'role': 'user', 'content': 'Hello'},
    {'role': 'assistant', 'content': 'Hi there!'},
    {'role': 'user', 'content': 'How are you?'},
    {'role': 'assistant', 'content': 'I am good.'},
]
result = ctx.build_context(messages, max_tokens=4096, model='gpt-4')
assert len(result) <= 5
assert result[0]['role'] == 'system'
print(f'Context: {len(result)} messages')
"
# EXPECTED: Context: 5 messages

# 4. Pinning logic:
python -c "
from aria_engine.config import EngineConfig
from aria_engine.context_manager import ContextManager

ctx = ContextManager(EngineConfig())
# System is always pinned
assert ctx._is_pinned({'role': 'system', 'content': 'x'}, 0, 10) == True
# First message pinned
assert ctx._is_pinned({'role': 'user', 'content': 'x'}, 0, 10) == True
# Last messages pinned
assert ctx._is_pinned({'role': 'user', 'content': 'x'}, 9, 10) == True
# Middle message not pinned
assert ctx._is_pinned({'role': 'assistant', 'content': 'x'}, 3, 10) == False
print('Pinning OK')
"
# EXPECTED: Pinning OK
```

## Prompt for Agent
```
Implement the Context Window Manager — token-aware sliding window with importance-based eviction.

FILES TO READ FIRST:
- aria_engine/config.py (EngineConfig — created in S1-01)
- aria_engine/chat_engine.py (ChatEngine._build_context — created in S2-01, will be enhanced to use ContextManager)
- src/api/db/models.py (EngineChatMessage — created in S1-05)
- aria_mind/cognition.py (lines 240-260 — current context building for reference)

STEPS:
1. Read all files above
2. Create aria_engine/context_manager.py with ContextManager class
3. Implement build_context() — the core windowing algorithm:
   a. Score all messages (role-based + recency + tool boost)
   b. Pin system prompt, first user message, and last N messages
   c. Fill remaining budget with highest-importance unpinned messages
   d. Return messages in original order
4. Implement build_context_from_session() — DB-backed variant
5. Implement _count_tokens() — litellm.token_counter with fallback
6. Implement _compute_importance() and _is_pinned()
7. Implement estimate_tokens() and get_window_stats() utilities
8. Run verification commands

CONSTRAINTS:
- Use litellm.token_counter for model-aware counting, with len(content)//4 fallback
- IMPORTANCE_SCORES: system=100, tool=80, user=60, assistant=40
- Always pin: system prompt, first user message, last 4 messages
- Never modify messages — only filter and reorder
```
