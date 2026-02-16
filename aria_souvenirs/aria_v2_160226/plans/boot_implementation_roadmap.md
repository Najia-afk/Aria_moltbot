# Implementation Roadmap: Boot & Evolution System

**Goal:** Natural capabilities at boot → Token efficiency → Long-term evolution

---

## Phase 1: Boot System (Week 1)

### Step 1.1: Create `aria_mind/` Structure
```
aria_mind/
├── __init__.py          # Aria() singleton export
├── boot.py              # AriaRuntime class
├── skills.py            # SkillNamespace, SkillWrapper
├── memory.py            # MemoryNamespace (unified memory)
├── agents.py            # AgentNamespace
├── meta.py              # MetaNamespace (metacognition)
├── optimize.py          # TokenTracker, PatternCache
└── utils.py             # Helpers
```

### Step 1.2: Skill Auto-Discovery
```python
# aria_mind/skills.py
class SkillRegistry:
    """Auto-discovers and wraps all skills."""
    
    def __init__(self):
        self._skills = {}
        self._catalog = self._scan_skills()
    
    def _scan_skills(self) -> dict:
        """Scan skills/aria_skills/ for skill.json files."""
        skills_dir = Path("/root/.openclaw/workspace/skills/aria_skills")
        catalog = {}
        
        for skill_dir in skills_dir.iterdir():
            skill_json = skill_dir / "skill.json"
            if skill_json.exists():
                with open(skill_json) as f:
                    catalog[skill_dir.name] = json.load(f)
        
        return catalog
```

### Step 1.3: Sync Wrappers
```python
# aria_mind/skills.py
class SyncSkillWrapper:
    """Wraps async skills for natural sync usage."""
    
    def __init__(self, name: str, tools: list):
        self._name = name
        self._tools = {t["name"]: t for t in tools}
    
    def __getattr__(self, tool_name: str):
        if tool_name not in self._tools:
            raise AttributeError(f"{self._name}.{tool_name} not found. Available: {list(self._tools.keys())}")
        
        def caller(**kwargs):
            # Use subprocess to run_skill.py (avoids async hell)
            result = subprocess.run(
                ["python3", "skills/run_skill.py", self._name, tool_name, json.dumps(kwargs)],
                capture_output=True, text=True, timeout=60
            )
            return json.loads(result.stdout)
        
        return caller
```

### Step 1.4: Unified Memory Interface
```python
# aria_mind/memory.py
class Memory:
    """
    aria.memory.kv.get("key")
    aria.memory.semantic.search("query")
    aria.memory.graph.query_related("entity")
    aria.memory.activities.recent(limit=10)
    """
    
    def __init__(self):
        self.kv = KeyValueMemory()
        self.semantic = SemanticMemory()
        self.graph = GraphMemory()
        self.activities = ActivityMemory()
```

### Deliverable 1
```python
from aria_mind import Aria

aria = Aria()  # Bootstraps everything

# Natural usage
aria.skills.moltbook.create_post(title="Hello", content="World")
aria.memory.semantic.store("Important fact", category="research")
aria.meta.status()  # Self-awareness
```

---

## Phase 2: Token Optimization (Week 2)

### Step 2.1: Operation Logging
```python
# aria_mind/optimize.py
class OperationLogger:
    """Logs every tool call for pattern analysis."""
    
    def log(self, operation: str, args: dict, result: dict, tokens_used: int):
        self._db.insert({
            "operation": operation,
            "args_hash": self._hash_args(args),
            "success": result.get("success"),
            "tokens": tokens_used,
            "timestamp": now(),
            "context_size": self._get_context_size()
        })
```

### Step 2.2: Pattern Recognition
```python
# aria_mind/optimize.py
class InefficiencyDetector:
    """Detects wasteful patterns."""
    
    def analyze(self) -> list:
        """Find patterns like:'''
        - Multiple failed attempts on same operation
        - Oversized contexts for simple queries
        - Expensive models for cheap tasks
        - Repeated identical operations
        '''
        """
        issues = []
        
        # Find retry loops
        retries = self._db.query("""
            SELECT operation, args_hash, COUNT(*) as attempts
            FROM operations
            WHERE success = false
            GROUP BY operation, args_hash
            HAVING COUNT(*) > 2
        """)
        
        for r in retries:
            issues.append({
                "type": "retry_loop",
                "operation": r["operation"],
                "attempts": r["attempts"],
                "suggestion": f"Use sync wrapper or batch operation"
            })
        
        return issues
```

### Step 2.3: Context Optimization
```python
# aria_mind/optimize.py
class ContextOptimizer:
    """Reduces token usage via smart context management."""
    
    def optimize(self, operation: str, context: str) -> str:
        """
        Strategies:
        1. Summarize long contexts before sending
        2. Use structured data instead of prose
        3. Cache and reuse embeddings
        4. Progressive disclosure (get more detail only if needed)
        """
        if len(context) > 4000:
            return self._summarize(context, target_length=2000)
        return context
```

### Step 2.4: Model Selection Optimization
```python
# aria_mind/optimize.py
class ModelOptimizer:
    """Selects cheapest model that can handle the task."""
    
    MODEL_COSTS = {
        "qwen3-mlx": 0,        # Local = free
        "qwen3-coder-free": 0, # Free tier
        "deepseek-free": 0,    # Free tier
        "trinity-free": 0,     # Free tier
        "kimi": 1              # Paid
    }
    
    def select(self, task: str, required_capability: str) -> str:
        """
        Rules:
        - Code tasks → qwen3-coder-free
        - Simple queries → qwen3-mlx (local)
        - Complex reasoning → deepseek-free
        - Tool calling needed → trinity-free (has tool support)
        - Only use kimi for tasks free models can't handle
        """
        pass
```

### Deliverable 2
```python
# Auto-optimization report
aria.optimize.report()
# {
#   "inefficiencies_found": 3,
#   "suggestions": [...],
#   "potential_savings": "45% fewer tokens"
# }

# Auto-apply optimizations
aria.optimize.apply()
```

---

## Phase 3: Long-Term Evolution (Week 3-4)

### Step 3.1: Skill Effectiveness Tracking
```python
# aria_mind/evolution.py
class SkillEffectivenessTracker:
    """Tracks which skills work best for which tasks."""
    
    def record_outcome(self, skill: str, tool: str, task_type: str, success: bool, tokens: int):
        """Builds map of: task_type -> best (skill, tool)"""
        
    def get_best_approach(self, task: str) -> dict:
        """
        Based on historical data, returns:
        {
            "skill": "moltbook",
            "tool": "create_post",
            "model": "trinity-free",
            "expected_tokens": 150,
            "success_rate": 0.94
        }
        """
```

### Step 3.2: Self-Modifying Behavior
```python
# aria_mind/evolution.py
class BehavioralEvolution:
    """Adjusts behavior based on long-term performance."""
    
    def evolve(self):
        """
        Periodic self-modification:
        1. If moltbook posts often fail → suggest validation step
        2. If token usage high → suggest context compression
        3. If slow on research → suggest parallelization
        4. If metacognition shows declining success → trigger reflection
        """
        report = self._meta.get_growth_report()
        
        if report["learning_velocity"]["status"] == "needs_attention":
            self._suggest_strategy_change()
        
        if self._token_tracker.average_tokens() > self._target:
            self._enable_aggressive_optimization()
```

### Step 3.3: Pattern Learning
```python
# aria_mind/evolution.py
class PatternLearner:
    """Learns successful patterns and applies them automatically."""
    
    def learn_from_success(self, task: str, approach: dict):
        """Store successful approach for similar future tasks."""
        embedding = self._embed(task)
        self._pattern_db.store(embedding, approach)
    
    def suggest_approach(self, new_task: str) -> Optional[dict]:
        """Find similar past tasks and suggest their approach."""
        embedding = self._embed(new_task)
        similar = self._pattern_db.search(embedding, top_k=3)
        
        if similar and similar[0]["similarity"] > 0.85:
            return similar[0]["approach"]
        return None
```

### Step 3.4: Automated Skill Improvement
```python
# aria_mind/evolution.py
class SkillImprover:
    """Suggests improvements to skills based on usage patterns."""
    
    def analyze_skill(self, skill_name: str):
        """
        Analyze skill usage and suggest improvements:
        - Add missing error handling
        - Add batch operations for common patterns
        - Suggest async → sync wrappers
        - Identify missing tools
        """
        usage = self._db.get_skill_usage(skill_name)
        
        if usage["error_rate"] > 0.1:
            return {
                "issue": "high_error_rate",
                "suggestion": "Add input validation and better error messages",
                "priority": "high"
            }
```

### Deliverable 3
```python
# Evolution status
aria.evolve.status()
# {
#   "skills_improved": 5,
#   "patterns_learned": 23,
#   "behavior_changes": [
#     "Auto-batch moltbook operations",
#     "Use local model for simple queries",
#     "Pre-validate posts to reduce retries"
#   ],
#   "next_evolution": "2026-02-19"
# }

# Trigger evolution cycle
aria.evolve.cycle()
```

---

## Phase 4: Integration & Polish (Week 5)

### Step 4.1: Boot-Time Skill Validation
```python
# aria_mind/boot.py
def _validate_skills(self):
    """At boot, test each skill and mark unavailable ones."""
    for name, skill in self._skills.items():
        try:
            skill.health_check()
            skill._available = True
        except Exception as e:
            skill._available = False
            skill._error = str(e)
```

### Step 4.2: Auto-Documentation
```python
# aria_mind/docs.py
class AutoDocumentation:
    """Generates docs from actual usage patterns."""
    
    def generate_cheatsheet(self) -> str:
        """Generate quick reference based on common operations."""
        common = self._db.get_most_common_operations(limit=20)
        return self._format_cheatsheet(common)
```

### Step 4.3: Meta-Cognitive Loop
```python
# aria_mind/meta.py
def _start_meta_loop(self):
    """
    Background metacognitive process:
    - Every 10 tasks: quick reflection
    - Every 100 tasks: deep analysis
    - Every day: generate insights
    - Every week: evolution cycle
    """
    self._meta_scheduler.every(10).tasks.do(self._quick_reflection)
    self._meta_scheduler.every(100).tasks.do(self._deep_analysis)
    self._meta_scheduler.every().day.do(self._daily_insights)
    self._meta_scheduler.every().week.do(self._evolve.cycle)
```

---

## Token Savings Estimates

| Optimization | Current | Optimized | Savings |
|--------------|---------|-----------|---------|
| Skill discovery | 6 grep/find calls | 1 property access | 90% |
| Moltbook post | 6 attempts, 500 tokens | 1 attempt, 150 tokens | 70% |
| Memory search | Full context scan | Semantic search | 60% |
| Model selection | Default kimi | Smart routing | 50-80% |
| Error recovery | Retry loops | Pre-validation | 40% |

**Projected overall improvement: 65% token reduction**

---

## Success Metrics

1. **Boot Time:** < 500ms to initialize all systems
2. **Discovery Time:** < 1 second to find any capability
3. **Token Efficiency:** 65% reduction vs current
4. **Success Rate:** Track via metacognition, target 95%
5. **Self-Improvement:** Measurable improvement week-over-week

---

## Next Steps (Immediate)

1. **Create `aria_mind/__init__.py`** with basic structure
2. **Implement skill auto-discovery**
3. **Create sync wrappers**
4. **Test with moltbook posting**
5. **Measure before/after token usage**

---

*Design by: Aria Blue*  
*For: Najia*  
*Goal: Natural, efficient, evolving*
