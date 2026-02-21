# S2-05: System Prompt Assembly Pipeline
**Epic:** E1 — Engine Core | **Priority:** P0 | **Points:** 3 | **Phase:** 2

## Problem
Aria's system prompt is assembled from multiple sources: soul files (IDENTITY.md, SOUL.md), per-agent configuration, active goals, date/time context, and available tool descriptions. Currently, OpenClaw injects a static system prompt from its config. The `cognition.py` `process()` method (line 251) calls `self.soul.get_system_prompt()` which returns only the soul identity — it doesn't include goals, tools, or dynamic context. We need a `PromptAssembler` that builds a complete, rich system prompt from all sources.

## Root Cause
The soul system (`aria_mind/soul/__init__.py`) provides `get_system_prompt()` which returns a static identity string. There is no pipeline that combines:
- Soul files (identity, values, boundaries)
- Agent-specific prompt (from `engine_agent_state.system_prompt` in DB)
- Active goals (from `goals` table or goals skill)
- Current date/time/context
- Available tool descriptions

OpenClaw assembled its own system prompt from `openclaw-config.json` system prompt + identity file mount. The Python side never owned prompt assembly. With OpenClaw gone, we need a native assembler.

## Fix
### `aria_engine/prompts.py`
```python
"""
System Prompt Assembler — Builds complete system prompts from multiple sources.

Assembles prompts from:
1. Soul files (IDENTITY.md, SOUL.md) — Aria's core identity (read-only)
2. Agent-specific prompt — from engine_agent_state.system_prompt in DB
3. Active goals — current objectives and focus areas
4. Date/time context — current timestamp, day of week
5. Tool descriptions — what tools/skills are available

Features:
- Caching with TTL (60s) to avoid re-reading files on every message
- Support for prompt override (testing/debugging)
- Modular sections that can be enabled/disabled
"""
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from aria_engine.config import EngineConfig

logger = logging.getLogger("aria.engine.prompts")


@dataclass
class PromptSection:
    """A named section of the system prompt."""
    name: str
    content: str
    priority: int = 50  # Higher = appears first
    enabled: bool = True


@dataclass
class AssembledPrompt:
    """Result of prompt assembly with metadata."""
    prompt: str
    sections: List[str]
    total_chars: int
    cached: bool = False
    assembled_at: float = 0.0

    def __str__(self) -> str:
        return self.prompt


class PromptAssembler:
    """
    Builds complete system prompts from multiple sources.

    Usage:
        assembler = PromptAssembler(config)

        # Basic assembly:
        prompt = assembler.assemble(agent_id="main")

        # With tools:
        prompt = assembler.assemble(agent_id="main", tools=tool_definitions)

        # With override (testing):
        prompt = assembler.assemble(agent_id="main", override="You are a test bot.")
    """

    # Cache TTL in seconds
    CACHE_TTL = 60.0

    def __init__(self, config: EngineConfig):
        self.config = config
        self._soul_cache: Dict[str, str] = {}
        self._soul_cache_time: float = 0.0
        self._prompt_cache: Dict[str, AssembledPrompt] = {}
        self._prompt_cache_times: Dict[str, float] = {}

    def assemble(
        self,
        agent_id: str = "main",
        tools: Optional[List[Dict[str, Any]]] = None,
        goals: Optional[List[str]] = None,
        agent_prompt: Optional[str] = None,
        override: Optional[str] = None,
        include_datetime: bool = True,
        include_tools: bool = True,
        include_goals: bool = True,
    ) -> AssembledPrompt:
        """
        Assemble a complete system prompt for an agent.

        Args:
            agent_id: Agent identifier (for cache key and agent-specific sections).
            tools: List of tool definitions (OpenAI format) to describe in prompt.
            goals: List of active goal strings.
            agent_prompt: Agent-specific prompt text (from engine_agent_state.system_prompt).
            override: If set, returns this string as the entire prompt (for testing).
            include_datetime: Whether to include current date/time section.
            include_tools: Whether to include tool descriptions section.
            include_goals: Whether to include goals section.

        Returns:
            AssembledPrompt with the full prompt string and metadata.
        """
        # Override bypasses everything
        if override:
            return AssembledPrompt(
                prompt=override,
                sections=["override"],
                total_chars=len(override),
                cached=False,
                assembled_at=time.monotonic(),
            )

        # Check cache
        cache_key = f"{agent_id}:{include_tools}:{include_goals}"
        cached = self._get_cached(cache_key)
        if cached is not None and tools is None and goals is None:
            # Only use cache when no dynamic content is provided
            return cached

        # Build sections
        sections: List[PromptSection] = []

        # ── Section 1: Soul Identity (highest priority) ───────────────────
        identity = self._load_soul_file("IDENTITY.md")
        if identity:
            sections.append(PromptSection(
                name="identity",
                content=identity,
                priority=100,
            ))

        # ── Section 2: Soul Values ────────────────────────────────────────
        soul = self._load_soul_file("SOUL.md")
        if soul:
            sections.append(PromptSection(
                name="soul",
                content=soul,
                priority=90,
            ))

        # ── Section 3: Agent-specific prompt ──────────────────────────────
        if agent_prompt:
            sections.append(PromptSection(
                name="agent_prompt",
                content=f"## Agent Instructions\n{agent_prompt}",
                priority=80,
            ))

        # ── Section 4: Active Goals ───────────────────────────────────────
        if include_goals and goals:
            goals_text = "## Current Goals\n"
            for i, goal in enumerate(goals, 1):
                goals_text += f"{i}. {goal}\n"
            sections.append(PromptSection(
                name="goals",
                content=goals_text,
                priority=70,
            ))

        # ── Section 5: Date/Time Context ──────────────────────────────────
        if include_datetime:
            now = datetime.now(timezone.utc)
            datetime_text = (
                f"## Current Context\n"
                f"- **Date:** {now.strftime('%A, %B %d, %Y')}\n"
                f"- **Time:** {now.strftime('%H:%M UTC')}\n"
                f"- **Timezone:** UTC\n"
            )
            sections.append(PromptSection(
                name="datetime",
                content=datetime_text,
                priority=60,
            ))

        # ── Section 6: Available Tools ────────────────────────────────────
        if include_tools and tools:
            tools_text = "## Available Tools\n"
            tools_text += "You can call the following tools when needed:\n\n"
            for tool in tools:
                func = tool.get("function", {})
                name = func.get("name", "unknown")
                desc = func.get("description", "No description")
                params = func.get("parameters", {})
                props = params.get("properties", {})

                tools_text += f"### `{name}`\n"
                tools_text += f"{desc}\n"
                if props:
                    tools_text += "**Parameters:**\n"
                    for pname, pdef in props.items():
                        ptype = pdef.get("type", "any")
                        pdesc = pdef.get("description", "")
                        required = pname in params.get("required", [])
                        req_marker = " (required)" if required else ""
                        tools_text += f"- `{pname}` ({ptype}{req_marker}): {pdesc}\n"
                tools_text += "\n"

            sections.append(PromptSection(
                name="tools",
                content=tools_text,
                priority=50,
            ))

        # ── Assemble ──────────────────────────────────────────────────────
        # Sort by priority (highest first)
        sections.sort(key=lambda s: s.priority, reverse=True)
        enabled = [s for s in sections if s.enabled]

        prompt_parts = [s.content.strip() for s in enabled]
        full_prompt = "\n\n---\n\n".join(prompt_parts)
        section_names = [s.name for s in enabled]

        result = AssembledPrompt(
            prompt=full_prompt,
            sections=section_names,
            total_chars=len(full_prompt),
            cached=False,
            assembled_at=time.monotonic(),
        )

        # Cache only if no dynamic content provided
        if tools is None and goals is None:
            self._set_cached(cache_key, result)

        logger.debug(
            "Assembled prompt for agent=%s: %d chars, sections=%s",
            agent_id, len(full_prompt), section_names,
        )

        return result

    async def assemble_for_session(
        self,
        agent_id: str,
        db_session_factory,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AssembledPrompt:
        """
        Assemble prompt with agent-specific data from the database.

        Loads agent_prompt and goals from DB, then calls assemble().
        """
        from sqlalchemy import select

        agent_prompt = None
        goals: List[str] = []

        async with db_session_factory() as db:
            # Load agent state for system_prompt
            try:
                from db.models import EngineAgentState
                result = await db.execute(
                    select(EngineAgentState).where(
                        EngineAgentState.agent_id == agent_id
                    )
                )
                agent = result.scalar_one_or_none()
                if agent and agent.system_prompt:
                    agent_prompt = agent.system_prompt
            except Exception as e:
                logger.debug("Could not load agent state: %s", e)

            # Load active goals
            try:
                from db.models import Goal
                goal_result = await db.execute(
                    select(Goal.title)
                    .where(Goal.status == "active")
                    .order_by(Goal.priority.desc())
                    .limit(10)
                )
                goals = [row[0] for row in goal_result.fetchall() if row[0]]
            except Exception as e:
                logger.debug("Could not load goals: %s", e)

        return self.assemble(
            agent_id=agent_id,
            tools=tools,
            goals=goals if goals else None,
            agent_prompt=agent_prompt,
        )

    def _load_soul_file(self, filename: str) -> Optional[str]:
        """
        Load a soul file from aria_mind/soul/ directory.

        Uses cache with TTL to avoid re-reading on every message.
        Falls back to reading from the legacy aria_mind/ root if soul/ doesn't exist.
        """
        now = time.monotonic()

        # Check cache
        if filename in self._soul_cache and (now - self._soul_cache_time) < self.CACHE_TTL:
            return self._soul_cache.get(filename)

        # Try soul/ directory first
        soul_dir = Path(self.config.soul_path)
        file_path = soul_dir / filename

        if not file_path.exists():
            # Fallback: try aria_mind/ root
            mind_dir = soul_dir.parent
            file_path = mind_dir / filename

        if not file_path.exists():
            logger.debug("Soul file not found: %s", filename)
            return None

        try:
            content = file_path.read_text(encoding="utf-8")
            self._soul_cache[filename] = content
            self._soul_cache_time = now
            logger.debug("Loaded soul file: %s (%d chars)", filename, len(content))
            return content
        except Exception as e:
            logger.warning("Failed to read soul file %s: %s", filename, e)
            return None

    def _get_cached(self, key: str) -> Optional[AssembledPrompt]:
        """Get cached prompt if not expired."""
        if key not in self._prompt_cache:
            return None
        cache_time = self._prompt_cache_times.get(key, 0)
        if (time.monotonic() - cache_time) > self.CACHE_TTL:
            self._prompt_cache.pop(key, None)
            self._prompt_cache_times.pop(key, None)
            return None
        cached = self._prompt_cache[key]
        return AssembledPrompt(
            prompt=cached.prompt,
            sections=cached.sections,
            total_chars=cached.total_chars,
            cached=True,
            assembled_at=cached.assembled_at,
        )

    def _set_cached(self, key: str, prompt: AssembledPrompt) -> None:
        """Cache an assembled prompt."""
        self._prompt_cache[key] = prompt
        self._prompt_cache_times[key] = time.monotonic()

    def clear_cache(self) -> None:
        """Clear all caches (useful when soul files change)."""
        self._soul_cache.clear()
        self._soul_cache_time = 0.0
        self._prompt_cache.clear()
        self._prompt_cache_times.clear()
        logger.info("Prompt cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        return {
            "soul_files_cached": len(self._soul_cache),
            "prompts_cached": len(self._prompt_cache),
            "cache_ttl_seconds": self.CACHE_TTL,
        }
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Reads agent state and goals from DB via ORM |
| 2 | .env for secrets (zero in code) | ❌ | No secrets in prompt assembly |
| 3 | models.yaml single source of truth | ❌ | No model routing in this module |
| 4 | Docker-first testing | ✅ | Soul path configurable via EngineConfig for Docker mount |
| 5 | aria_memories only writable path | ❌ | No file writes — only reads soul files |
| 6 | No soul modification | ✅ | Reads soul files, NEVER writes to them |

## Dependencies
- S1-01 must complete first (aria_engine package + EngineConfig.soul_path)
- S1-05 must complete first (EngineAgentState ORM model)

## Verification
```bash
# 1. Module imports:
python -c "from aria_engine.prompts import PromptAssembler, PromptSection, AssembledPrompt; print('OK')"
# EXPECTED: OK

# 2. Basic assembly with override:
python -c "
from aria_engine.config import EngineConfig
from aria_engine.prompts import PromptAssembler
pa = PromptAssembler(EngineConfig())
result = pa.assemble(override='You are a test bot.')
assert result.prompt == 'You are a test bot.'
assert result.sections == ['override']
assert result.total_chars == len('You are a test bot.')
print(f'Override OK: {result}')
"
# EXPECTED: Override OK: You are a test bot.

# 3. Assembly with datetime:
python -c "
from aria_engine.config import EngineConfig
from aria_engine.prompts import PromptAssembler
pa = PromptAssembler(EngineConfig())
result = pa.assemble(agent_id='main', include_tools=False, include_goals=False)
assert 'datetime' in result.sections
assert 'Date:' in result.prompt
print(f'Sections: {result.sections}')
print(f'Chars: {result.total_chars}')
"
# EXPECTED: Sections include 'datetime', prompt contains 'Date:'

# 4. Assembly with tools:
python -c "
from aria_engine.config import EngineConfig
from aria_engine.prompts import PromptAssembler
pa = PromptAssembler(EngineConfig())
tools = [{'type': 'function', 'function': {'name': 'search', 'description': 'Search the web', 'parameters': {'type': 'object', 'properties': {'q': {'type': 'string', 'description': 'Query'}}, 'required': ['q']}}}]
result = pa.assemble(agent_id='main', tools=tools)
assert 'tools' in result.sections
assert 'search' in result.prompt
assert 'Search the web' in result.prompt
print('Tools assembly OK')
"
# EXPECTED: Tools assembly OK

# 5. Cache behavior:
python -c "
from aria_engine.config import EngineConfig
from aria_engine.prompts import PromptAssembler
pa = PromptAssembler(EngineConfig())
r1 = pa.assemble(agent_id='main')
r2 = pa.assemble(agent_id='main')
assert r2.cached == True
stats = pa.get_cache_stats()
assert stats['prompts_cached'] >= 1
print(f'Cache stats: {stats}')
"
# EXPECTED: Cache stats: {'soul_files_cached': ..., 'prompts_cached': 1, ...}
```

## Prompt for Agent
```
Implement the System Prompt Assembly Pipeline for Aria Engine.

FILES TO READ FIRST:
- aria_engine/config.py (EngineConfig.soul_path — created in S1-01)
- aria_mind/soul/__init__.py (full file — Soul class, get_system_prompt)
- aria_mind/soul/identity.py (full file — identity values)
- aria_mind/IDENTITY.md (full file — Aria's identity document)
- aria_mind/SOUL.md (full file — Aria's soul document)
- aria_mind/cognition.py (line 251 — current system prompt injection)
- src/api/db/models.py (EngineAgentState — system_prompt column, created in S1-05)

STEPS:
1. Read all files above
2. Create aria_engine/prompts.py with PromptAssembler class
3. Implement assemble() — multi-section prompt builder
4. Implement _load_soul_file() — cached soul file reader
5. Implement assemble_for_session() — DB-backed variant
6. Implement caching with 60s TTL
7. Implement override support for testing
8. Run verification commands

CONSTRAINTS:
- Constraint 6: NEVER write to soul files — read-only access
- Cache soul files with 60s TTL
- Sections ordered by priority (identity=100, soul=90, agent=80, goals=70, datetime=60, tools=50)
- Override mode bypasses all assembly for testing
```
