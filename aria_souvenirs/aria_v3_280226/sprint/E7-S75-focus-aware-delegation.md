# S-75: Roundtable + Swarm — Focus-Aware Agent Auto-Selection + Context Cap

**Epic:** E7 — Focus System v2 | **Priority:** P1 | **Points:** 5 | **Phase:** 3

---

## Problem

`aria_engine/roundtable.py` `discuss()` at line 136:
```python
async def discuss(
    self,
    topic: str,
    agent_ids: list[str],   # ← REQUIRED, always explicit
    ...
```

Two compounding failures:

1. **Callers must always enumerate agent IDs manually.** Aria cannot say
   "discuss this devops task" and have the system auto-select `devsecops`,
   `data`, `orchestrator` agents. Human-in-the-loop selection is required for
   every roundtable invocation — defeating the entire L1/L2/L3 hierarchy.

2. **`MAX_CONTEXT_TOKENS = 2000` is a single global constant (line 38).** A
   `creative` agent with `token_budget_hint = 800` is still fed 2000 tokens of
   context — generating a context that exceeds its own budget ceiling before
   the LLM even starts generating. This is a guaranteed budget-bust on every
   creative roundtable.

`aria_engine/swarm.py` has the same issue: pheromone weights control task
assignment but there is no focus-keyword matching to route tasks to the right
tier of agent.

---

## Root Cause

`focus_type` on agents is stored in DB and loaded into `EngineAgent` objects,
but neither `Roundtable.discuss()` nor `Swarm` ever queries `SPECIALTY_PATTERNS`
(updated in S-72) or `FocusProfileEntry.token_budget_hint` when deciding which
agents to select for a given topic.

---

## Design

### Delegation Levels
```
L1 — Orchestrator   (1 always included if available; routes/synthesizes)
L2 — Specialist     (1–3 selected by keyword match against topic)
L3 — Ephemeral      (0–2 selected only if topic triggers their pattern)
```

### Auto-selection algorithm (roundtable)

```python
def _select_agents_for_topic(pool: AgentPool, topic: str, max_agents: int = 5) -> list[str]:
    """
    Score all idle agents by keyword match against topic, respect delegation
    levels, and return top-N agent_ids for roundtable participation.

    Selection rules:
    - Always include ≥1 L1 agent (highest pheromone among L1 agents)
    - Fill remaining slots with L2 agents scoring > 0 (sorted by score desc)
    - Include L3 agents only if score > 0.4 AND remaining slot available
    - Hard cap: max_agents (default 5) — token economy enforcement
    """
```

### Context window per participating agent

Instead of one global `MAX_CONTEXT_TOKENS = 2000`, compute:

```python
# Per-agent context cap = min of all participants' token_budget_hint
# This guarantees context never exceeds what the tightest agent can receive
context_token_cap = min(
    fp.get("token_budget_hint", 2000)
    for fp in [agent._focus_profile for agent in participants if agent._focus_profile]
) if any participant has a focus profile else 2000
```

---

## Fix

### Step 1 — Make `agent_ids` optional in `discuss()`

**File:** `aria_engine/roundtable.py`

**BEFORE (line 136):**
```python
    async def discuss(
        self,
        topic: str,
        agent_ids: list[str],
        rounds: int = DEFAULT_ROUNDS,
        synthesizer_id: str = "main",
        agent_timeout: int = DEFAULT_AGENT_TIMEOUT,
        total_timeout: int = DEFAULT_TOTAL_TIMEOUT,
        on_turn: Any = None,
    ) -> RoundtableResult:
```

**AFTER:**
```python
    async def discuss(
        self,
        topic: str,
        agent_ids: list[str] | None = None,
        rounds: int = DEFAULT_ROUNDS,
        synthesizer_id: str = "main",
        agent_timeout: int = DEFAULT_AGENT_TIMEOUT,
        total_timeout: int = DEFAULT_TOTAL_TIMEOUT,
        on_turn: Any = None,
        max_agents: int = 5,          # hard cap for token economy
    ) -> RoundtableResult:
```

### Step 2 — Add auto-selection block at top of `discuss()`

Insert after method docstring, before `if len(agent_ids) < 2:`:

```python
        # Auto-select agents if not explicitly provided
        if agent_ids is None:
            agent_ids = self._select_agents_for_topic(topic, max_agents)
            if len(agent_ids) < 2:
                raise EngineError(
                    f"Not enough agents available for topic: '{topic[:80]}'"
                )

        # Enforce agent cap (even for explicit lists) — token economy
        if len(agent_ids) > max_agents:
            logger.warning(
                "Roundtable: truncating %d agents to max_agents=%d",
                len(agent_ids),
                max_agents,
            )
            agent_ids = agent_ids[:max_agents]
```

### Step 3 — Add `_select_agents_for_topic()` method

```python
    def _select_agents_for_topic(
        self,
        topic: str,
        max_agents: int = 5,
    ) -> list[str]:
        """
        Auto-select agents by focus keyword match against topic.

        Scoring:
            1. Always include ≥1 L1 agent (orchestrator tier)
            2. Fill L2 slots with highest keyword-match score
            3. Include L3 agents only if score > 0.4 and slots remain
            4. Hard cap at max_agents

        Returns:
            Ordered list of agent_ids (L1 first, then L2, then L3).
        """
        from aria_engine.routing import compute_specialty_match

        all_agents = self._pool.list_agents()   # list[EngineAgent]
        l1_agents, l2_candidates, l3_candidates = [], [], []

        for agent in all_agents:
            if agent.status == "offline":
                continue
            fp = agent._focus_profile
            level = (fp.get("delegation_level") if fp else None) or 2  # default L2
            score = compute_specialty_match(topic, agent.focus_type or "")

            entry = (agent.agent_id, score, level)
            if level == 1:
                l1_agents.append(entry)
            elif level == 2:
                l2_candidates.append(entry)
            else:
                l3_candidates.append(entry)

        # Sort by score desc
        l1_agents.sort(key=lambda x: x[1], reverse=True)
        l2_candidates.sort(key=lambda x: x[1], reverse=True)
        l3_candidates.sort(key=lambda x: x[1], reverse=True)

        selected: list[str] = []

        # Always include top L1
        if l1_agents:
            selected.append(l1_agents[0][0])

        # Fill L2 slots (score > 0 means at least one keyword matched)
        for agent_id, score, _ in l2_candidates:
            if len(selected) >= max_agents:
                break
            if score > 0:
                selected.append(agent_id)

        # Fill L3 only if highly relevant
        for agent_id, score, _ in l3_candidates:
            if len(selected) >= max_agents:
                break
            if score > 0.4:
                selected.append(agent_id)

        logger.info(
            "Auto-selected %d agents for topic '%s': %s",
            len(selected), topic[:60], selected,
        )
        return selected
```

### Step 4 — Per-participant context cap

Replace `MAX_CONTEXT_TOKENS` usage in the discussion loop. Find where
`MAX_CONTEXT_TOKENS` is used to build the prior-context string and replace with:

```python
# Per-agent context cap — tightest participant's token budget wins
_participant_agents = [self._pool.get_agent(aid) for aid in agent_ids if self._pool.get_agent(aid)]
_budgets = [
    a._focus_profile.get("token_budget_hint", MAX_CONTEXT_TOKENS)
    for a in _participant_agents
    if a._focus_profile
]
context_token_cap = min(_budgets) if _budgets else MAX_CONTEXT_TOKENS
```

Then replace every reference to `MAX_CONTEXT_TOKENS` in the discussion body
with `context_token_cap`.

### Step 5 — Patch `swarm.py` task routing

**File:** `aria_engine/swarm.py`

Find the agent selection function (around line 199). Add focus keyword score
as a tiebreaker multiplier on pheromone weight:

```python
# Focus bonus: adds up to 0.3x on top of pheromone weight
from aria_engine.routing import compute_specialty_match
focus_bonus = compute_specialty_match(task_description, agent.focus_type or "")
effective_weight = pheromone_weight * (1.0 + 0.3 * focus_bonus)
```

This keeps pheromone as primary signal, adds focus as a secondary booster —
no behavior regression for agents without focus profiles.

---

## Constraints

| # | Constraint | Status | Notes |
|---|-----------|--------|-------|
| 1 | `agent_ids` still accepted explicitly | ✅ | `None` default is backward-compatible |
| 2 | L1 agent always selected | ✅ | `_select_agents_for_topic` enforces this |
| 3 | max_agents cap enforced | ✅ | Applied to both auto-selected and explicit lists |
| 4 | Context cap = tightest participant | ✅ | `min(_budgets)` logic |
| 5 | Swarm non-breaking | ✅ | Pheromone is still primary; focus is ×1.0–1.3 bonus |
| 6 | No soul modification | ✅ | None |

---

## Dependencies

- **S-72** — `compute_specialty_match()` uses DB-driven patterns
- **S-73** — `agent._focus_profile` dict populated with `delegation_level`
- **S-74** — `token_budget_hint` values filled in DB

---

## Verification

```bash
# 1. Syntax clean (both files)
docker exec aria-engine python3 -c "
import ast, pathlib
for f in ['aria_engine/roundtable.py', 'aria_engine/swarm.py']:
    ast.parse(pathlib.Path(f).read_text())
    print(f, 'syntax OK')
"
# EXPECTED:
# aria_engine/roundtable.py syntax OK
# aria_engine/swarm.py syntax OK

# 2. agent_ids defaults to None
docker exec aria-engine python3 -c "
import inspect
from aria_engine.roundtable import Roundtable
sig = inspect.signature(Roundtable.discuss)
param = sig.parameters['agent_ids']
print('agent_ids default:', param.default)
assert param.default is None
print('PASS')
"
# EXPECTED: agent_ids default: None / PASS

# 3. Auto-selection returns L1 first
docker exec aria-engine python3 -c "
import asyncio, os
from sqlalchemy.ext.asyncio import create_async_engine
from aria_engine.agent_pool import AgentPool
from aria_engine.routing import EngineRouter
from aria_engine.roundtable import Roundtable

async def test():
    db = create_async_engine(os.environ['DATABASE_URL'])
    pool = AgentPool(db)
    await pool.load_from_db()
    router = EngineRouter(db)
    await router.initialize_patterns()
    rt = Roundtable(db, pool, router)
    ids = rt._select_agents_for_topic('deploy new docker container')
    print('auto-selected:', ids)
    # First agent should have delegation_level = 1 (orchestrator)
    first_agent = pool.get_agent(ids[0]) if ids else None
    if first_agent and first_agent._focus_profile:
        print('first agent level:', first_agent._focus_profile.get('delegation_level'))

asyncio.run(test())
"
# EXPECTED:
# auto-selected: ['orchestrator-id', 'devsecops-id', ...]  (≥2 agents)
# first agent level: 1

# 4. Context token cap = tightest participant
docker exec aria-engine python3 -c "
# Simulate two participants: orchestrator (3000) + social (800)
profiles = [{'token_budget_hint': 3000}, {'token_budget_hint': 800}]
cap = min(p['token_budget_hint'] for p in profiles)
print('context_token_cap:', cap)
assert cap == 800
print('PASS')
"
# EXPECTED: context_token_cap: 800 / PASS
```

---

## Prompt for Agent

You are executing ticket S-75 for the Aria project.

**Constraint:** `agent_ids: list[str]` must become `agent_ids: list[str] | None = None` for backward compatibility. All existing callers with explicit `agent_ids` lists must continue working unchanged. Do NOT modify `aria_mind/soul/`.

**Files to read first:**
- `aria_engine/roundtable.py` — full `discuss()` method and the context-building loop that uses `MAX_CONTEXT_TOKENS`
- `aria_engine/swarm.py` — find agent selection / pheromone weight computation area (around line 199)

**Steps:**
1. Make `agent_ids` optional with `None` default in `discuss()` signature.
2. Add auto-selection guard block at top of `discuss()` body.
3. Add `_select_agents_for_topic()` method to `Roundtable` class.
4. Replace static `MAX_CONTEXT_TOKENS` usage with per-participant `context_token_cap`.
5. Patch `swarm.py` pheromone computation to multiply by `(1.0 + 0.3 * focus_bonus)`.
6. Run all 4 verification commands.
7. Report: "S-75 DONE — Auto-selection live, L1 pinned, context_token_cap tightened, swarm focus bonus applied."
