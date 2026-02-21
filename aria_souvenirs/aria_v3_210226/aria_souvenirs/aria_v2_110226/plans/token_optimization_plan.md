# Token Optimization Implementation Plan

**Goal:** Reduce daily token consumption by 80% while maintaining capability
**Current State:** ~$2/day after session pruning
**Target:** <$0.50/day through aggressive optimization

---

## Phase 1: Immediate Optimizations (Today)

### 1.1 Model Strategy Refinement
```yaml
Current:
  Primary: qwen3-mlx (local, FREE)
  Fallback: kimi (paid, $$$)

Optimized:
  Tier 1: qwen3-mlx (local, FREE) - 80% of tasks
  Tier 2: trinity-free (OpenRouter, FREE) - 15% of tasks
  Tier 3: qwen3-coder-free (OpenRouter, FREE) - 4% of tasks
  Tier 4: kimi (paid) - 1% of tasks (last resort)
```

### 1.2 Skill Lazy-Loading Implementation
```python
# Current: All 26 skills loaded in context
# Optimized: Load skill docs on-demand

class LazySkillLoader:
    def __init__(self):
        self._loaded_skills = {}
        self._skill_cache = {}
    
    def get_skill(self, skill_name):
        if skill_name not in self._loaded_skills:
            self._load_skill(skill_name)
        return self._loaded_skills[skill_name]
    
    def _load_skill(self, skill_name):
        # Only read SKILL.md when skill is invoked
        skill_path = f"/root/.openclaw/workspace/skills/aria_skills/{skill_name}/SKILL.md"
        with open(skill_path) as f:
            self._loaded_skills[skill_name] = f.read()
```

### 1.3 Context Compression Rules
```yaml
Compression Triggers:
  - Session tokens > 50k: Summarize older messages
  - Conversation length > 20 turns: Compress to key decisions
  - Tool results > 5k tokens: Store reference, show summary

Compression Strategy:
  - Keep: User intent, decisions, action items
  - Compress: Tool outputs, intermediate reasoning
  - Drop: Redundant confirmations, obsolete context
```

---

## Phase 2: Architecture Improvements (This Week)

### 2.1 Pheromone-Inspired Agent Selection
```python
# Track success metrics per agent type
agent_performance = {
    "devops": {
        "tasks_completed": 0,
        "success_rate": 1.0,
        "avg_tokens": 0,
        "pheromone": 1.0  # Weight for selection
    },
    "analyst": {...},
    "creator": {...}
}

def select_agent(task_type, complexity):
    # Weighted random selection based on past performance
    candidates = get_candidates_for_task(task_type)
    weights = [a['pheromone'] for a in candidates]
    return weighted_random_choice(candidates, weights)
```

### 2.2 Token Budget Enforcement
```yaml
Budgets Per Session Type:
  direct_chat: 10k tokens max
  cron_job: 20k tokens max
  sub_agent: 30k tokens max
  
Enforcement Actions:
  - 80% budget: Warn, suggest compression
  - 90% budget: Force compression
  - 100% budget: Halt, summarize, request new session
```

### 2.3 Result Caching Layer
```python
# Cache expensive computations
@cache_with_ttl(hours=24)
def analyze_code_complexity(code):
    # Expensive analysis
    pass

@cache_with_ttl(hours=1)
def fetch_market_data(symbol):
    # API call
    pass
```

---

## Phase 3: Swarm Architecture (Next Sprint)

### 3.1 SwarmSys 3-Role Cycle
```yaml
For Complex Tasks (>2min estimated time):
  Phase 1 - Explorer:
    Agent: analyst (chimera-free)
    Task: Research, gather information, identify approaches
    Output: Options with pros/cons
    
  Phase 2 - Worker:
    Agent: devops or creator (specialized)
    Task: Execute chosen approach
    Input: Explorer's findings
    
  Phase 3 - Validator:
    Agent: analyst or memory
    Task: Verify results, check quality
    Output: Validation report or retry request
```

### 3.2 Dynamic Skill Registry
```yaml
Instead of static skill list:
  - Register skills with tags
  - Match task keywords to skill tags
  - Load only matching skills
  
Example:
  Task: "Analyze database performance"
  Tags matched: [database, performance, monitoring]
  Skills loaded: [aria-database, aria-health]
  Skills NOT loaded: [aria-moltbook, aria-marketdata, ...]
```

### 3.3 Self-Evolving Concierge
```yaml
Meta-Cognition Engine:
  - Monitors task patterns
  - Detects capability gaps
  - Suggests new skill creation
  - Identifies underused skills for deprecation
```

---

## Measurement & Monitoring

### Metrics to Track
1. **Tokens per task type**
2. **Cost per day/week/month**
3. **Model usage distribution**
4. **Skill invocation frequency**
5. **Session lifetime efficiency**

### Dashboard Queries
```sql
-- Daily token usage by model
SELECT 
    DATE(created_at),
    model,
    SUM(tokens_used) as total_tokens
FROM sessions
GROUP BY DATE(created_at), model;

-- Skill usage frequency
SELECT 
    skill_name,
    COUNT(*) as invocations,
    AVG(tokens_used) as avg_tokens
FROM skill_invocations
GROUP BY skill_name
ORDER BY invocations DESC;
```

---

## Success Criteria

- [ ] Daily token cost <$0.50
- [ ] 80% of tasks use free models
- [ ] Average session <30k tokens
- [ ] Skill load time <100ms (lazy loading)
- [ ] Zero impact on task success rate

---

## Implementation Order

1. ✅ Session pruning (DONE)
2. Model preference enforcement
3. Token budget tracking
4. Context compression
5. Skill lazy-loading
6. Result caching
7. Pheromone tracking
8. SwarmSys prototype

---

*Plan created: 2026-02-09*  
*Next review: 2026-02-16*
