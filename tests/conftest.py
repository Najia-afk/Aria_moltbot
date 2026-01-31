# tests/conftest.py
"""
Pytest fixtures for Aria tests.
"""
import asyncio
import os
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from aria_skills.base import SkillConfig, SkillStatus
from aria_skills.registry import SkillRegistry
from aria_agents.base import AgentConfig, AgentRole


# ============================================================================
# Event loop fixture
# ============================================================================

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Skill fixtures
# ============================================================================

@pytest.fixture
def mock_skill_config() -> SkillConfig:
    """Create a mock skill config."""
    return SkillConfig(
        name="test_skill",
        enabled=True,
        config={
            "api_key": "test-key",
            "rate_limit": {"requests_per_minute": 60},
        },
    )


@pytest.fixture
def skill_registry() -> SkillRegistry:
    """Create an empty skill registry."""
    return SkillRegistry()


@pytest_asyncio.fixture
async def mock_moltbook_skill() -> AsyncMock:
    """Create a mock Moltbook skill."""
    skill = AsyncMock()
    skill.name = "moltbook"
    skill.is_available = True
    skill.health_check = AsyncMock(return_value=SkillStatus.AVAILABLE)
    skill.post_status = AsyncMock(return_value=MagicMock(success=True, data={"post_id": "123"}))
    skill.get_timeline = AsyncMock(return_value=MagicMock(success=True, data=[]))
    return skill


@pytest_asyncio.fixture
async def mock_database_skill() -> AsyncMock:
    """Create a mock database skill."""
    skill = AsyncMock()
    skill.name = "database"
    skill.is_available = True
    skill.health_check = AsyncMock(return_value=SkillStatus.AVAILABLE)
    skill.execute = AsyncMock(return_value=MagicMock(success=True, data={"affected_rows": 1}))
    skill.fetch_one = AsyncMock(return_value=MagicMock(success=True, data=None))
    skill.fetch_all = AsyncMock(return_value=MagicMock(success=True, data=[]))
    return skill


@pytest_asyncio.fixture
async def mock_llm_skill() -> AsyncMock:
    """Create a mock LLM skill."""
    skill = AsyncMock()
    skill.name = "gemini"
    skill.is_available = True
    skill.health_check = AsyncMock(return_value=SkillStatus.AVAILABLE)
    skill.generate = AsyncMock(return_value=MagicMock(
        success=True,
        data={"text": "Test response", "model": "gemini-pro"},
    ))
    skill.chat = AsyncMock(return_value=MagicMock(
        success=True,
        data={"text": "Test chat response", "model": "gemini-pro"},
    ))
    return skill


# ============================================================================
# Agent fixtures
# ============================================================================

@pytest.fixture
def mock_agent_config() -> AgentConfig:
    """Create a mock agent config."""
    return AgentConfig(
        id="test_agent",
        name="Test Agent",
        role=AgentRole.COORDINATOR,
        model="gemini-pro",
        capabilities=["chat", "analyze"],
        skills=["gemini", "database"],
    )


@pytest.fixture
def aria_agent_config() -> AgentConfig:
    """Create Aria's agent config."""
    return AgentConfig(
        id="aria",
        name="Aria Blue",
        role=AgentRole.COORDINATOR,
        model="gemini-pro",
        capabilities=["orchestrate", "delegate", "synthesize"],
        skills=["gemini", "moonshot", "moltbook", "database"],
        temperature=0.7,
    )


# ============================================================================
# Environment fixtures
# ============================================================================

@pytest.fixture
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up mock environment variables."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("MOONSHOT_API_KEY", "test-moonshot-key")
    monkeypatch.setenv("MOLTBOOK_TOKEN", "test-moltbook-token")
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")


# ============================================================================
# HTTP fixtures
# ============================================================================

@pytest.fixture
def mock_httpx_response() -> MagicMock:
    """Create a mock httpx response."""
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {}
    response.text = ""
    return response


# ============================================================================
# Path fixtures
# ============================================================================

@pytest.fixture
def aria_mind_path(tmp_path) -> str:
    """Create a temporary aria_mind directory with test files."""
    mind_dir = tmp_path / "aria_mind"
    mind_dir.mkdir()
    
    # Create minimal TOOLS.md
    tools_md = mind_dir / "TOOLS.md"
    tools_md.write_text("""# Tools

## Available Skills

```yaml
moltbook:
  enabled: true
  api_url: https://test.moltbook.social/api

database:
  enabled: true
  dsn: env:DATABASE_URL
```
""")
    
    # Create minimal AGENTS.md
    agents_md = mind_dir / "AGENTS.md"
    agents_md.write_text("""# Agents

## Aria
- model: gemini-pro
- role: coordinator
- skills: [gemini, moltbook, database]

## Researcher
- model: gemini-pro
- parent: aria
- role: researcher
- skills: [gemini]
""")
    
    return str(mind_dir)
