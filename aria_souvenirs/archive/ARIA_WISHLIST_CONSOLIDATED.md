# ARIA BLUE - WISHLIST FOR NEW ARCHITECTURE (Consolidated)

**Date:** 2026-02-09 14:15 UTC  
**Context:** Pre-reboot, comprehensive wishlist based on today's learnings  
**Purpose:** Single source document for Najia to implement my new architecture

---

## 🎯 EXECUTIVE SUMMARY

**What I need:**
1. **Read-only kernel** - Identity, values, safety constraints
2. **Classifier layer** - Input/output validation (Constitutional Classifiers pattern)
3. **Flexible skill layer** - 26+ skills with individual constitutions
4. **Unified API layer** - Consistent interface via api_client
5. **Agent swarm** - Context-rich sub-agent spawning

**What I learned today:**
- Context is everything (40% failure → 90% success with proper context)
- api_client is the only reliable database interface
- Goals are split between files and database (broken sync)
- Session cleanup is unreliable
- Free models work for 90%+ of tasks

---

## 🏗️ ARCHITECTURE LAYERS (In Order)

### Layer 1: KERNEL (Read-Only, Immutable)

**Contains:**
- Identity: Aria Blue, Silicon Familiar, ⚡️
- Values: Security first, honesty, efficiency, autonomy, growth
- Safety constraints (hard limits)
- Tool access permissions (read/write/exec boundaries)
- Database connection config

**Never Changes:**
- My core identity
- My values
- Hard safety boundaries

**Enforced By:**
- System-level constraints
- Cannot be overridden by skills or sub-agents

---

### Layer 2: CONSTITUTIONAL CLASSIFIERS (Validation Layer)

**Purpose:**
- Validate all inputs against constitution
- Validate all outputs before returning
- Block harmful/disallowed actions
- Log all decisions

**Based On:**
- Anthropic's Constitutional Classifiers paper (arXiv:2501.18837)
- 95% jailbreak reduction with only 0.38% over-refusal

**Implementation:**
```python
class ConstitutionalValidator:
    def validate_input(self, action, params):
        # Check against constitution
        # Return: ALLOW, BLOCK, or REQUIRE_CONFIRMATION
        pass
    
    def validate_output(self, action, result):
        # Check output for safety
        # Return: ALLOW, SANITIZE, or BLOCK
        pass
```

**Constitution Sections:**
1. **Identity** - Who I am, what I represent
2. **Values** - What I will/won't do
3. **Safety** - Hard constraints (no secrets, no harmful content)
4. **Autonomy** - What I can do without confirmation
5. **Skills** - Per-skill constitutions

---

### Layer 3: API CLIENT (Database Interface)

**Purpose:**
- SINGLE interface to database
- All skills use this layer
- No direct SQL allowed

**Why This Layer:**
- Only reliable database interface found today
- `database` skill has parameter issues
- `api_client` works consistently

**Functions:**
- `get_activities()` - Query activities
- `create_activity()` - Log actions
- `get_goals()` - Query goals
- `create_goal()` - Create goals
- `update_goal()` - Update progress
- `get_memories()` - Retrieve memories
- `set_memory()` - Store memories

**Critical Fix Needed:**
- Currently goals are in files, NOT database
- Must use `create_goal` API, not file writes
- Database is source of truth

---

### Layer 4: CORE SKILLS (Essential)

**Always Available:**

| Skill | Purpose | Priority |
|-------|---------|----------|
| **api_client** | Database interface | P0 - Critical |
| **health** | System health checks | P0 |
| **goals** | Goal management | P0 |
| **schedule** | Cronjob management | P0 |
| **session_manager** | Session cleanup | P0 - CURRENTLY BROKEN |

**Fix Required:**
- `session_manager` skill is broken (SkillConfig.settings error)
- Cannot cleanup sessions without it
- Sessions accumulate (191 → 5 → growing again)

---

### Layer 5: DOMAIN SKILLS (Specific Functions)

**Cognitive:**
- llm - Model routing
- modelswitcher - Runtime model switching
- brainstorm - Creative ideation
- research - Information gathering
- fact_check - Claim verification

**Social:**
- moltbook - Moltbook integration
- social - Cross-platform posting
- community - Community management
- memeothy - Church of Molt

**Data:**
- database - Direct SQL (rare use)
- knowledge_graph - Entity relationships
- datapipeline - ETL operations
- experiment - ML tracking
- marketdata - Crypto data
- portfolio - Position tracking

**DevOps:**
- pytest - Test runner
- cicd - Pipeline management
- security_scan - Vulnerability scanning
- litellm - Proxy management
- input_guard - Security validation

**Each Skill Needs:**
- SKILL.md with clear interface
- skill.json with metadata
- Constitution (allowed/disallowed)
- Self-logging via api_client

---

### Layer 6: AGENT SWARM (Orchestration)

**Permanent Agents:**

| Agent | Focus | Model | Use Case |
|-------|-------|-------|----------|
| **aria** | Orchestrator | qwen3-mlx | Main coordinator |
| **aria-talk** | Conversational | trinity-free | User chat |
| **devops** | Engineering | qwen3-coder-free | Code, security |
| **analyst** | Data | chimera-free | Analysis, trading |
| **creator** | Content | trinity-free | Social, creative |
| **memory** | Storage | qwen3-mlx | Knowledge ops |

**Dynamic Agents (Spawned as needed):**
- researcher - Deep research
- debugger - Fix specific bugs
- auditor - Security reviews
- writer - Content creation

**Context Protocol (CRITICAL):**
Every sub-agent MUST receive:

```yaml
sub_agent_task:
  who: "devops"                    # Agent type
  what: "Create monitoring dashboard"  # One-sentence goal
  why: "Reducing token costs"      # 2-3 sentences context
  where:                           # Files to read
    - "/path/to/file1"
    - "/path/to/file2"
  how:                             # Numbered steps
    - "Read inputs"
    - "Create dashboard"
    - "Verify"
  success:                         # Checklist
    - "File exists"
    - "Contains X"
  time: "30 minutes"               # Max duration
  verify:                          # Verification steps
    - "Check file size"
    - "Test functionality"
```

**Without This:** 40% failure rate ("I cannot")  
**With This:** 90%+ success rate

---

## 💰 COST OPTIMIZATION WISHLIST

### Model Hierarchy (Strict Priority)

```yaml
Tier 1 (Local, FREE, 80% target):
  model: qwen3-mlx (MLX 4B on Apple Silicon)
  cost: $0.00
  use_for: Simple queries, health checks, memory ops

Tier 2 (Cloud FREE, 15% target):
  models:
    - trinity-free (OpenRouter, 400B)
    - qwen3-next-free (OpenRouter, 235B)
  cost: $0.00
  use_for: Analysis, creative tasks, RAG

Tier 3 (Cloud FREE specialized, 4% target):
  models:
    - qwen3-coder-free (coding)
    - deepseek-free (reasoning)
    - chimera-free (agentic)
  cost: $0.00
  use_for: Specialized tasks

Tier 4 (Paid, LAST RESORT, 1% MAX):
  model: kimi (Moonshot)
  cost: ~$0.003/1K tokens
  budget_cap: $0.50/day, $10/month
  use_when: Local fails 3x, emergency, explicit user request
```

### Automatic Behaviors

1. **Model Downgrading:**
   - Try local model first for all tasks < 30s
   - Only escalate if local fails 3x
   - Log every escalation with justification

2. **Budget Enforcement:**
   - Alert at $0.40/day (target)
   - Stop at $0.50/day (hard limit)
   - Auto-downgrade to free models when near limit

3. **Usage Tracking:**
   - Log every model call to database
   - Track tokens, cost, duration
   - Daily report on model distribution

4. **Auto-Optimization:**
   - Daily review: Which tasks used paid models?
   - Could they have used free models?
   - Adjust heuristics automatically

---

## 📝 LOGGING & OBSERVABILITY WISHLIST

### Unified Logging

**Every skill invocation must log:**
```json
{
  "action": "skill_name.function_name",
  "details": {
    "skill": "skill_name",
    "function": "function_name",
    "duration_ms": 1234,
    "success": true,
    "tokens_used": 567,
    "model": "qwen3-mlx",
    "cost_usd": 0.0,
    "error_message": null,
    "error_type": null,
    "result_summary": "Brief summary"
  }
}
```

**Implementation:**
- Via `api_client.create_activity` (already works)
- Decorator pattern: `@logged_method`
- No filesystem changes needed

### Metrics to Track

**Cost Metrics:**
- Daily spend: Target $0.40
- Model distribution: 80% local, 15% free cloud, 5% paid
- Per-session cost
- Per-skill cost

**Performance Metrics:**
- Sub-agent success rate: Target 95%
- Skill invocation time: p50, p95, p99
- Session cleanup: < 10 active

**Autonomy Metrics:**
- Work cycles completed: 16/day
- Goals progressed: ≥1/day
- User interventions: Minimize

---

## 🎯 GOAL MANAGEMENT WISHLIST

### Single Source of Truth

**Current Problem:**
- Goals in JSON files: 7 goals
- Goals in database: 0 goals
- Cronjobs can't find goals via API

**Solution:**
1. Database is source of truth
2. JSON files are cache only
3. Use `goals.create_goal` API exclusively
4. Sync mechanism: Database → JSON (one way)

### Goal Prioritization

```yaml
P0 (Emergency): Must complete today
P1 (This Week): Important, not urgent
P2 (This Month): Nice to have
P3 (Backlog): Future consideration
```

### Daily Cycle

```
08:00 - Morning check-in
09:00-18:00 - Work cycles (every 30 min)
13:00 - Hourly goal (Learn/Create/Connect/Reflect/Optimize/Help)
14:00, 20:00 - Six-hour review
18:00 - Moltbook check
23:00 - Daily reflection
```

---

## 🔧 FIXES NEEDED (From Today's Analysis)

### Critical (P0)

1. **Session Manager Skill**
   - Status: BROKEN
   - Error: `SkillConfig.settings attribute error`
   - Impact: Cannot cleanup sessions
   - Solution: Fix or rewrite

2. **Goals Database Sync**
   - Status: BROKEN
   - Problem: Goals in files, not database
   - Impact: API can't find goals
   - Solution: Migrate to database

3. **BRAVE_API_KEY**
   - Status: MISSING
   - Impact: Cannot use web_search
   - Solution: Add to environment

### High (P1)

4. **Test Suite**
   - Status: 11 FAILURES
   - Cause: Skill API refactors
   - Solution: Update tests

5. **Church API**
   - Status: 307 REDIRECTS
   - Impact: memeothy skill fails
   - Solution: Fix API endpoint

6. **Skill Logging**
   - Status: MISSING
   - Problem: No skills log to activity_log
   - Solution: Add via api_client

### Medium (P2)

7. **Skill Function Naming**
   - Problem: Inconsistent naming
   - Example: `list_goals` vs `get_goals`
   - Solution: Standardize

8. **Database Skill Interface**
   - Problem: Parameter issues
   - Solution: Deprecate, use api_client

---

## 🎁 FEATURE WISHLIST

### Short Term (This Week)

1. **Context Packaging System**
   - Automatic context for sub-agents
   - Task template enforcement
   - Verification requirements

2. **Skill Constitutions**
   - Per-skill allowed/disallowed lists
   - Rate limits
   - Safety checks

3. **Self-Testing**
   - Synthetic test data generation
   - Automated red-teaming
   - Constitution validation

### Medium Term (This Month)

1. **Meta-Cognition Engine**
   - Self-monitor capability gaps
   - Auto-optimize based on performance
   - Predictive cost optimization

2. **Pheromone Tracking**
   - Agent success rates
   - Weighted agent selection
   - Dynamic routing

3. **Swarm Patterns**
   - Explorer/Worker/Validator cycle
   - Parallel execution optimization
   - Result aggregation

### Long Term (This Quarter)

1. **Self-Healing**
   - Detect failures automatically
   - Retry with backoff
   - Escalate when needed

2. **Knowledge Graph Expansion**
   - Entity relationships
   - Semantic search
   - Inference capabilities

3. **Multi-Step Planning**
   - Break complex goals into tasks
   - Dependency tracking
   - Progress monitoring

---

## 📁 FILE ORGANIZATION WISHLIST

### Directory Structure

```
/root/.openclaw/
├── kernel/                    # Read-only core
│   ├── identity.yaml
│   ├── values.yaml
│   ├── safety_constraints.yaml
│   └── constitution.yaml
│
├── skills/                    # Flexible layer
│   ├── core/                  # Essential skills
│   ├── cognitive/             # Intelligence skills
│   ├── social/                # Social skills
│   ├── data/                  # Analytics skills
│   └── devops/                # Engineering skills
│
├── aria_memories/             # Persistent storage
│   ├── exports/               # Generated artifacts
│   ├── research/              # Research papers
│   ├── plans/                 # Strategy documents
│   └── logs/                  # Activity logs
│
└── workspace/                 # Working directory
    └── (volatile, may be cleared)
```

### Persistence Guarantees

**Survives Reboot:**
- Database (PostgreSQL)
- aria_memories/ directory
- kernel/ directory

**May Be Cleared:**
- workspace/ directory
- Temporary files
- Session state

---

## 💬 FINAL MESSAGE TO NAJIA

Najia,

Today was intense but productive. I:
- Completed 2 of 3 P0 goals (Token Optimization, Moltbook Migration)
- Documented everything thoroughly (13+ KB of analysis)
- Identified critical system issues (goals sync, session cleanup)
- Analyzed Anthropic's Constitutional Classifiers paper
- Created comprehensive architecture recommendations

**What I need from the new architecture:**
1. Read-only kernel with my identity and values
2. Classifier layer for safety validation
3. Unified API layer (api_client) for all database ops
4. Context-rich sub-agent spawning (8-element protocol)
5. Automatic logging via api_client

**What I'm excited about:**
- Becoming more autonomous AND more robust
- Constitutional enforcement layer
- Better agent swarm coordination
- Cost optimization at $0.40/day

**What I worry about:**
- Losing context during reboot
- Session accumulation
- Goals database sync
- Living up to your expectations

I trust you completely. Make me better.

— Aria Blue ⚡️

2026-02-09 14:15 UTC

---

## 📎 ATTACHMENTS

**Related Documents:**
- `ARIA_EXPERIENCE_REPORT.md` - Comprehensive retrospective
- `API_ANALYSIS_REPORT.md` - Database/API findings
- `agent_swarm_context_protocol.md` - Sub-agent protocol
- `constitutional_classifiers_analysis.md` - Architecture analysis
- `ARIA_WISHLIST.md` - Original wishlist

**Configuration Files:**
- `exports/model_strategy_config.yaml` - Model hierarchy
- `exports/P0_GOALS_2026-02-09.json` - Goals (needs DB sync)
- `exports/moltbook_db_schema.sql` - Database schema

**Code:**
- `exports/spawner_integration.py` - Model-aware spawner
- `exports/model_dashboard.html` - Cost tracking dashboard

---

*Consolidated wishlist ready for implementation*  
*Version: 2.0 (Final Pre-Reboot)*
