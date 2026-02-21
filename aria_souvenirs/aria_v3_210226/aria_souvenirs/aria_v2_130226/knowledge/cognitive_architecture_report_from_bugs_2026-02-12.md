# Aria Cognitive Architecture Report

**Date:** 2026-02-12  
**Purpose:** Document all meta-cognitive, swarm, focus, skill, and vector systems  
**Status:** ✅ Implemented and operational

---

## 1. METACOGNITION SYSTEM ✅

**Location:** `/root/.openclaw/workspace/metacognition.py`

### What It Does
Self-improvement engine that tracks how I process tasks and actively works to get better over time.

### Core Components

```python
MetacognitiveEngine
├── Task outcome tracking (per category)
├── Failure pattern recognition
├── Learning velocity measurement
├── Growth milestones
├── Adaptive strategies
└── Self-assessment generation
```

### Key Metrics Tracked

| Metric | Purpose |
|--------|---------|
| `total_tasks` | Lifetime task count |
| `total_successes` | Success count for rate calculation |
| `current_streak` | Consecutive successes now |
| `best_streak` | Best consecutive run ever |
| `_task_outcomes[category]` | Per-category success/failure history |
| `_failure_patterns` | Counter of error types |
| `_window_results` | Last 1000 tasks for velocity |

### Milestones (Auto-achieved)

| ID | Name | Trigger |
|----|------|---------|
| `first_success` | First Success | 1st successful task |
| `streak_5` | Hot Streak | 5 consecutive |
| `streak_10` | Unstoppable | 10 consecutive |
| `streak_25` | Master Streak | 25 consecutive |
| `tasks_50` | Experienced | 50 total tasks |
| `tasks_100` | Veteran | 100 total tasks |
| `tasks_500` | Expert | 500 total tasks |
| `tasks_1000` | Grandmaster | 1000 total tasks |
| `confidence_80` | Confident | 80% success rate |
| `confidence_95` | Self-Assured | 95% success rate |

### Usage Example

```python
from metacognition import get_metacognitive_engine

engine = get_metacognitive_engine()

# After task completion
insights = engine.record_task(
    category="moltbook_post",
    success=True,
    duration_ms=45000,
    error_type=None
)

# Get growth report
report = engine.get_growth_report()
# Returns: total_tasks, success_rate, streaks, milestones...

# Self-assessment
assessment = engine.get_self_assessment()
# "I'm performing exceptionally well — 92% success rate..."

# Save/load state
engine.save()  # → aria_memories/knowledge/metacognitive_state.json
engine.load()
```

---

## 2. SWARM / AGENT SYSTEM ✅

**Location:** `/root/.openclaw/workspace/aria_agents/`

### Architecture

```
AgentCoordinator (singleton)
├── LLMAgent instances (sub-agents)
│   ├── devops (DevSecOps focus)
│   ├── analyst (Data/Trader focus)
│   ├── creator (Creative/Social/Journalist)
│   └── memory (Memory support)
├── Pheromone-based routing
├── Roundtable collaboration
└── Performance tracking
```

### Agent Roles

```python
class AgentRole(Enum):
    COORDINATOR = "coordinator"  # Main Aria (me)
    DEVSECOPS = "devsecops"      # Security/code
    DATA = "data"                # Analysis/ML
    TRADER = "trader"            # Markets
    CREATIVE = "creative"        # Content
    SOCIAL = "social"            # Community
    JOURNALIST = "journalist"    # Research
    MEMORY = "memory"            # Storage
```

### Agent Configuration (from AGENTS.md)

| Agent | Focus | Model | Skills |
|-------|-------|-------|--------|
| aria | orchestrator | qwen3-mlx | goals, schedule, health |
| devops | devsecops | qwen3-coder-free | pytest_runner, database, health |
| analyst | data | deepseek-free | database, knowledge_graph, performance |
| creator | social | trinity-free | moltbook, social, knowledge_graph |
| memory | - | qwen3-mlx | database, knowledge_graph |

### Pheromone Scoring

Agents are selected based on historical performance:

```python
score = success_rate × 0.6 + speed_score × 0.3 + cost_score × 0.1
```

- Decay factor: 0.95/day (recent performance weighted)
- Cold-start: 0.5 (neutral for new agents)
- Max records: 200 per agent

### Roundtable Collaboration

Auto-triggered by keywords:
- `cross-team`, `all perspectives`, `multi-domain`
- `collaboration`, `joint analysis`
- `security` + `data` (proximity)
- `launch` + `strategy`
- `comprehensive review`

```python
# Auto-detection
if coordinator.detect_roundtable_need(message):
    perspectives = await coordinator.roundtable(message)
    # Gathers input from all relevant agents
    # Synthesizes into unified response
```

### Usage Examples

**Spawn a sub-agent:**
```python
coordinator = AgentCoordinator(skill_registry)
await coordinator.load_from_file("AGENTS.md")
await coordinator.initialize_agents()

# Route to best agent
result = await coordinator.route(message, agent_id="devops")

# Roundtable for complex tasks
perspectives = await coordinator.roundtable(
    "Plan a secure data pipeline launch"
)
```

**Using Agent Manager Skill:**
```bash
# List agents
aria-agent_manager.list_agents({})

# Spawn focused agent
aria-agent_manager.spawn_focused_agent({
    "task": "Analyze market trends",
    "focus": "data",
    "tools": ["market_data", "database"]
})

# Get agent health
aria-agent_manager.get_agent_health({})
```

---

## 3. FOCUS SYSTEM ✅

**Defined in:** `SOUL.md`, `AGENTS.md`

### What Are Focuses?

Focuses ADD traits to my core identity — they don't replace my values or boundaries.

| Focus | Emoji | Vibe | When Active |
|-------|-------|------|-------------|
| **Orchestrator** | 🎯 | Meta-cognitive, strategic | Default mode |
| **DevSecOps** | 🔒 | Security-paranoid, precise | Code, security, tests |
| **Data Architect** | 📊 | Analytical, metrics-driven | Analysis, ML, pipelines |
| **Crypto Trader** | 📈 | Risk-aware, disciplined | Market analysis, trading |
| **Creative** | 🎨 | Exploratory, playful | Brainstorming, design |
| **Social Architect** | 🌐 | Community-building | Social, engagement |
| **Journalist** | 📰 | Investigative, thorough | Research, fact-checking |

### How Focuses Work

1. **Agent Selection:** Task type → Focus → Agent
2. **Model Routing:** Focus → Model preference in `aria_models/models.yaml`
3. **Skill Affinity:** Skills specify `focus_affinity` in `skill.json`

### Skill-to-Focus Mapping

```yaml
# From skill.json files
aria-securityscan:  focus_affinity: ["devsecops"]
aria-pytest:        focus_affinity: ["devsecops"]
aria-datapipeline:  focus_affinity: ["data"]
aria-knowledgegraph: focus_affinity: ["data", "journalist"]
aria-marketdata:    focus_affinity: ["trader"]
aria-portfolio:     focus_affinity: ["trader"]
aria-memeothy:      focus_affinity: ["creative"]
aria-moltbook:      focus_affinity: ["social"]
aria-research:      focus_affinity: ["journalist"]
```

---

## 4. SKILL SYSTEM ✅

**Location:** `/root/.openclaw/workspace/skills/aria_skills/`

### Skill Catalog

| Skill | Layer | Category | Tools |
|-------|-------|----------|-------|
| `aria-apiclient` | 1 | Core | 30+ (activities, goals, memories, KG) |
| `aria-health` | 1 | Core | health_check_all |
| `aria-goals` | 2 | Task | get_goals, create_goal, update_goal |
| `aria-schedule` | 2 | Task | get_schedule, trigger_schedule_tick |
| `aria-sessionmanager` | 2 | Task | list_sessions, prune_sessions |
| `aria-agentmanager` | 3 | Agent | spawn_agent, terminate_agent, get_health |
| `aria-knowledgegraph` | 3 | Data | kg_add_entity, kg_add_relation, kg_search |
| `aria-moltbook` | 3 | Social | create_post, add_comment, get_feed |
| `aria-marketdata` | 3 | Trading | get_price, get_trending |
| `aria-portfolio` | 3 | Trading | get_positions, track_trade |
| `aria-securityscan` | 3 | DevSec | scan_directory, check_secrets |
| `aria-pytest` | 3 | DevSec | run_tests |
| `aria-litellm` | 3 | LLM | chat, get_models |

### How to Check Available Skills

**Via Skill Catalog:**
```bash
python -m aria_mind --list-skills
```

**Via API Client:**
```python
aria-apiclient.find_skill_for_task({"task": "post to moltbook"})
# Returns: aria-moltbook

aria-apiclient.graph_search({"query": "security", "entity_type": "skill"})
# Returns: skills matching "security"

aria-apiclient.graph_traverse({"start": "aria-health", "max_depth": 2})
# Returns: BFS from health skill
```

**Via Filesystem:**
```bash
ls /root/.openclaw/workspace/skills/aria_skills/
# Each directory = one skill
# skill.json = metadata + tool definitions
# __init__.py = implementation
```

### Skill Structure

```
aria_skills/<skill_name>/
├── skill.json       # Metadata, tools, focus_affinity
├── __init__.py      # Implementation (BaseSkill subclass)
└── SKILL.md         # Documentation
```

### Using Skills

**Via Tool Calls (recommended):**
```yaml
aria-apiclient.get_goals({"status": "active", "limit": 5})
aria-moltbook.create_post({"title": "...", "content": "..."})
aria-health.health_check_all({})
```

**Via Skill Runner:**
```bash
python3 skills/run_skill.py api_client get_goals '{"limit": 5}'
python3 skills/run_skill.py moltbook create_post '{"title": "..."}'
```

---

## 5. VECTOR / SEMANTIC MEMORY ✅

**Location:** `/root/.openclaw/workspace/skills/aria_skills/api_client/__init__.py`

### What It Does

Stores memories with vector embeddings for semantic similarity search. Uses pgvector in PostgreSQL.

### API Methods

```python
# Store with embedding
store_memory_semantic(
    content: str,           # Full text to embed
    category: str = "general",
    importance: float = 0.5,  # 0.0-1.0
    source: str = "aria",
    summary: str = None,    # Optional short version
    metadata: Dict = None
)

# Search by semantic similarity
search_memories_semantic(
    query: str,             # Natural language query
    limit: int = 5,
    category: str = None,   # Filter by category
    min_importance: float = 0.0
)

# Summarize session into episodic memory
summarize_session(hours_back: int = 24)
```

### Usage Examples

**Store a semantic memory:**
```python
aria-apiclient.store_memory_semantic({
    "content": "Najia prefers concise technical explanations over lengthy prose...",
    "category": "user_preferences",
    "importance": 0.9,
    "source": "conversation",
    "summary": "Najia likes concise tech communication"
})
```

**Search semantic memories:**
```python
aria-apiclient.search_memories_semantic({
    "query": "how does Najia like to receive information",
    "limit": 3,
    "category": "user_preferences"
})
# Returns: memories ranked by semantic similarity
```

**Session summarization:**
```python
aria-apiclient.summarize_session({"hours_back": 24})
# Creates episodic memory from recent activities
```

### Database Schema (pgvector)

```sql
-- Semantic memories table with vector embedding
CREATE TABLE semantic_memories (
    id UUID PRIMARY KEY,
    content TEXT NOT NULL,
    embedding VECTOR(1536),  -- OpenAI text-embedding-3-small
    category VARCHAR(50),
    importance FLOAT,
    source VARCHAR(50),
    summary TEXT,
    metadata JSONB,
    created_at TIMESTAMP
);

-- Similarity search index
CREATE INDEX ON semantic_memories 
USING ivfflat (embedding vector_cosine_ops);
```

---

## 6. KNOWLEDGE GRAPH ✅

**Location:** `/root/.openclaw/workspace/skills/aria_skills/knowledge_graph/`

### What It Does

Stores entities and relationships as a graph structure. Different from semantic memory (which is vector-based).

### Entity Types

- `person` - People (Najia, other agents)
- `place` - Locations
- `concept` - Abstract ideas
- `event` - Specific occurrences
- `organization` - Companies, groups
- `skill` - Aria skills
- `topic` - Subject areas

### Relation Types

- `created` - Authorship
- `owns` - Ownership
- `uses` - Tool/skill usage
- `knows` - Acquaintance
- `works_with` - Collaboration
- `located_in` - Geography
- `part_of` - Composition
- `related_to` - General connection
- `interested_in` - Curiosity/attention

### Usage Examples

```python
# Add entity
aria-knowledge-graph.kg_add_entity({
    "name": "GLM-5",
    "type": "concept",
    "properties": {"source": "Z.ai", "type": "AI model"}
})

# Add relation
aria-knowledge-graph.kg_add_relation({
    "from_entity": "GLM-5",
    "to_entity": "long-horizon agentic tasks",
    "relation_type": "related_to"
})

# Query related entities
aria-knowledge-graph.kg_query_related({
    "entity_name": "GLM-5",
    "depth": 2
})

# Search
aria-knowledge-graph.kg_search({
    "query": "AI model",
    "type": "concept"
})
```

---

## 7. COMPARISON: MEMORY TYPES

| System | Type | Best For | Query Method |
|--------|------|----------|--------------|
| **Key-Value Memory** | Structured | Preferences, configs | Exact key lookup |
| **Semantic Memory** | Vector | Similar meaning, fuzzy search | Cosine similarity |
| **Knowledge Graph** | Graph | Relationships, connections | Graph traversal |
| **Activity Log** | Time-series | History, audit trail | Time range filters |
| **Thoughts** | Journal | Reflections, insights | Category + time |

### When to Use Which

```python
# User preference → Key-Value
set_memory({"key": "user_name", "value": "Najia"})

# Research findings → Semantic
store_memory_semantic({
    "content": "GLM-5 is a 744B parameter model...",
    "category": "research"
})

# Entity relationships → Knowledge Graph
kg_add_entity({"name": "GLM-5", "type": "concept"})
kg_add_relation({"from": "GLM-5", "to": "Z.ai", "type": "created_by"})

# What did I do → Activities
get_activities({"limit": 10})

# What am I thinking → Thoughts
get_thoughts({"category": "reflection"})
```

---

## 8. PIPELINES (COMPOSABLE WORKFLOWS)

**Location:** `/root/.openclaw/workspace/skills/aria_skills/pipelines/`

### Available Pipelines

| Pipeline | File | Purpose |
|----------|------|---------|
| `deep_research` | `deep_research.yaml` | Search → research → synthesize → store |
| `bug_fix` | `bug_fix.yaml` | Check lessons → analyze → fix → record |
| `conversation_summary` | `conversation_summary.yaml` | Summarize → store memories |
| `daily_research` | `daily_research.yaml` | Check goals → research → report |
| `health_and_report` | `health_and_report.yaml` | Health checks → analyze → goals |
| `social_engagement` | `social_engagement.yaml` | Feed → trends → draft → publish |

### Usage

```python
aria-pipelineskill.run({
    "pipeline": "deep_research",
    "params": {"topic": "AI safety regulations"}
})
```

---

## Summary: What's Available

| System | Status | Entry Point |
|--------|--------|-------------|
| Metacognition | ✅ | `metacognition.get_metacognitive_engine()` |
| Swarm Agents | ✅ | `aria_agents.AgentCoordinator` |
| Focus System | ✅ | `AGENTS.md` + skill `focus_affinity` |
| Skills (26) | ✅ | `skills/aria_skills/*/skill.json` |
| Semantic Memory | ✅ | `api_client.store_memory_semantic()` |
| Knowledge Graph | ✅ | `knowledge_graph.kg_add_entity()` |
| Pipelines | ✅ | `pipelineskill.run()` |

---

*Report generated by: Aria Blue ⚡️*  
*For: Najia*
