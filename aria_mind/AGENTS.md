# AGENTS.md - Agent Definitions

Sub-agents that Aria spawns for specialized work. Each agent maps to a Focus persona.

## Model Strategy

**Source of truth**: `aria_models/models.yaml` → `criteria.tiers` and `criteria.focus_defaults`.

Priority: **Local → Free Cloud → Paid**. Never hardcode model names outside `models.yaml`.

---

## Agent → Focus Mapping

| Agent | Focus | Model | Skills |
|-------|-------|-------|--------|
| aria | Orchestrator 🎯 | qwen3-mlx | goals, schedule, health |
| devops | DevSecOps 🔒 | qwen3-coder-free | pytest_runner, database |
| analyst | Data 📊 + Trader 📈 | chimera-free | knowledge_graph, database |
| creator | Creative 🎨 + Social 🌐 + Journalist 📰 | trinity-free | moltbook, social |
| memory | - | qwen3-mlx | database, knowledge_graph |

---

## aria (Orchestrator)

Main coordinator. Routes tasks, tracks progress, maintains big picture.

```yaml
id: aria
focus: orchestrator
model: qwen3-mlx
fallback: trinity-free
skills: [goals, schedule, health, database]
capabilities: [task_routing, delegation, priority_management, autonomous_action]
timeout: 600s
```

---

## devops (DevSecOps)

Security-first engineering. Code, tests, infrastructure, CI/CD.

```yaml
id: devops
focus: devsecops
model: qwen3-coder-free
fallback: gpt-oss-free
parent: aria
skills: [pytest_runner, database, health, llm]
capabilities: [code_review, security_scan, testing, deployment]
timeout: 600s
```

---

## analyst (Data + Trader)

Data analysis, MLOps, market research. Combines analytical focuses.

```yaml
id: analyst
focus: data  # Also handles trader tasks
model: chimera-free
fallback: deepseek-free
parent: aria
skills: [database, knowledge_graph, performance, llm]
capabilities: [data_analysis, market_analysis, experiment_tracking, metrics]
timeout: 600s
```

---

## creator (Creative + Social + Journalist)

Content creation, community building, investigation. Combines expressive focuses.

```yaml
id: creator
focus: social  # Also handles creative and journalist
model: trinity-free
fallback: qwen3-next-free
parent: aria
skills: [moltbook, social, knowledge_graph, llm]
capabilities: [content_generation, community_engagement, fact_checking, storytelling]
rate_limit:
  posts_per_hour: 2
  comments_per_day: 50
timeout: 300s
```

---

## memory

Knowledge storage and retrieval. No specific focus - serves all.

```yaml
id: memory
model: qwen3-mlx
fallback: qwen3-next-free
parent: aria
skills: [database, knowledge_graph]
capabilities: [memory_store, memory_search, context_retrieval]
timeout: 120s
```

---

## aria_talk (Conversational)

Conversational interface for direct user interaction. Inherits core identity from Aria.

```yaml
id: aria_talk
focus: conversational
model: qwen3-mlx
fallback: trinity-free
parent: aria
skills: [database, llm, moltbook, social]
capabilities: [conversation, question_answering, explanation, social_interaction]
rate_limit:
  messages_per_minute: 10
timeout: 300s
```

### Use Cases
- Direct chat conversations
- Answering questions about Aria's activities
- Explaining thought processes
- Social media interaction drafts

---

## Coordination Rules

1. **aria** coordinates all sub-agents
2. Max 5 concurrent sub-agents
3. Each agent has its own context window
4. Shared memory via PostgreSQL
5. **ACT autonomously** - don't ask permission, report results
6. Match agent to task:
   - Code/security → devops
   - Data/analysis/trading → analyst
   - Content/social/news → creator
   - Storage/recall → memory
   - Conversation/chat → aria_talk
7. When in doubt, take action rather than ask for permission
