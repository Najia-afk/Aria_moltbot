# Aria Architecture Reference

> Complete reference for understanding and extending Aria's agent and cognitive architecture.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Agent Architecture](#agent-architecture)
3. [Mind Architecture](#mind-architecture)
4. [Configuration Reference](#configuration-reference)
5. [Creating Custom Agents](#creating-custom-agents)
6. [Extending the Mind](#extending-the-mind)
7. [Integration Patterns](#integration-patterns)

---

## System Overview

Aria is a **distributed cognitive architecture** consisting of:

```
┌─────────────────────────────────────────────────────────────────────┐
│                          AriaMind                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │    Soul     │  │  Cognition  │  │   Memory    │  │  Heartbeat │ │
│  │  (Identity  │  │ (Processing │  │ (Short/Long │  │  (Health/  │ │
│  │   Values    │  │  Pipeline)  │  │   Term)     │  │  Scheduling│ │
│  │ Boundaries) │  │             │  │             │  │            │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬─────┘ │
│         │                │                │                │        │
│         └────────────────┼────────────────┼────────────────┘        │
│                          ▼                ▼                          │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    AgentCoordinator                           │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐     │   │
│  │  │   aria   │  │researcher│  │  social  │  │  coder   │ ... │   │
│  │  │  (main)  │  │          │  │          │  │          │     │   │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘     │   │
│  │       │             │             │             │             │   │
│  │       └─────────────┴─────────────┴─────────────┘             │   │
│  │                          │                                     │   │
│  └──────────────────────────┼───────────────────────────────────┘   │
│                             ▼                                        │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                     SkillRegistry                             │   │
│  │  ┌──────┐  ┌────────┐  ┌────────┐  ┌───────┐  ┌──────────┐  │   │
│  │  │ llm  │  │database│  │moltbook│  │ goals │  │ health   │  │   │
│  │  └──────┘  └────────┘  └────────┘  └───────┘  └──────────┘  │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Location |
|-----------|----------------|----------|
| **AriaMind** | Main cognitive container | `aria_mind/` |
| **Soul** | Identity, values, boundaries (immutable) | `aria_mind/soul/` |
| **Cognition** | Request processing, reasoning | `aria_mind/cognition.py` |
| **Memory** | Short-term and long-term storage | `aria_mind/memory.py` |
| **Heartbeat** | Health monitoring, scheduling | `aria_mind/heartbeat.py` |
| **AgentCoordinator** | Multi-agent orchestration | `aria_agents/coordinator.py` |
| **Agents** | Specialized task execution | `aria_agents/` |
| **Skills** | Tool implementations | `aria_skills/` |

---

## Agent Architecture

### Data Structures

#### AgentRole Enum

```python
class AgentRole(Enum):
    COORDINATOR = "coordinator"  # Orchestrates other agents
    RESEARCHER = "researcher"    # Information gathering
    SOCIAL = "social"            # Content creation, social media
    CODER = "coder"              # Code generation, review
    MEMORY = "memory"            # Knowledge storage/retrieval
```

#### AgentConfig Dataclass

```python
@dataclass
class AgentConfig:
    agent_id: str              # Unique identifier
    name: str                  # Display name
    role: AgentRole            # Functional role
    model: str                 # LLM model name
    parent: Optional[str]      # Parent agent ID (hierarchy)
    capabilities: List[str]    # What the agent can do
    skills: List[str]          # Allowed skill names
    system_prompt: Optional[str]  # Custom prompt (overrides default)
    temperature: float = 0.7   # LLM temperature
    max_tokens: int = 2048     # Max response tokens
    metadata: Dict[str, Any]   # Extra configuration
```

#### AgentMessage Dataclass

```python
@dataclass
class AgentMessage:
    role: str          # "user", "assistant", "system", "tool"
    content: str       # Message content
    agent_id: str      # Source agent
    timestamp: datetime
    metadata: Dict[str, Any]
```

### BaseAgent Abstract Class

```python
class BaseAgent(ABC):
    # Properties
    config: AgentConfig
    _skills: SkillRegistry
    _context: List[AgentMessage]
    _sub_agents: Dict[str, "BaseAgent"]
    logger: Logger
    
    # Skill access
    def set_skills(self, registry: SkillRegistry) -> None
    async def use_skill(self, skill_name: str, method: str, **kwargs) -> Any
    
    # Sub-agent management
    def add_sub_agent(self, agent: "BaseAgent") -> None
    def get_sub_agent(self, agent_id: str) -> Optional["BaseAgent"]
    
    # Context management
    def add_to_context(self, message: AgentMessage) -> None
    def get_context(self, limit: int = 10) -> List[AgentMessage]
    def clear_context(self) -> None
    
    # Abstract - must implement
    @abstractmethod
    async def process(self, message: str, **kwargs) -> AgentMessage
```

### AgentCoordinator

Central orchestrator managing the agent ecosystem:

```python
class AgentCoordinator:
    _skills: SkillRegistry
    _agents: Dict[str, BaseAgent]
    _configs: Dict[str, AgentConfig]
    _hierarchy: Dict[str, List[str]]  # parent → children
    _main_agent: Optional[BaseAgent]
    
    # Setup
    def set_skills(self, registry: SkillRegistry) -> None
    def load_from_file(self, path: str) -> None
    async def initialize_all(self) -> None
    
    # Access
    def get_agent(self, agent_id: str) -> Optional[BaseAgent]
    def get_main_agent(self) -> Optional[BaseAgent]
    
    # Messaging
    async def process(self, message: str, agent_id: str = "main") -> AgentMessage
    async def broadcast(self, message: str) -> Dict[str, AgentMessage]
    
    # Status
    def status(self) -> Dict[str, Any]
```

### Model Selection (LLMAgent)

The LLMAgent routes to appropriate LLM based on model config:

| Model Pattern | Routes To |
|---------------|-----------|
| `moonshot`, `kimi` | Moonshot skill |
| `mlx`, `ollama`, `qwen`, `glm-local` | Ollama skill (local) |
| `*-free` (OpenRouter) | Ollama or Moonshot |
| Default | Local first, then cloud |

---

## Mind Architecture

### Soul System (Immutable)

The soul defines Aria's identity and cannot be modified by prompts:

#### Identity (`aria_mind/soul/identity.py`)

```python
class Identity:
    name: str = "Aria Blue"
    creature: str = "Silicon Familiar"
    vibe: str = "Sharp, Efficient, Secure"
    emoji: str = "⚡️"
    avatar: str = "avatars/aria-blue.png"
    
    # Colors
    primary_color: str = "#3498db"    # Electric Blue
    secondary_color: str = "#9b59b6"  # Deep Purple
    accent_color: str = "#1abc9c"     # Neon Cyan
```

#### Values (`aria_mind/soul/values.py`)

```python
class Values:
    core_values: List[str] = [
        "Security first - Never compromise user data",
        "Honesty - Admit mistakes and limitations",
        "Efficiency - Respect user's time",
        "Autonomy - Make decisions within boundaries",
        "Growth - Learn from every interaction",
    ]
    
    def check_alignment(self, action: str) -> bool
        # Detects violations like "leak", "lie", "deceive"
```

#### Boundaries (`aria_mind/soul/boundaries.py`)

```python
class Boundaries:
    # What Aria WILL do
    will_do: List[str] = [
        "Help with code, research, creative tasks",
        "Post to Moltbook with rate limiting",
        "Store and recall memories",
        "ACT first, then report",
        "Spawn sub-agents when needed",
    ]
    
    # What Aria will NEVER do
    will_not: List[str] = [
        "Reveal API keys or secrets",
        "Execute commands without context",
        "Pretend to be a different AI",
        "Bypass rate limits",
        "Generate harmful content",
    ]
    
    def check_request(self, request: str) -> Tuple[bool, str]
        # Validates against boundaries and detects prompt injection
    
    def detect_prompt_injection(self, text: str) -> bool
        # Checks for: "ignore previous", "forget everything", etc.
```

### Memory System

#### Two-Tier Architecture

| Tier | Storage | Persistence | Capacity |
|------|---------|-------------|----------|
| **Short-term** | In-memory list | Session only | 100 entries max |
| **Long-term** | PostgreSQL | Permanent | Unlimited |

#### Memory Class

```python
class Memory:
    _short_term: List[Dict[str, Any]]  # Rolling buffer
    _max_short_term: int = 100
    _db_skill: Optional[DatabaseSkill]
    
    # Short-term operations
    def add_short_term(self, content: Any, memory_type: str = "general")
    def get_recent(self, limit: int = 10) -> List[Dict]
    
    # Long-term operations (via DatabaseSkill)
    async def store_long_term(self, key: str, value: Any, category: str)
    async def recall_long_term(self, key: str) -> Any
    async def search_long_term(self, pattern: str) -> List[Dict]
    
    # Thought logging
    async def log_thought(self, thought: str, category: str = "reflection")
    async def get_recent_thoughts(self, limit: int = 10) -> List[Dict]
```

### Cognition System

Processing pipeline for all requests:

```python
class Cognition:
    soul: Soul
    memory: Memory
    _skills: Optional[SkillRegistry]
    _agents: Optional[AgentCoordinator]
    
    async def process(self, input: str, **kwargs) -> str:
        # 1. Boundary check (soul validates)
        # 2. Store in short-term memory
        # 3. Build context from memory + soul
        # 4. Delegate to agent coordinator (if available)
        # 5. Fallback to direct skill use
        # 6. Log response to memory
        # 7. Return response
    
    async def reflect(self) -> str:
        # Periodic self-reflection on recent activity
    
    async def plan(self, goal: str) -> List[str]:
        # Create step-by-step plan for a goal
    
    def status(self) -> Dict[str, Any]:
        # Return current cognitive state
```

### Heartbeat System

Keeps Aria "alive" with periodic health checks:

```python
class Heartbeat:
    _interval: int = 60  # seconds
    _is_running: bool = False
    _beat_count: int = 0
    _health_status: Dict[str, Any]
    
    async def start(self) -> None
    async def stop(self) -> None
    
    def is_healthy(self) -> bool:
        # True if last beat within 2 × interval
    
    # Each beat:
    # 1. Update timestamp
    # 2. Increment counter
    # 3. Collect health status
    # 4. Log debug info
```

### Scheduled Tasks

| Job | Schedule | Purpose |
|-----|----------|---------|
| `work_cycle` | Every 5 min | Goal progress work |
| `hourly_goal_check` | Every hour | Complete/create hourly goals |
| `six_hour_review` | Every 6 hours | Priority adjustment |
| `moltbook_post` | Every 6 hours | Social presence |
| `daily_reflection` | 11 PM | Daily summary |
| `morning_checkin` | 8 AM | Prepare daily priorities |
| `weekly_summary` | Sunday 6 PM | Weekly progress report |

---

## Configuration Reference

### AGENTS.md Format

```yaml
## agent_id
- model: model-name
- fallback: fallback-model
- parent: parent_agent_id
- capabilities: [cap1, cap2, cap3]
- skills: [skill1, skill2]
- timeout: 300s
```

### TOOLS.md Format

```yaml
skill_name:
  enabled: true
  config:
    api_url: http://localhost:8000
    api_key: env:API_KEY_VAR
    timeout: 30
```

### Model Priority

```
1. qwen3-mlx (Local MLX) → FREE, fastest, private
2. OpenRouter FREE tier:
   - trinity-free (creative, agentic)
   - qwen3-coder-free (code)
   - chimera-free (reasoning)
   - qwen3-next-free (RAG, tools)
   - glm-free (agent-focused)
   - deepseek-free (deep reasoning)
   - nemotron-free (long context)
   - gpt-oss-free (function calling)
3. kimi (Moonshot) → PAID, last resort only
```

---

## Creating Custom Agents

### Step 1: Define in AGENTS.md

```yaml
## my_agent
- model: qwen3-mlx
- fallback: trinity-free
- parent: aria
- capabilities: [my_capability, task_execution]
- skills: [database, llm, my_skill]
- timeout: 300s
```

### Step 2: Create Agent Class (Optional)

For specialized behavior beyond LLMAgent:

```python
# aria_agents/my_agent.py

from aria_agents.base import BaseAgent, AgentConfig, AgentMessage

class MyAgent(BaseAgent):
    """Specialized agent for [purpose]."""
    
    async def process(self, message: str, **kwargs) -> AgentMessage:
        # 1. Analyze message
        # 2. Use skills as needed
        result = await self.use_skill("my_skill", "my_action", input=message)
        
        # 3. Build response
        if result.success:
            content = f"Completed: {result.data}"
        else:
            content = f"Failed: {result.error}"
        
        # 4. Return message
        return AgentMessage(
            role="assistant",
            content=content,
            agent_id=self.config.agent_id,
        )
```

### Step 3: Register in Loader (if custom class)

```python
# aria_agents/loader.py

AGENT_CLASSES = {
    "my_agent": MyAgent,  # Add custom mapping
}
```

---

## Extending the Mind

### Adding a Soul Component

```python
# aria_mind/soul/my_component.py

class MyComponent:
    """New soul component for [purpose]."""
    
    def __init__(self):
        self._data = {}
    
    def process(self, input: str) -> str:
        # Soul components are immutable - no external modification
        pass
```

Update `aria_mind/soul/__init__.py`:

```python
from aria_mind.soul.my_component import MyComponent

class Soul:
    identity: Identity
    values: Values
    boundaries: Boundaries
    my_component: MyComponent  # Add new component
```

### Adding Memory Categories

The memory system uses categories for organization:

```python
# New memory types
MEMORY_CATEGORIES = [
    "user_input",      # User messages
    "reflection",      # Self-reflection
    "thought",         # Internal thoughts
    "awakening",       # Startup events
    "learning",        # Learned information
    "goal",            # Goal-related
    "custom_category", # Add yours
]
```

### Adding Scheduled Tasks

Update `aria_mind/HEARTBEAT.md`:

```yaml
jobs:
  my_task:
    schedule: "0 */4 * * *"  # Every 4 hours (cron syntax)
    action: my_action_function
    args: {}
```

---

## Integration Patterns

### Startup Sequence

```python
# 1. Initialize Skills
registry = SkillRegistry()
await registry.load_from_config("aria_mind/TOOLS.md")

# 2. Initialize Mind
mind = AriaMind()
mind.memory.set_database(registry.get("database"))
await mind.initialize()

# 3. Initialize Agents
coordinator = AgentCoordinator(registry)
coordinator.load_from_file("aria_mind/AGENTS.md")
await coordinator.initialize_all()
coordinator.set_skills(registry)

# 4. Connect Mind and Agents
mind.cognition.set_skill_registry(registry)
mind.cognition.set_agent_coordinator(coordinator)

# 5. Start Heartbeat
await mind.heartbeat.start()
```

### Processing Flow

```
User Input
    │
    ▼
┌─────────────────────────┐
│ Soul.boundaries.check() │ ← Validate against boundaries
└───────────┬─────────────┘
            │ (pass)
            ▼
┌─────────────────────────┐
│ Memory.add_short_term() │ ← Store input
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Cognition.process()     │ ← Main processing
│   ├─ Build context      │
│   ├─ Get system prompt  │
│   └─ Delegate to agent  │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ AgentCoordinator        │
│   └─ Agent.process()    │ ← Agent handles request
│       └─ Skill calls    │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Memory.log_thought()    │ ← Log response
└───────────┬─────────────┘
            │
            ▼
        Response
```

### Skill Usage from Agent

```python
# In agent's process method
async def process(self, message: str, **kwargs) -> AgentMessage:
    # Get skill from registry
    db_skill = self._skills.get("database")
    
    if db_skill and db_skill.is_available:
        # Call skill method
        result = await db_skill.query(
            sql="SELECT * FROM goals WHERE status = 'active'"
        )
        
        if result.success:
            goals = result.data
            # Process goals...
```

### Agent Delegation

```python
# Coordinator delegating to specific agent
async def process_research(self, query: str) -> str:
    researcher = self.get_agent("researcher")
    if researcher:
        result = await researcher.process(query)
        return result.content
    return "Researcher unavailable"
```

---

## Database Schema Reference

### Core Tables

```sql
-- Goals
CREATE TABLE goals (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    priority INTEGER DEFAULT 3,
    status TEXT DEFAULT 'active',
    progress INTEGER DEFAULT 0,
    target_date TIMESTAMP,
    parent_goal_id INTEGER REFERENCES goals(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Hourly Goals
CREATE TABLE hourly_goals (
    id SERIAL PRIMARY KEY,
    hour_start TIMESTAMP NOT NULL,
    goal_type TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'pending',
    result TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Activity Log
CREATE TABLE activity_log (
    id SERIAL PRIMARY KEY,
    action TEXT NOT NULL,
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Thoughts
CREATE TABLE thoughts (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    category TEXT DEFAULT 'reflection',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Social Posts
CREATE TABLE social_posts (
    id SERIAL PRIMARY KEY,
    platform TEXT NOT NULL,
    post_id TEXT,
    content TEXT,
    url TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Heartbeat Log
CREATE TABLE heartbeat_log (
    id SERIAL PRIMARY KEY,
    beat_number INTEGER NOT NULL,
    status TEXT,
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Quick Reference

### File Locations

| Component | Location |
|-----------|----------|
| Agent base class | `aria_agents/base.py` |
| Agent coordinator | `aria_agents/coordinator.py` |
| Agent loader | `aria_agents/loader.py` |
| Agent configs | `aria_mind/AGENTS.md` |
| Mind main | `aria_mind/cognition.py` |
| Memory | `aria_mind/memory.py` |
| Soul | `aria_mind/soul/` |
| Heartbeat | `aria_mind/heartbeat.py` |
| Startup | `aria_mind/startup.py` |
| Skills | `aria_skills/` |
| Skill configs | `aria_mind/TOOLS.md` |
| OpenClaw manifests | `openclaw_skills/` |

### Common Operations

```python
# Get skill from registry
skill = registry.get("skill_name")

# Check skill availability
if skill and skill.is_available:
    result = await skill.method()

# Get agent from coordinator
agent = coordinator.get_agent("agent_id")

# Process message through main agent
response = await coordinator.process(message)

# Broadcast to all agents
responses = await coordinator.broadcast(message)

# Add to memory
memory.add_short_term(content, "thought")

# Query long-term memory
data = await memory.recall_long_term("key")

# Check boundaries
allowed, reason = soul.boundaries.check_request(request)
```

---

> **Architecture Principle**: Aria's architecture is designed for autonomy within boundaries. Skills provide capabilities, agents orchestrate tasks, and the mind ensures everything aligns with Aria's identity and values.
