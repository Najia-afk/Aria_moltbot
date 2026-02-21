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
from typing import Any

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
    sections: list[str]
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
        self._soul_cache: dict[str, str] = {}
        self._soul_cache_time: float = 0.0
        self._prompt_cache: dict[str, AssembledPrompt] = {}
        self._prompt_cache_times: dict[str, float] = {}

    def assemble(
        self,
        agent_id: str = "main",
        tools: list[dict[str, Any]] | None = None,
        goals: list[str] | None = None,
        agent_prompt: str | None = None,
        override: str | None = None,
        include_datetime: bool = True,
        include_tools: bool = True,
        include_goals: bool = True,
        mind_files: list[str] | None = None,
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

        # Determine which mind files to load (per-agent selection)
        _mind_file_sections = {
            "IDENTITY.md": ("identity", 100),
            "SOUL.md": ("soul", 90),
            "SKILLS.md": ("skills", 85),
            "TOOLS.md": ("tools_reference", 84),
            "MEMORY.md": ("memory", 83),
            "GOALS.md": ("goals_reference", 82),
            "AGENTS.md": ("agents_reference", 81),
            "SECURITY.md": ("security_reference", 80),
        }
        # Default: load all if mind_files not specified
        files_to_load = mind_files if mind_files else list(_mind_file_sections.keys())

        # Build sections
        sections: list[PromptSection] = []

        # ── Soul / Mind file sections (loaded per agent config) ───────────
        for filename in files_to_load:
            if filename not in _mind_file_sections:
                # Custom file — load with default priority
                content = self._load_soul_file(filename)
                if content:
                    sections.append(PromptSection(
                        name=filename.replace(".md", "").lower(),
                        content=content,
                        priority=75,
                    ))
                continue
            section_name, priority = _mind_file_sections[filename]
            content = self._load_soul_file(filename)
            if content:
                sections.append(PromptSection(
                    name=section_name,
                    content=content,
                    priority=priority,
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
        tools: list[dict[str, Any]] | None = None,
    ) -> AssembledPrompt:
        """
        Assemble prompt with agent-specific data from the database.

        Loads agent_prompt, goals, and mind_files from DB, then calls assemble().
        """
        from sqlalchemy import select

        agent_prompt = None
        goals: list[str] = []
        mind_files: list[str] | None = None

        async with db_session_factory() as db:
            # Load agent state for system_prompt + mind_files
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
                # Read mind_files from agent metadata if available
                if agent and agent.metadata_json:
                    mf = agent.metadata_json.get("mind_files")
                    if isinstance(mf, list) and mf:
                        mind_files = mf
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
            mind_files=mind_files,
        )

    def _load_soul_file(self, filename: str) -> str | None:
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

    def _get_cached(self, key: str) -> AssembledPrompt | None:
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

    def get_cache_stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        return {
            "soul_files_cached": len(self._soul_cache),
            "prompts_cached": len(self._prompt_cache),
            "cache_ttl_seconds": self.CACHE_TTL,
        }
