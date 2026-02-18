# S4-04: Agent Auto-Routing with Pheromone Scoring
**Epic:** E3 — Agent Pool | **Priority:** P0 | **Points:** 3 | **Phase:** 3

## Problem
The existing pheromone routing logic in `aria_agents/coordinator.py` and `aria_agents/scoring.py` works in-memory with JSON file persistence. The engine needs this ported to `aria_engine/routing.py` with database-backed pheromone scores stored in `engine_agent_state.pheromone_score`. The routing must factor in agent specialty match, current load, pheromone score, and recent success rate to pick the best agent for any message.

Reference: `aria_agents/scoring.py` (lines 1-286) defines `compute_pheromone()`, `select_best_agent()`, and `PerformanceTracker`. `aria_agents/coordinator.py` (lines 300-340) shows pheromone-based agent selection in `process()`. The `aria_engine.agent_state` table has `pheromone_score NUMERIC(5,3)` column.

## Root Cause
The scoring logic is file-based (`pheromone_scores.json` in `aria_memories/knowledge/`) and tightly coupled to `AgentCoordinator`. The engine needs scores persisted to PostgreSQL so they survive container restarts without filesystem dependencies, and the routing logic needs to consider factors the current implementation doesn't — like agent specialty matching and current load.

## Fix
### `aria_engine/routing.py`
```python
"""
Agent Auto-Routing — pheromone-based message routing.

Ports scoring logic from aria_agents/scoring.py to engine with DB persistence.
Features:
- Multi-factor routing: specialty match + load + pheromone + success rate
- Pheromone score update after each interaction (boost on success, decay on failure)
- Scores persisted to engine_agent_state.pheromone_score
- Cold start handling (new agents get neutral 0.500 score)
- Time-decay weighting (recent performance matters more)
"""
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from aria_engine.config import EngineConfig
from aria_engine.exceptions import EngineError

logger = logging.getLogger("aria.engine.routing")

# Scoring parameters (ported from aria_agents/scoring.py)
DECAY_FACTOR = 0.95          # Per-day decay
COLD_START_SCORE = 0.500     # Neutral starting score
MAX_RECORDS_PER_AGENT = 200  # History cap

# Routing weight factors
WEIGHTS = {
    "pheromone": 0.35,       # Overall pheromone score
    "specialty": 0.30,       # Specialty match for the message
    "load": 0.20,            # Current load (lower = better)
    "recency": 0.15,         # Recent success rate (last 10 interactions)
}

# Specialty keywords per focus type
SPECIALTY_PATTERNS: Dict[str, re.Pattern] = {
    "social": re.compile(
        r"(social|post|tweet|moltbook|community|engage|share|content)",
        re.IGNORECASE,
    ),
    "analysis": re.compile(
        r"(analy|metric|data|report|review|insight|trend|stat)",
        re.IGNORECASE,
    ),
    "devops": re.compile(
        r"(deploy|docker|server|ci|cd|build|test|infra|monitor|debug)",
        re.IGNORECASE,
    ),
    "creative": re.compile(
        r"(creat|write|art|story|design|brand|visual|content|blog)",
        re.IGNORECASE,
    ),
    "research": re.compile(
        r"(research|paper|study|learn|explore|investigate|knowledge)",
        re.IGNORECASE,
    ),
}


def compute_specialty_match(
    message: str,
    focus_type: Optional[str],
) -> float:
    """
    Compute how well a message matches an agent's specialty.

    Args:
        message: The input message.
        focus_type: Agent's focus type (e.g., 'social', 'analysis').

    Returns:
        Float 0.0-1.0 indicating match strength.
    """
    if not focus_type or focus_type not in SPECIALTY_PATTERNS:
        return 0.3  # Generalist agents get moderate match

    pattern = SPECIALTY_PATTERNS[focus_type]
    matches = len(pattern.findall(message))
    if matches == 0:
        return 0.1  # No match
    if matches == 1:
        return 0.6
    if matches == 2:
        return 0.8
    return 1.0  # Strong match


def compute_load_score(
    status: str,
    consecutive_failures: int,
) -> float:
    """
    Compute load score (higher = less loaded = better).

    Args:
        status: Agent status ('idle', 'busy', 'error', 'disabled').
        consecutive_failures: Number of consecutive failures.

    Returns:
        Float 0.0-1.0 (1.0 = idle and healthy).
    """
    if status == "disabled":
        return 0.0
    if status == "error":
        return 0.1
    if status == "busy":
        return 0.3

    # Idle — penalize for recent failures
    failure_penalty = min(consecutive_failures * 0.1, 0.5)
    return max(1.0 - failure_penalty, 0.2)


def compute_pheromone_score(records: List[Dict[str, Any]]) -> float:
    """
    Compute pheromone score from performance records.

    Ported from aria_agents/scoring.py compute_pheromone().

    Score formula: success_rate * 0.6 + speed_score * 0.3 + cost_score * 0.1
    With time-decay: DECAY_FACTOR^age_days per record.

    Args:
        records: List of performance records.

    Returns:
        Float score between 0.0 and 1.0.
    """
    if not records:
        return COLD_START_SCORE

    score = 0.0
    weight_sum = 0.0
    now = datetime.now(timezone.utc)

    for r in records:
        created = r.get("created_at", now)
        if isinstance(created, str):
            created = datetime.fromisoformat(
                created.replace("Z", "+00:00")
            )
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)

        age_days = max((now - created).total_seconds() / 86400, 0)
        decay = DECAY_FACTOR**age_days

        s = (
            float(r.get("success", False)) * 0.6
            + r.get("speed_score", 0.5) * 0.3
            + r.get("cost_score", 0.5) * 0.1
        )
        score += s * decay
        weight_sum += decay

    return score / weight_sum if weight_sum > 0 else COLD_START_SCORE


class EngineRouter:
    """
    Routes messages to the best available agent based on multi-factor scoring.

    Usage:
        router = EngineRouter(db_engine)
        best_agent_id = await router.route_message(
            message="Deploy the latest build",
            available_agents=["main", "aria-devops", "aria-talk"],
        )
        # → "aria-devops" (highest combined score)

        # After interaction:
        await router.update_scores(
            agent_id="aria-devops",
            success=True,
            duration_ms=1500,
        )
    """

    def __init__(self, db_engine: AsyncEngine):
        self._db_engine = db_engine
        # In-memory record cache per agent (synced to DB periodically)
        self._records: Dict[str, List[Dict[str, Any]]] = {}
        self._total_invocations = 0

    async def route_message(
        self,
        message: str,
        available_agents: List[str],
    ) -> str:
        """
        Route a message to the best available agent.

        Considers:
        1. Pheromone score (historical performance, time-decayed)
        2. Specialty match (how well message fits agent's focus)
        3. Load (current status and consecutive failures)
        4. Recency (last 10 interaction success rate)

        Args:
            message: The input message to route.
            available_agents: List of agent_ids to choose from.

        Returns:
            The agent_id of the best match.

        Raises:
            EngineError: If no agents are available.
        """
        if not available_agents:
            raise EngineError("No available agents for routing")

        if len(available_agents) == 1:
            return available_agents[0]

        # Load agent state from DB
        agent_states = await self._load_agent_states(available_agents)

        scores: Dict[str, float] = {}

        for agent_id in available_agents:
            state = agent_states.get(agent_id, {})

            # Factor 1: Pheromone score
            pheromone = float(state.get("pheromone_score", COLD_START_SCORE))

            # Factor 2: Specialty match
            focus_type = state.get("focus_type")
            specialty = compute_specialty_match(message, focus_type)

            # Factor 3: Load
            status = state.get("status", "idle")
            failures = state.get("consecutive_failures", 0)
            load = compute_load_score(status, failures)

            # Factor 4: Recency (last 10 interactions)
            records = self._records.get(agent_id, [])
            recent = records[-10:] if records else []
            if recent:
                recency = sum(
                    1 for r in recent if r.get("success")
                ) / len(recent)
            else:
                recency = 0.5  # Neutral for new agents

            # Combined score
            combined = (
                pheromone * WEIGHTS["pheromone"]
                + specialty * WEIGHTS["specialty"]
                + load * WEIGHTS["load"]
                + recency * WEIGHTS["recency"]
            )
            scores[agent_id] = combined

            logger.debug(
                "Route score %s: pheromone=%.3f specialty=%.3f "
                "load=%.3f recency=%.3f → combined=%.3f",
                agent_id, pheromone, specialty, load, recency, combined,
            )

        best = max(scores, key=scores.get)
        logger.info(
            "Routed message to %s (score=%.3f, runners-up: %s)",
            best,
            scores[best],
            ", ".join(
                f"{k}={v:.3f}"
                for k, v in sorted(
                    scores.items(), key=lambda x: x[1], reverse=True
                )
                if k != best
            )[:100],
        )

        return best

    async def update_scores(
        self,
        agent_id: str,
        success: bool,
        duration_ms: int,
        token_cost: float = 0.0,
    ) -> float:
        """
        Update pheromone scores after an interaction.

        Records the result, recomputes the agent's pheromone score,
        and persists to engine_agent_state.

        Args:
            agent_id: The agent that handled the interaction.
            success: Whether the interaction succeeded.
            duration_ms: Duration in milliseconds.
            token_cost: Normalized token cost (0.0-1.0).

        Returns:
            Updated pheromone score.
        """
        # Compute normalized speed score (faster = higher, cap at 30s)
        speed_score = max(0.0, 1.0 - (duration_ms / 30000))
        cost_score = max(0.0, 1.0 - min(token_cost, 1.0))

        record = {
            "success": success,
            "speed_score": round(speed_score, 3),
            "cost_score": round(cost_score, 3),
            "duration_ms": duration_ms,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        if agent_id not in self._records:
            self._records[agent_id] = []

        self._records[agent_id].append(record)
        self._total_invocations += 1

        # Trim old records
        if len(self._records[agent_id]) > MAX_RECORDS_PER_AGENT:
            self._records[agent_id] = self._records[agent_id][
                -MAX_RECORDS_PER_AGENT:
            ]

        # Recompute pheromone score
        new_score = compute_pheromone_score(self._records[agent_id])

        # Persist to DB
        await self._persist_score(agent_id, new_score)

        logger.debug(
            "Updated %s: %s (%dms) → score=%.3f",
            agent_id,
            "✓" if success else "✗",
            duration_ms,
            new_score,
        )

        return new_score

    async def _load_agent_states(
        self,
        agent_ids: List[str],
    ) -> Dict[str, Dict[str, Any]]:
        """Load agent states from DB for routing decisions."""
        if not agent_ids:
            return {}

        placeholders = ", ".join(f":a{i}" for i in range(len(agent_ids)))
        params = {f"a{i}": aid for i, aid in enumerate(agent_ids)}

        async with self._db_engine.begin() as conn:
            result = await conn.execute(
                text(f"""
                    SELECT agent_id, focus_type, status,
                           consecutive_failures, pheromone_score,
                           last_active_at
                    FROM aria_engine.agent_state
                    WHERE agent_id IN ({placeholders})
                """),
                params,
            )
            rows = result.mappings().all()

        return {row["agent_id"]: dict(row) for row in rows}

    async def _persist_score(
        self,
        agent_id: str,
        score: float,
    ) -> None:
        """Persist pheromone score to agent_state table."""
        async with self._db_engine.begin() as conn:
            await conn.execute(
                text("""
                    UPDATE aria_engine.agent_state
                    SET pheromone_score = :score,
                        updated_at = NOW()
                    WHERE agent_id = :agent_id
                """),
                {"agent_id": agent_id, "score": round(score, 3)},
            )

    async def get_routing_table(self) -> List[Dict[str, Any]]:
        """Get current routing table with all agent scores and stats."""
        async with self._db_engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT agent_id, display_name, focus_type, status,
                           pheromone_score, consecutive_failures,
                           last_active_at
                    FROM aria_engine.agent_state
                    WHERE status != 'disabled'
                    ORDER BY pheromone_score DESC
                """)
            )
            rows = result.mappings().all()

        table = []
        for row in rows:
            agent_id = row["agent_id"]
            records = self._records.get(agent_id, [])
            recent = records[-10:] if records else []
            success_rate = (
                sum(1 for r in recent if r.get("success")) / len(recent)
                if recent
                else None
            )

            table.append({
                "agent_id": agent_id,
                "display_name": row["display_name"],
                "focus_type": row["focus_type"],
                "status": row["status"],
                "pheromone_score": float(row["pheromone_score"] or 0.5),
                "consecutive_failures": row["consecutive_failures"],
                "recent_success_rate": (
                    round(success_rate, 3) if success_rate is not None else None
                ),
                "total_records": len(records),
                "last_active_at": (
                    row["last_active_at"].isoformat()
                    if row["last_active_at"]
                    else None
                ),
            })

        return table
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Router at engine infrastructure layer |
| 2 | .env for secrets (zero in code) | ✅ | DATABASE_URL from config |
| 3 | models.yaml single source of truth | ❌ | No model references |
| 4 | Docker-first testing | ✅ | Requires PostgreSQL for agent_state |
| 5 | aria_memories only writable path | ❌ | No file writes — scores in DB |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S4-01 (AgentPool — provides available_agents list)
- S1-05 (Alembic migration — agent_state.pheromone_score column)

## Verification
```bash
# 1. Module imports:
python -c "
from aria_engine.routing import EngineRouter, compute_specialty_match, compute_load_score
print('OK')
"
# EXPECTED: OK

# 2. Specialty matching:
python -c "
from aria_engine.routing import compute_specialty_match
print(compute_specialty_match('Deploy the Docker build', 'devops'))    # high
print(compute_specialty_match('Deploy the Docker build', 'social'))    # low
print(compute_specialty_match('Write a blog post about AI', 'creative'))  # high
"
# EXPECTED: 0.8+, 0.1, 0.8+

# 3. Load scoring:
python -c "
from aria_engine.routing import compute_load_score
print(compute_load_score('idle', 0))       # 1.0
print(compute_load_score('busy', 0))       # 0.3
print(compute_load_score('error', 0))      # 0.1
print(compute_load_score('idle', 3))       # 0.7
"
# EXPECTED: 1.0, 0.3, 0.1, 0.7
```

## Prompt for Agent
```
Port pheromone routing from aria_agents to the Aria Engine with DB persistence.

FILES TO READ FIRST:
- aria_agents/scoring.py (full file — compute_pheromone, PerformanceTracker, WEIGHTS)
- aria_agents/coordinator.py (lines 300-340 — pheromone-based agent selection in process())
- aria_engine/agent_pool.py (created in S4-01 — EngineAgent with status, pheromone_score)
- MASTER_PLAN.md (lines 140-160 — agent_state.pheromone_score column)

STEPS:
1. Read all files above
2. Create aria_engine/routing.py
3. Port compute_pheromone() as compute_pheromone_score()
4. Add compute_specialty_match() — regex-based keyword matching per focus type
5. Add compute_load_score() — factor in status and consecutive_failures
6. Implement EngineRouter.route_message() — multi-factor score combination
7. Implement update_scores() — record result + recompute + persist to DB
8. Implement get_routing_table() — current state for dashboard
9. Run verification commands

CONSTRAINTS:
- Scoring formula from aria_agents/scoring.py must be preserved
- Scores persist to engine_agent_state.pheromone_score (not filesystem)
- Cold start: 0.500 for untested agents
- Decay: 0.95 per day
```
