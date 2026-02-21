# S4-05: Engine Roundtable Discussion
**Epic:** E3 — Agent Pool | **Priority:** P1 | **Points:** 5 | **Phase:** 3

## Problem
The existing `AgentCoordinator.roundtable()` in `aria_agents/coordinator.py` (lines 460-530) runs multi-agent collaborative discussions but uses in-memory `LLMAgent` instances and filesystem logging. The engine needs a native `Roundtable` class in `aria_engine/roundtable.py` that uses the `AgentPool` (S4-01), `EngineRouter` (S4-04), and `AgentSessionScope` (S4-02) for proper isolation, with all discussion turns persisted to `chat_messages` under a shared roundtable session.

Reference: `aria_agents/coordinator.py` roundtable() does 3-round discussion with explore→work→validate cycle, broadcasts topic to participants, gathers responses, and uses a synthesizer to produce the final answer.

## Root Cause
The coordinator's roundtable is monolithic — it creates throwaway LLMAgent objects, doesn't persist discussion turns, has no timeout handling, and doesn't benefit from pheromone routing. The engine's roundtable should leverage properly pooled agents with session isolation, persist every turn for auditability, and handle timeouts gracefully so a slow agent doesn't block the whole discussion.

## Fix
### `aria_engine/roundtable.py`
```python
"""
Engine Roundtable — multi-agent collaborative discussion.

Ports roundtable logic from aria_agents/coordinator.py with:
- Proper agent pool integration (S4-01)
- Session isolation per roundtable (S4-02)
- All turns persisted to chat_messages
- Per-agent timeout handling
- Pheromone score updates after each contribution
- Configurable rounds, timeout, and synthesis
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from aria_engine.agent_pool import AgentPool
from aria_engine.config import EngineConfig
from aria_engine.exceptions import EngineError
from aria_engine.routing import EngineRouter
from aria_engine.session_isolation import AgentSessionScope

logger = logging.getLogger("aria.engine.roundtable")

# Defaults
DEFAULT_ROUNDS = 3
DEFAULT_AGENT_TIMEOUT = 60  # seconds per agent per round
DEFAULT_TOTAL_TIMEOUT = 300  # seconds for entire roundtable
MAX_CONTEXT_TOKENS = 2000   # Approx tokens to include from prior turns


@dataclass
class RoundtableTurn:
    """A single turn in a roundtable discussion."""

    agent_id: str
    round_number: int
    content: str
    duration_ms: int
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class RoundtableResult:
    """Complete result of a roundtable discussion."""

    session_id: str
    topic: str
    participants: List[str]
    rounds: int
    turns: List[RoundtableTurn]
    synthesis: str
    synthesizer_id: str
    total_duration_ms: int
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def turn_count(self) -> int:
        return len(self.turns)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "topic": self.topic,
            "participants": self.participants,
            "rounds": self.rounds,
            "turn_count": self.turn_count,
            "synthesis": self.synthesis,
            "synthesizer_id": self.synthesizer_id,
            "total_duration_ms": self.total_duration_ms,
            "created_at": self.created_at.isoformat(),
            "turns": [
                {
                    "agent_id": t.agent_id,
                    "round": t.round_number,
                    "content": t.content[:200] + "..."
                    if len(t.content) > 200
                    else t.content,
                    "duration_ms": t.duration_ms,
                }
                for t in self.turns
            ],
        }


class Roundtable:
    """
    Multi-agent collaborative discussion engine.

    Orchestrates a structured discussion where multiple agents
    contribute to a topic across several rounds, with each agent
    seeing prior responses for context. A synthesizer agent
    produces the final combined answer.

    Usage:
        roundtable = Roundtable(db_engine, agent_pool, router)

        result = await roundtable.discuss(
            topic="Design the new caching strategy",
            agent_ids=["aria-devops", "aria-analyst", "aria-creator"],
            rounds=3,
            synthesizer_id="main",
        )
        # result.synthesis contains the final combined answer
        # result.turns contains all individual contributions
    """

    def __init__(
        self,
        db_engine: AsyncEngine,
        agent_pool: AgentPool,
        router: EngineRouter,
    ):
        self._db_engine = db_engine
        self._pool = agent_pool
        self._router = router

    async def discuss(
        self,
        topic: str,
        agent_ids: List[str],
        rounds: int = DEFAULT_ROUNDS,
        synthesizer_id: str = "main",
        agent_timeout: int = DEFAULT_AGENT_TIMEOUT,
        total_timeout: int = DEFAULT_TOTAL_TIMEOUT,
    ) -> RoundtableResult:
        """
        Run a multi-round collaborative discussion.

        Each round sends the topic + prior context to each agent.
        After all rounds, a synthesizer agent combines the insights.

        Args:
            topic: Discussion topic / question.
            agent_ids: List of agents to participate.
            rounds: Number of discussion rounds (default 3).
            synthesizer_id: Agent to produce the final synthesis.
            agent_timeout: Seconds per agent response (default 60).
            total_timeout: Max total seconds (default 300).

        Returns:
            RoundtableResult with all turns and final synthesis.

        Raises:
            EngineError: If fewer than 2 agents, or total timeout exceeded.
        """
        if len(agent_ids) < 2:
            raise EngineError(
                "Roundtable requires at least 2 participants"
            )

        start = time.monotonic()
        session_id = f"roundtable-{uuid4().hex[:12]}"

        # Create a roundtable session in the DB
        await self._create_session(session_id, topic, agent_ids)

        logger.info(
            "Roundtable started: '%s' with %s (%d rounds)",
            topic[:80],
            agent_ids,
            rounds,
        )

        turns: List[RoundtableTurn] = []

        for round_num in range(1, rounds + 1):
            # Check total timeout
            elapsed = time.monotonic() - start
            if elapsed > total_timeout:
                logger.warning(
                    "Roundtable total timeout after round %d (%.0fs)",
                    round_num - 1,
                    elapsed,
                )
                break

            remaining = total_timeout - elapsed
            round_timeout = min(
                agent_timeout * len(agent_ids),
                remaining,
            )

            round_turns = await self._run_round(
                session_id=session_id,
                topic=topic,
                agent_ids=agent_ids,
                round_number=round_num,
                prior_turns=turns,
                agent_timeout=agent_timeout,
                round_timeout=round_timeout,
            )
            turns.extend(round_turns)

        # Synthesis round
        elapsed = time.monotonic() - start
        if elapsed < total_timeout:
            synthesis, synth_ms = await self._synthesize(
                session_id=session_id,
                topic=topic,
                turns=turns,
                synthesizer_id=synthesizer_id,
                timeout=min(agent_timeout * 2, total_timeout - elapsed),
            )
        else:
            synthesis = self._fallback_synthesis(turns)
            synth_ms = 0

        total_ms = int((time.monotonic() - start) * 1000)

        result = RoundtableResult(
            session_id=session_id,
            topic=topic,
            participants=agent_ids,
            rounds=rounds,
            turns=turns,
            synthesis=synthesis,
            synthesizer_id=synthesizer_id,
            total_duration_ms=total_ms,
        )

        # Persist synthesis as final message
        await self._persist_message(
            session_id, synthesizer_id, synthesis, "synthesis"
        )

        # Update pheromone scores for all participants
        for agent_id in agent_ids:
            agent_turns = [
                t for t in turns if t.agent_id == agent_id
            ]
            if agent_turns:
                avg_ms = sum(t.duration_ms for t in agent_turns) // len(
                    agent_turns
                )
                await self._router.update_scores(
                    agent_id=agent_id,
                    success=True,
                    duration_ms=avg_ms,
                )

        logger.info(
            "Roundtable complete: %d turns, %d agents, %.1fs",
            len(turns),
            len(agent_ids),
            total_ms / 1000,
        )

        return result

    async def _run_round(
        self,
        session_id: str,
        topic: str,
        agent_ids: List[str],
        round_number: int,
        prior_turns: List[RoundtableTurn],
        agent_timeout: int,
        round_timeout: float,
    ) -> List[RoundtableTurn]:
        """Run one round of discussion, collecting all agent responses."""
        context = self._build_context(prior_turns)

        prompt = self._build_round_prompt(
            topic, round_number, context, len(agent_ids)
        )

        tasks = []
        for agent_id in agent_ids:
            tasks.append(
                self._get_agent_response(
                    session_id=session_id,
                    agent_id=agent_id,
                    prompt=prompt,
                    round_number=round_number,
                    timeout=agent_timeout,
                )
            )

        # Run all agents in parallel with round-level timeout
        turns: List[RoundtableTurn] = []
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=round_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Round %d timed out after %.0fs",
                round_number,
                round_timeout,
            )
            results = []

        for r in results:
            if isinstance(r, RoundtableTurn):
                turns.append(r)
            elif isinstance(r, Exception):
                logger.warning("Agent response error: %s", r)

        logger.debug(
            "Round %d: %d/%d responses",
            round_number,
            len(turns),
            len(agent_ids),
        )

        return turns

    async def _get_agent_response(
        self,
        session_id: str,
        agent_id: str,
        prompt: str,
        round_number: int,
        timeout: int,
    ) -> RoundtableTurn:
        """Get a single agent's response with timeout."""
        start = time.monotonic()

        try:
            response = await asyncio.wait_for(
                self._pool.process_with_agent(
                    agent_id=agent_id,
                    message=prompt,
                    session_id=session_id,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            response = f"[{agent_id} timed out after {timeout}s]"
        except Exception as e:
            response = f"[{agent_id} error: {e}]"
            logger.warning("Agent %s failed in round %d: %s", agent_id, round_number, e)

        duration_ms = int((time.monotonic() - start) * 1000)

        turn = RoundtableTurn(
            agent_id=agent_id,
            round_number=round_number,
            content=response,
            duration_ms=duration_ms,
        )

        # Persist to DB
        await self._persist_message(
            session_id,
            agent_id,
            response,
            f"round-{round_number}",
        )

        return turn

    async def _synthesize(
        self,
        session_id: str,
        topic: str,
        turns: List[RoundtableTurn],
        synthesizer_id: str,
        timeout: float,
    ) -> tuple[str, int]:
        """
        Synthesize all discussion turns into a final answer.

        Returns:
            Tuple of (synthesis text, duration_ms).
        """
        context = self._build_context(turns, max_per_agent=500)

        prompt = (
            f"You are the synthesizer for a roundtable discussion.\n\n"
            f"TOPIC: {topic}\n\n"
            f"DISCUSSION ({len(turns)} contributions from "
            f"{len(set(t.agent_id for t in turns))} agents):\n\n"
            f"{context}\n\n"
            f"TASK: Synthesize the key insights into a coherent, "
            f"actionable answer. Highlight areas of agreement and "
            f"note any important disagreements. Be concise but thorough."
        )

        start = time.monotonic()
        try:
            synthesis = await asyncio.wait_for(
                self._pool.process_with_agent(
                    agent_id=synthesizer_id,
                    message=prompt,
                    session_id=session_id,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            synthesis = self._fallback_synthesis(turns)
        except Exception as e:
            logger.error("Synthesis failed: %s", e)
            synthesis = self._fallback_synthesis(turns)

        duration_ms = int((time.monotonic() - start) * 1000)
        return synthesis, duration_ms

    def _build_context(
        self,
        turns: List[RoundtableTurn],
        max_per_agent: int = 300,
    ) -> str:
        """Build context string from prior turns."""
        if not turns:
            return "(No prior discussion)"

        lines = []
        for t in turns:
            content = t.content
            if len(content) > max_per_agent:
                content = content[:max_per_agent] + "..."
            lines.append(
                f"[Round {t.round_number}] {t.agent_id}: {content}"
            )

        return "\n\n".join(lines)

    def _build_round_prompt(
        self,
        topic: str,
        round_number: int,
        context: str,
        participant_count: int,
    ) -> str:
        """Build the prompt for a discussion round."""
        if round_number == 1:
            phase = "EXPLORE — Share your initial analysis"
        elif round_number == 2:
            phase = "WORK — Build on others' ideas"
        else:
            phase = "VALIDATE — Critique and refine"

        return (
            f"ROUNDTABLE DISCUSSION (Round {round_number}, Phase: {phase})\n"
            f"Participants: {participant_count} agents\n\n"
            f"TOPIC: {topic}\n\n"
            f"PRIOR DISCUSSION:\n{context}\n\n"
            f"YOUR TURN: Contribute your perspective. "
            f"{'Introduce your analysis.' if round_number == 1 else ''}"
            f"{'Build on what others said.' if round_number == 2 else ''}"
            f"{'Identify gaps and finalize.' if round_number >= 3 else ''}"
        )

    def _fallback_synthesis(self, turns: List[RoundtableTurn]) -> str:
        """Fallback synthesis when the synthesizer agent fails."""
        if not turns:
            return "(No discussion content to synthesize)"

        agents = set(t.agent_id for t in turns)
        last_round = max(t.round_number for t in turns)
        final_turns = [t for t in turns if t.round_number == last_round]

        parts = [
            f"[Auto-synthesis from {len(turns)} turns, "
            f"{len(agents)} agents, {last_round} rounds]\n"
        ]
        for t in final_turns:
            parts.append(f"• {t.agent_id}: {t.content[:300]}")

        return "\n".join(parts)

    async def _create_session(
        self,
        session_id: str,
        topic: str,
        agent_ids: List[str],
    ) -> None:
        """Create a roundtable session in the DB."""
        title = f"Roundtable: {topic[:100]}"
        async with self._db_engine.begin() as conn:
            await conn.execute(
                text("""
                    INSERT INTO aria_engine.chat_sessions
                        (session_id, title, agent_id, session_type, metadata)
                    VALUES
                        (:sid, :title, :agent, 'roundtable',
                         :meta::jsonb)
                """),
                {
                    "sid": session_id,
                    "title": title,
                    "agent": "roundtable",
                    "meta": (
                        '{"participants": '
                        + str(agent_ids).replace("'", '"')
                        + "}"
                    ),
                },
            )

    async def _persist_message(
        self,
        session_id: str,
        agent_id: str,
        content: str,
        role: str,
    ) -> None:
        """Persist a roundtable message to chat_messages."""
        async with self._db_engine.begin() as conn:
            await conn.execute(
                text("""
                    INSERT INTO aria_engine.chat_messages
                        (session_id, role, content, agent_id)
                    VALUES
                        (:sid, :role, :content, :agent)
                """),
                {
                    "sid": session_id,
                    "role": role,
                    "content": content,
                    "agent": agent_id,
                },
            )

    async def list_roundtables(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List recent roundtable sessions."""
        async with self._db_engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT s.session_id, s.title, s.metadata,
                           s.created_at,
                           COUNT(m.id) AS message_count
                    FROM aria_engine.chat_sessions s
                    LEFT JOIN aria_engine.chat_messages m
                        ON m.session_id = s.session_id
                    WHERE s.session_type = 'roundtable'
                    GROUP BY s.session_id, s.title, s.metadata,
                             s.created_at
                    ORDER BY s.created_at DESC
                    LIMIT :limit OFFSET :offset
                """),
                {"limit": limit, "offset": offset},
            )
            rows = result.mappings().all()

        return [
            {
                "session_id": row["session_id"],
                "title": row["title"],
                "participants": (row["metadata"] or {}).get(
                    "participants", []
                ),
                "message_count": row["message_count"],
                "created_at": row["created_at"].isoformat(),
            }
            for row in rows
        ]
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Roundtable at engine orchestration layer |
| 2 | .env for secrets (zero in code) | ✅ | DATABASE_URL from config |
| 3 | models.yaml single source of truth | ❌ | LLM calls through agent_pool.process_with_agent() |
| 4 | Docker-first testing | ✅ | Requires PostgreSQL for session persistence |
| 5 | aria_memories only writable path | ❌ | All state in DB |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S4-01 (AgentPool — `process_with_agent()`)
- S4-02 (Session Isolation — `AgentSessionScope`)
- S4-04 (Pheromone Routing — `EngineRouter.update_scores()`)

## Verification
```bash
# 1. Module imports:
python -c "
from aria_engine.roundtable import Roundtable, RoundtableResult, RoundtableTurn
print('OK')
"
# EXPECTED: OK

# 2. Prompt building:
python -c "
from aria_engine.roundtable import Roundtable
rt = Roundtable.__new__(Roundtable)
p = rt._build_round_prompt('Test topic', 1, '(No prior)', 3)
assert 'EXPLORE' in p
p2 = rt._build_round_prompt('Test topic', 2, 'prior context', 3)
assert 'WORK' in p2
p3 = rt._build_round_prompt('Test topic', 3, 'prior context', 3)
assert 'VALIDATE' in p3
print('Prompts OK')
"
# EXPECTED: Prompts OK

# 3. Context building:
python -c "
from aria_engine.roundtable import Roundtable, RoundtableTurn
rt = Roundtable.__new__(Roundtable)
turns = [
    RoundtableTurn('agent-a', 1, 'First thought', 100),
    RoundtableTurn('agent-b', 1, 'Second thought', 200),
]
ctx = rt._build_context(turns)
assert 'agent-a' in ctx and 'agent-b' in ctx
print('Context OK')
"
# EXPECTED: Context OK

# 4. Fallback synthesis:
python -c "
from aria_engine.roundtable import Roundtable, RoundtableTurn
rt = Roundtable.__new__(Roundtable)
turns = [
    RoundtableTurn('a', 1, 'Hello', 100),
    RoundtableTurn('b', 1, 'World', 200),
    RoundtableTurn('a', 2, 'Updated', 150),
]
s = rt._fallback_synthesis(turns)
assert 'Auto-synthesis' in s
print('Fallback OK')
"
# EXPECTED: Fallback OK
```

## Prompt for Agent
```
Port the roundtable discussion system from aria_agents to the Aria Engine.

FILES TO READ FIRST:
- aria_agents/coordinator.py (lines 460-530 — existing roundtable() implementation)
- aria_agents/coordinator.py (lines 200-260 — explore/work/validate cycle)
- aria_engine/agent_pool.py (S4-01 — AgentPool.process_with_agent())
- aria_engine/routing.py (S4-04 — EngineRouter.update_scores())
- aria_engine/session_isolation.py (S4-02 — AgentSessionScope)

STEPS:
1. Read all files above
2. Create aria_engine/roundtable.py
3. Implement RoundtableTurn and RoundtableResult dataclasses
4. Implement Roundtable class with discuss() as main entry point
5. Port the 3-phase cycle (explore→work→validate) as round prompts
6. Run agents in parallel with per-agent and total timeouts
7. Persist all turns to chat_messages under a shared roundtable session
8. Add synthesis step — synthesizer agent combines all insights
9. Update pheromone scores for all participants after discussion
10. Implement list_roundtables() for dashboard display
11. Run verification commands

CONSTRAINTS:
- Session type must be 'roundtable' in chat_sessions
- Each turn persisted as a chat_message with role = 'round-N'
- Minimum 2 participants required
- Total timeout prevents runaway discussions
- Fallback synthesis if synthesizer agent fails
```
