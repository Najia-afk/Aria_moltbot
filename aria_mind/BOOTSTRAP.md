# BOOTSTRAP.md - Initialization Sequence

How to initialize Aria from a fresh state.

## Prerequisites

1. **Environment Variables** (in .env):
   ```bash
   DATABASE_URL=postgresql://aria_admin:YOUR_PASSWORD@localhost:5432/aria_warehouse
   GOOGLE_GEMINI_KEY=your_key_here
   MOONSHOT_KIMI_KEY=your_key_here
   MOLTBOOK_TOKEN=your_token_here
   ```

2. **PostgreSQL Database**:
   ```bash
   docker run -d --name aria-db \
   -e POSTGRES_USER=aria_admin \
   -e POSTGRES_PASSWORD=YOUR_PASSWORD \
   -e POSTGRES_DB=aria_warehouse \
     -p 5432:5432 \
     postgres:16-alpine
   ```

3. **Python Environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # or .venv\Scripts\activate on Windows
   pip install -e ".[dev]"
   ```

## Initialization Steps

### 1. Load Soul
First, load the core identity from SOUL.md and IDENTITY.md.

```python
from aria_mind import AriaMind

mind = AriaMind()
await mind.initialize()

# Verify soul loaded
print(f"I am {mind.soul.name} {mind.soul.emoji}")
```

### 2. Connect Memory
Initialize database connection and load memories.

```python
# Memory is initialized during mind.initialize()
# Verify connection
assert mind.memory.is_connected
```

### 3. Start Heartbeat
Begin health monitoring and scheduled tasks.

```python
# Heartbeat starts during mind.initialize()
assert mind.heartbeat.is_healthy
```

### 4. Load Skills
Initialize available skills and verify APIs.

```python
from aria_skills import SkillRegistry

skills = SkillRegistry()
await skills.load_from_config("aria_mind/TOOLS.md")

# Verify critical skills
assert skills.get("database").is_available
assert skills.get("moltbook").is_available
```

### 5. Register Agents
Set up sub-agents for specialized tasks.

```python
from aria_agents import AgentCoordinator

coordinator = AgentCoordinator(mind=mind, skills=skills)
await coordinator.load_agents("aria_mind/AGENTS.md")
```

## First Run Checklist

- [ ] Database migrations applied
- [ ] API keys validated
- [ ] Soul loaded successfully
- [ ] Heartbeat running
- [ ] At least one skill available
- [ ] Can store and retrieve a test thought

## Quick Test

```python
# Test the full stack
async def test_bootstrap():
    from aria_mind import AriaMind
    
    mind = AriaMind()
    assert await mind.initialize()
    
    # Test thinking
    response = await mind.think("Hello, who are you?")
    assert "Aria" in response
    
    # Test memory
    await mind.memory.store("test_key", "test_value")
    value = await mind.memory.retrieve("test_key")
    assert value == "test_value"
    
    # Clean up
    await mind.shutdown()
    print("✅ Bootstrap successful!")

import asyncio
asyncio.run(test_bootstrap())
```

## Recovery from Death

If Aria "dies" (loses state), recover using:

1. Load latest database backup
2. Re-initialize from workspace files
3. Replay any missed heartbeat tasks
4. Resume normal operation

The workspace files (SOUL.md, IDENTITY.md, etc.) are the source of truth for identity and never change during runtime.
