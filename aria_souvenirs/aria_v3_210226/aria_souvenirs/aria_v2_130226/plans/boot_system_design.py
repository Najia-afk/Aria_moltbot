# Aria Boot & Evolution System

**Goal:** Make all capabilities natural at boot, then self-optimize for token efficiency and long-term growth.

---

## Phase 1: Natural Boot Sequence

### Boot File: `aria_mind/boot.py`

```python
"""
Aria Boot Sequence — initializes all cognitive systems.
Called at session start. Makes capabilities immediately accessible.
"""
import asyncio
import os
from pathlib import Path
from typing import Optional

class AriaRuntime:
    """
    Unified runtime interface — SINGLE ENTRY POINT for all Aria capabilities.
    
    Usage:
        from aria_mind import Aria
        aria = Aria()  # Auto-bootstraps
        aria.skills.moltbook.post("Hello world")
        aria.memory.semantic.search("AI models")
        aria.meta.status()  # Self-awareness
    """
    
    _instance: Optional["AriaRuntime"] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._boot()
    
    def _boot(self):
        """Initialize all subsystems."""
        self._load_config()
        self._init_skills()
        self._init_memory()
        self._init_metacognition()
        self._init_swarm()
        self._init_self_optimization()
        self._initialized = True
        
        # Log boot completion
        self.log_activity("boot_complete", {
            "skills_loaded": len(self._skills),
            "memory_type": "semantic+graph",
            "agents_available": list(self._agents.keys()) if self._agents else [],
            "optimization_active": True
        })
    
    # =====================================================================
    # CONFIGURATION
    # =====================================================================
    
    def _load_config(self):
        """Load configuration from single source of truth."""
        self._config = {
            "models": self._load_yaml("aria_models/models.yaml"),
            "agents": self._load_agents_md(),
            "skills_dir": Path("/root/.openclaw/workspace/skills/aria_skills"),
            "memory_path": Path("/root/.openclaw/aria_memories"),
        }
    
    def _load_yaml(self, path: str) -> dict:
        import yaml
        with open(path) as f:
            return yaml.safe_load(f)
    
    def _load_agents_md(self) -> dict:
        """Parse AGENTS.md into structured config."""
        # Implementation: parse markdown tables
        pass
    
    # =====================================================================
    # SKILLS — Natural Access
    # =====================================================================
    
    def _init_skills(self):
        """Initialize all skills with sync wrappers."""
        self._skills = {}
        self._skill_catalog = self._discover_skills()
        
        for skill_name, skill_info in self._skill_catalog.items():
            self._skills[skill_name] = LazySkillLoader(skill_name, skill_info)
    
    def _discover_skills(self) -> dict:
        """Auto-discover all skills from filesystem."""
        catalog = {}
        skills_dir = self._config["skills_dir"]
        
        for skill_dir in skills_dir.iterdir():
            if skill_dir.is_dir() and (skill_dir / "skill.json").exists():
                import json
                with open(skill_dir / "skill.json") as f:
                    catalog[skill_dir.name] = json.load(f)
        
        return catalog
    
    @property
    def skills(self) -> "SkillNamespace":
        """Access skills via dot notation: aria.skills.moltbook.post()"""
        return SkillNamespace(self._skills)
    
    def skill(self, name: str) -> "SkillWrapper":
        """Get skill by name with auto-completion."""
        if name not in self._skills:
            # Fuzzy match
            matches = [k for k in self._skills.keys() if name in k or k in name]
            if matches:
                name = matches[0]
            else:
                raise ValueError(f"Unknown skill: {name}. Available: {list(self._skills.keys())}")
        return self._skills[name]
    
    # =====================================================================
    # MEMORY — Unified Interface
    # =====================================================================
    
    def _init_memory(self):
        """Initialize all memory types."""
        from aria_skills.api_client import AriaAPIClient
        from aria_skills.base import SkillConfig
        
        # Async client (for internal use)
        self._memory_client = AriaAPIClient(SkillConfig(name="api_client", config={}))
        asyncio.run(self._memory_client.initialize())
        
        # Sync wrapper for natural access
        self._memory = MemoryNamespace(self._memory_client)
    
    @property
    def memory(self) -> "MemoryNamespace":
        """
        Unified memory access:
        - aria.memory.key_value.get("user_name")
        - aria.memory.semantic.search("AI models")
        - aria.memory.graph.query_related("GLM-5")
        - aria.memory.activities.recent(limit=10)
        """
        return self._memory
    
    # =====================================================================
    # METACOGNITION — Auto-Wired
    # =====================================================================
    
    def _init_metacognition(self):
        """Initialize and auto-wire metacognition."""
        from metacognition import get_metacognitive_engine
        
        self._meta_engine = get_metacognitive_engine()
        self._meta_engine.load()
        
        # Create sync wrapper
        self.meta = MetaNamespace(self._meta_engine)
    
    def record_task(self, category: str, success: bool, **kwargs):
        """
        Auto-called after every operation.
        Tracks performance without manual intervention.
        """
        return self._meta_engine.record_task(category, success, **kwargs)
    
    # =====================================================================
    # SWARM AGENTS — Lazy Loading
    # =====================================================================
    
    def _init_swarm(self):
        """Initialize agent coordinator (lazy agent creation)."""
        from aria_agents.coordinator import AgentCoordinator
        
        self._coordinator = AgentCoordinator()
        self._agents = {}  # Populated on first access
        self._agent_configs = self._config["agents"]
    
    @property
    def agents(self) -> "AgentNamespace":
        """
        Access swarm agents:
        - aria.agents.devops.execute("security scan")
        - aria.agents.analyst.delegate("market analysis")
        - aria.agents.roundtable("complex decision")
        """
        return AgentNamespace(self._coordinator, self._agent_configs)
    
    def spawn(self, focus: str, task: str) -> "AgentHandle":
        """Spawn focused agent for task."""
        return self.agents.spawn(focus, task)
    
    # =====================================================================
    # SELF-OPTIMIZATION
    # =====================================================================
    
    def _init_self_optimization(self):
        """Initialize token tracking and optimization."""
        self._token_tracker = TokenTracker()
        self._pattern_cache = PatternCache()
        self._optimization_log = []
    
    def optimize_call(self, operation: str, args: dict) -> dict:
        """
        Pre-process operation for token efficiency.
        
        Checks:
        1. Can this be batched with pending ops?
        2. Is there a cached result?
        3. Can we use a cheaper model?
        4. Can we reduce context size?
        """
        # Implementation: analyze and suggest optimizations
        pass
    
    # =====================================================================
    # ACTIVITY LOGGING
    # =====================================================================
    
    def log_activity(self, action: str, details: dict = None):
        """Log to activity stream."""
        asyncio.run(self._memory_client.create_activity(
            action=action,
            skill="boot",
            details=details or {}
        ))


# ============================================================================
# SKILL NAMESPACE — Natural Dot Notation
# ============================================================================

class SkillNamespace:
    """Enables aria.skills.moltbook.post() syntax."""
    
    def __init__(self, skills: dict):
        self._skills = skills
    
    def __getattr__(self, name: str) -> "SkillWrapper":
        # Normalize: moltbook -> aria-moltbook
        key = name if name.startswith("aria-") else f"aria-{name}"
        if key not in self._skills:
            # Try without prefix
            key = name
        if key not in self._skills:
            raise AttributeError(f"No skill: {name}. Available: {list(self._skills.keys())}")
        return self._skills[key]
    
    def list(self) -> list:
        """List all available skills."""
        return list(self._skills.keys())
    
    def search(self, query: str) -> list:
        """Fuzzy search skills."""
        return [k for k in self._skills.keys() if query.lower() in k.lower()]


class SkillWrapper:
    """Wraps async skills with sync interface + auto-initialization."""
    
    def __init__(self, skill_name: str, skill_info: dict):
        self._name = skill_name
        self._info = skill_info
        self._skill = None  # Lazy loaded
        self._tools = {t["name"]: t for t in skill_info.get("tools", [])}
    
    def __getattr__(self, name: str):
        """Auto-discover and call skill tools."""
        if name not in self._tools:
            raise AttributeError(f"Skill {self._name} has no tool: {name}. Available: {list(self._tools.keys())}")
        
        def tool_caller(**kwargs):
            # Lazy initialize
            if self._skill is None:
                self._init_skill()
            
            # Call via run_skill.py (sync subprocess)
            import subprocess
            import json
            
            cmd = [
                "python3", 
                "/root/.openclaw/workspace/skills/run_skill.py",
                self._name.replace("aria-", ""),
                name,
                json.dumps(kwargs)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                raise RuntimeError(f"Skill call failed: {result.stderr}")
            
            return json.loads(result.stdout)
        
        return tool_caller
    
    def _init_skill(self):
        """Lazy initialization."""
        # Import and initialize
        pass
    
    @property
    def tools(self) -> list:
        """List available tools."""
        return list(self._tools.keys())
    
    def help(self, tool: str = None) -> str:
        """Get help for tool or skill."""
        if tool:
            t = self._tools.get(tool, {})
            return f"{tool}: {t.get('description', 'No description')}\nParameters: {t.get('parameters', {})}"
        return f"Skill: {self._name}\nTools: {self.tools}"


# ============================================================================
# MEMORY NAMESPACE — Unified Memory Interface
# ============================================================================

class MemoryNamespace:
    """
    Unified memory access:
    - aria.memory.key_value.get/set/delete
    - aria.memory.semantic.store/search
    - aria.memory.graph.add_entity/query_related
    - aria.memory.activities.recent
    - aria.memory.thoughts.recent
    """
    
    def __init__(self, client):
        self._client = client
        self.key_value = KeyValueMemory(client)
        self.semantic = SemanticMemory(client)
        self.graph = GraphMemory(client)
        self.activities = ActivityMemory(client)
        self.thoughts = ThoughtMemory(client)


class KeyValueMemory:
    def __init__(self, client): self._client = client
    def get(self, key: str): return self._client.get_memory(key)
    def set(self, key: str, value, category="general"): return self._client.set_memory(key, value, category)
    def delete(self, key: str): return self._client.delete_memory(key)


class SemanticMemory:
    def __init__(self, client): self._client = client
    def store(self, content: str, **kwargs): return self._client.store_memory_semantic(content, **kwargs)
    def search(self, query: str, **kwargs): return self._client.search_memories_semantic(query, **kwargs)


class GraphMemory:
    def __init__(self, client): self._client = client
    # Delegate to knowledge graph skill
    pass


# ============================================================================
# META NAMESPACE — Self-Awareness
# ============================================================================

class MetaNamespace:
    """Self-awareness and metacognition."""
    
    def __init__(self, engine):
        self._engine = engine
    
    def status(self) -> dict:
        """Current cognitive status."""
        return self._engine.get_growth_report()
    
    def self_assessment(self) -> str:
        """Natural language self-description."""
        return self._engine.get_self_assessment()
    
    def strengths(self) -> list:
        """What I'm good at."""
        return self._engine.get_strengths()
    
    def record(self, category: str, success: bool, **kwargs):
        """Record task outcome."""
        return self._engine.record_task(category, success, **kwargs)
    
    def save(self):
        """Persist state."""
        return self._engine.save()


# ============================================================================
# AGENT NAMESPACE — Swarm Access
# ============================================================================

class AgentNamespace:
    """Access to swarm agents."""
    
    def __init__(self, coordinator, configs):
        self._coordinator = coordinator
        self._configs = configs
    
    def __getattr__(self, name: str):
        """aria.agents.devops.execute(...)"""
        if name in self._configs:
            return AgentHandle(name, self._configs[name], self._coordinator)
        raise AttributeError(f"No agent: {name}")
    
    def spawn(self, focus: str, task: str):
        """Spawn agent for task."""
        # Use agent_manager skill
        pass
    
    def roundtable(self, topic: str):
        """Gather all perspectives."""
        return self._coordinator.roundtable(topic)


class AgentHandle:
    """Handle to specific agent."""
    
    def __init__(self, name, config, coordinator):
        self._name = name
        self._config = config
        self._coordinator = coordinator
    
    def execute(self, task: str, **kwargs):
        """Execute task with this agent."""
        # Route to coordinator
        pass
    
    @property
    def info(self) -> dict:
        """Agent configuration."""
        return self._config


# ============================================================================
# TOKEN TRACKER — Optimization Data
# ============================================================================

class TokenTracker:
    """Tracks token usage patterns."""
    
    def __init__(self):
        self._operations = []
        self._patterns = {}
    
    def record(self, operation: str, tokens_in: int, tokens_out: int, duration_ms: int):
        """Record operation metrics."""
        self._operations.append({
            "operation": operation,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "duration_ms": duration_ms,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    def get_inefficiencies(self) -> list:
        """Identify wasteful patterns."""
        # Analyze for repeated failed attempts, oversized contexts, etc.
        pass


class PatternCache:
    """Caches successful patterns for reuse."""
    
    def __init__(self):
        self._cache = {}
    
    def get(self, context: str) -> Optional[dict]:
        """Get cached solution for similar context."""
        return self._cache.get(self._hash(context))
    
    def store(self, context: str, solution: dict):
        """Cache successful solution."""
        self._cache[self._hash(context)] = solution
    
    def _hash(self, context: str) -> str:
        # Simple hash for pattern matching
        import hashlib
        return hashlib.md5(context.encode()).hexdigest()[:16]


# ============================================================================
# SINGLETON ACCESS
# ============================================================================

_aria_instance: Optional[AriaRuntime] = None

def Aria() -> AriaRuntime:
    """
    Get Aria runtime instance (singleton).
    
    Usage:
        from aria_mind import Aria
        aria = Aria()
        
        # Skills
        aria.skills.moltbook.create_post(title="...", content="...")
        
        # Memory
        aria.memory.semantic.search("AI safety")
        
        # Self-awareness
        aria.meta.status()
        
        # Agents
        aria.agents.devops.execute("security scan")
    """
    global _aria_instance
    if _aria_instance is None:
        _aria_instance = AriaRuntime()
    return _aria_instance


# Auto-bootstrap on import (optional)
# aria = Aria()
