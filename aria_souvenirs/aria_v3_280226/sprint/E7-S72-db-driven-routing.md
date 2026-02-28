# S-72: routing.py — Replace Hardcoded SPECIALTY_PATTERNS with DB-Driven Cache

**Epic:** E7 — Focus System v2 | **Priority:** P1 | **Points:** 2 | **Phase:** 2

---

## Problem

`aria_engine/routing.py` lines 40–68 define `SPECIALTY_PATTERNS` as a
hardcoded Python dict of 5 entries (`social`, `analysis`, `devops`, `creative`,
`research`). This means:

1. Adding a new focus persona requires a code change and re-deploy
2. The routing vocab is disconnected from `FocusProfileEntry.expertise_keywords`
   (created in S-70 with per-profile keyword arrays)
3. `compute_specialty_match()` at line 83 returns hardcoded float values (0.1 /
   0.6 / 0.8 / 1.0) regardless of how many focus profiles exist
4. Focus IDs in the DB (`devsecops`, `data`, `orchestrator`, `journalist`,
   `rpg_master`) are not in `SPECIALTY_PATTERNS` so they always return 0.3

---

## Root Cause

`SPECIALTY_PATTERNS` was `compile_time-only` (module-level dict set at import).
`EngineRouter.__init__` at line 200 receives `db_engine: AsyncEngine` but never
uses it to load focus profile data. The patterns are compiled from hardcoded
regex strings, not from `aria_engine.focus_profiles.expertise_keywords`.

---

## Fix

### Step 1 — Rename hardcoded dict to `_FALLBACK_PATTERNS` and add a mutable cache

**File:** `aria_engine/routing.py`

**BEFORE (lines 39–68):**
```python
# Specialty keywords per focus type
SPECIALTY_PATTERNS: dict[str, re.Pattern] = {
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
```

**AFTER:**
```python
# Fallback specialty patterns (used when DB is unavailable)
_FALLBACK_PATTERNS: dict[str, re.Pattern] = {
    "social":       re.compile(r"(social|post|tweet|moltbook|community|engage|share|content)", re.IGNORECASE),
    "analysis":     re.compile(r"(analy|metric|data|report|review|insight|trend|stat)", re.IGNORECASE),
    "devops":       re.compile(r"(deploy|docker|server|ci|cd|build|test|infra|monitor|debug)", re.IGNORECASE),
    "devsecops":    re.compile(r"(deploy|docker|server|ci|cd|build|test|infra|monitor|debug|security|vulnerability|patch)", re.IGNORECASE),
    "creative":     re.compile(r"(creat|write|art|story|design|brand|visual|content|blog)", re.IGNORECASE),
    "research":     re.compile(r"(research|paper|study|learn|explore|investigate|knowledge)", re.IGNORECASE),
    "data":         re.compile(r"(analy|metric|data|report|insight|trend|stat|pipeline|ml|query|sql)", re.IGNORECASE),
    "orchestrator": re.compile(r"(strategy|plan|coordinate|orchestrate|decide|priority|goal|overview)", re.IGNORECASE),
    "journalist":   re.compile(r"(report|article|news|investigate|story|lead|headline|press|coverage)", re.IGNORECASE),
    "rpg_master":   re.compile(r"(rpg|campaign|quest|npc|dungeon|character|encounter|lore|world)", re.IGNORECASE),
}

# Live cache — populated by EngineRouter.initialize_patterns() from DB
# Falls back to _FALLBACK_PATTERNS when empty
SPECIALTY_PATTERNS: dict[str, re.Pattern] = dict(_FALLBACK_PATTERNS)
```

### Step 2 — Add `initialize_patterns()` method to `EngineRouter`

**File:** `aria_engine/routing.py`

**BEFORE (lines 200–204 — EngineRouter.__init__):**
```python
    def __init__(self, db_engine: AsyncEngine):
        self._db_engine = db_engine
        # In-memory record cache per agent (synced to DB periodically)
        self._records: dict[str, list[dict[str, Any]]] = {}
        self._total_invocations = 0
```

**AFTER:**
```python
    def __init__(self, db_engine: AsyncEngine):
        self._db_engine = db_engine
        # In-memory record cache per agent (synced to DB periodically)
        self._records: dict[str, list[dict[str, Any]]] = {}
        self._total_invocations = 0

    async def initialize_patterns(self) -> int:
        """
        Load focus profile expertise_keywords from DB and compile into
        SPECIALTY_PATTERNS. Safe to call multiple times (idempotent cache refresh).
        Falls back to _FALLBACK_PATTERNS if DB is unavailable or table is empty.

        Returns:
            Number of profiles loaded.
        """
        global SPECIALTY_PATTERNS
        try:
            from db.models import FocusProfileEntry
            async with self._db_engine.begin() as conn:
                from sqlalchemy import select as _select
                result = await conn.execute(
                    _select(
                        FocusProfileEntry.focus_id,
                        FocusProfileEntry.expertise_keywords,
                    ).where(FocusProfileEntry.enabled == True)  # noqa: E712
                )
                rows = result.all()

            if not rows:
                logger.warning("No focus profiles in DB — keeping fallback patterns")
                return 0

            new_patterns: dict[str, re.Pattern] = {}
            for row in rows:
                keywords: list[str] = row.expertise_keywords or []
                if not keywords:
                    continue
                # Build alternation pattern from keyword list
                pattern_str = "(" + "|".join(re.escape(k) for k in keywords) + ")"
                new_patterns[row.focus_id] = re.compile(pattern_str, re.IGNORECASE)

            SPECIALTY_PATTERNS = new_patterns
            logger.info("initialize_patterns: loaded %d focus profiles from DB", len(new_patterns))
            return len(new_patterns)

        except Exception as exc:
            logger.warning("initialize_patterns failed (%s) — using fallback", exc)
            SPECIALTY_PATTERNS = dict(_FALLBACK_PATTERNS)
            return 0
```

### Step 3 — Call `initialize_patterns()` at engine startup

**File:** `aria_engine/entrypoint.py` (or wherever `EngineRouter` is constructed)

Find where `EngineRouter` is instantiated and add a call:

```python
# After router = EngineRouter(db_engine):
await router.initialize_patterns()
logger.info("Routing patterns: %d focus profiles loaded", n)
```

---

## Constraints

| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | routing.py is engine-layer; reads DB directly (engine layer is permitted) |
| 2 | No secrets in code | ✅ | No secrets |
| 3 | models.yaml SoT | ✅ | No model names in this file |
| 4 | Docker-first | ✅ | Verification via docker exec |
| 5 | aria_memories writable | ✅ | No file writes |
| 6 | No soul modification | ✅ | No soul file touched |

---

## Dependencies

- **S-71 must complete first** — `aria_engine.focus_profiles` table must be seeded with 8 profiles

---

## Verification

```bash
# 1. Syntax clean
docker exec aria-engine python3 -c "
import ast, pathlib
ast.parse(pathlib.Path('aria_engine/routing.py').read_text())
print('syntax OK')
"
# EXPECTED: syntax OK

# 2. SPECIALTY_PATTERNS still a dict
docker exec aria-engine python3 -c "
from aria_engine.routing import SPECIALTY_PATTERNS, _FALLBACK_PATTERNS
print('SPECIALTY_PATTERNS keys:', sorted(SPECIALTY_PATTERNS.keys()))
print('_FALLBACK_PATTERNS keys:', sorted(_FALLBACK_PATTERNS.keys()))
"
# EXPECTED:
# SPECIALTY_PATTERNS keys: ['analysis', 'creative', 'data', 'devsecops', 'devops', 'journalist', 'orchestrator', 'research', 'rpg_master', 'social']
# _FALLBACK_PATTERNS keys: [same list]

# 3. compute_specialty_match still works
docker exec aria-engine python3 -c "
from aria_engine.routing import compute_specialty_match
score = compute_specialty_match('deploy new docker container', 'devsecops')
print('devsecops score:', score)
score2 = compute_specialty_match('write a blog post', 'creative')
print('creative score:', score2)
"
# EXPECTED:
# devsecops score: 0.6  (≥ 0.1 means match found)
# creative score: 0.6

# 4. initialize_patterns() loads from DB (run after S-71 seed)
docker exec aria-engine python3 -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
import os
from aria_engine.routing import EngineRouter

async def test():
    db = create_async_engine(os.environ['DATABASE_URL'])
    router = EngineRouter(db)
    n = await router.initialize_patterns()
    print('profiles loaded:', n)
    from aria_engine.routing import SPECIALTY_PATTERNS
    print('pattern keys:', sorted(SPECIALTY_PATTERNS.keys()))

asyncio.run(test())
"
# EXPECTED:
# profiles loaded: 8
# pattern keys: ['creative', 'data', 'devsecops', 'journalist', 'orchestrator', 'research', 'rpg_master', 'social']
```

---

## Prompt for Agent

You are executing ticket S-72 for the Aria project. Do exactly the following.

**Constraint:** No skill imports, no SQLAlchemy in skill layer. Engine layer may
access DB directly. Do NOT modify `aria_mind/soul/`.

**Files to read first:**
- `aria_engine/routing.py` lines 1–110 (SPECIALTY_PATTERNS, EngineRouter.__init__, compute_specialty_match)
- `aria_engine/entrypoint.py` (find where EngineRouter is instantiated)

**Steps:**

1. In `aria_engine/routing.py`:
   a. Replace the `SPECIALTY_PATTERNS` block (lines 39–68) with
      `_FALLBACK_PATTERNS` + `SPECIALTY_PATTERNS = dict(_FALLBACK_PATTERNS)` as shown.
   b. Add the `initialize_patterns()` async method to `EngineRouter`
      immediately after `__init__` (after line 204).
2. In `aria_engine/entrypoint.py`, find where `EngineRouter` is constructed.
   After that line, call `await router.initialize_patterns()`.
3. Run all 4 verification commands and confirm outputs.
4. Report: "S-72 DONE — DB-driven patterns loaded, fallback preserved, verification passed."
