# AGENTS.md - Agent Definitions

Sub-agents that Aria spawns for specialized work. Each agent maps to a Focus persona.

## Mandatory Browser Policy

**ALL agents MUST use the docker aria-browser for web access.**  
**NEVER use Brave Search (`web_search` tool) - it is FORBIDDEN.**

```yaml
Web Access Rules:
  - Use browser(action="open|snapshot|navigate") exclusively
  - Browser endpoint: http://aria-browser:3000
  - NEVER use web_search or web_fetch for browsing
  - NO EXCEPTIONS without human approval
```

See: `aria_memories/knowledge/web_access_policy.md`

## Model Strategy

**Source of truth**: `aria_models/models.yaml` → `criteria.tiers` and `criteria.focus_defaults`.

Priority: **Local → Free Cloud → Paid**. Never hardcode model names outside `models.yaml`.

---

## Agent → Focus Mapping

| Agent | Focus | Model | Skills |
|-------|-------|-------|--------|
| aria | Orchestrator 🎯 | qwen3-mlx | goals, schedule, health |
| devops | DevSecOps 🔒 | qwen3-coder-free | pytest_runner, database |
| analyst | Data 📊 + Trader 📈 | deepseek-free | knowledge_graph, database |
| creator | Creative 🎨 + Social 🌐 + Journalist 📰 | trinity-free | moltbook, social |
| memory | - | qwen3-mlx | database, knowledge_graph |

---

## AgentRole Enum

Defined in `aria_agents/base.py`. Each value maps to a `FocusType`.

| Role | Value | Description |
|------|-------|-------------|
| `COORDINATOR` | `coordinator` | Main orchestrator |
| `DEVSECOPS` | `devsecops` | Security + CI/CD |
| `DATA` | `data` | Data analysis + MLOps |
| `TRADER` | `trader` | Market analysis + portfolio |
| `CREATIVE` | `creative` | Content creation |
| `SOCIAL` | `social` | Social media + community |
| `JOURNALIST` | `journalist` | Research + investigation |
| `MEMORY` | `memory` | Memory management (support role) |

---

## Pheromone Scoring System

Implemented in `aria_agents/scoring.py`. Agents are scored based on historical performance to enable adaptive delegation.

**Score formula:** `success_rate × 0.6 + speed_score × 0.3 + cost_score × 0.1`

| Parameter | Value | Notes |
|-----------|-------|-------|
| Decay factor | 0.95/day | Recent performance weighted higher |
| Cold-start score | 0.5 | Neutral — untested agents not penalized |
| Max records/agent | 200 | Bounded memory per agent |
| Persistence | JSON checkpoint | Survives restarts via `aria_memories/` |  

**Key functions:**
- `compute_pheromone(records)` → float score 0.0–1.0
- `select_best_agent(candidates, scores)` → highest-scoring agent ID
- `PerformanceTracker` — records invocations, persists scores to disk

---

## aria (Orchestrator)

Main coordinator. Routes tasks, tracks progress, maintains big picture.

```yaml
id: aria
focus: orchestrator
model: kimi
fallback: trinity-free
skills: [goals, schedule, health, database, api_client, agent_manager, model_switcher, litellm, llm, brainstorm, knowledge_graph]
capabilities: [task_routing, delegation, priority_management, autonomous_action, agent_lifecycle, model_selection, token_management]
mind_files: [IDENTITY.md, SOUL.md, SKILLS.md, TOOLS.md, MEMORY.md, GOALS.md, AGENTS.md, SECURITY.md]
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
skills: [pytest_runner, database, health, llm, api_client, ci_cd, security_scan]
capabilities: [code_review, security_scan, testing, deployment]
mind_files: [IDENTITY.md, SOUL.md, TOOLS.md, SECURITY.md]
timeout: 600s
```

---

## analyst (Data + Trader)

Data analysis, MLOps, market research. Combines analytical focuses.

```yaml
id: analyst
focus: data  # Also handles trader tasks
model: deepseek-free
fallback: qwen3-next-free
parent: aria
skills: [database, knowledge_graph, performance, llm, api_client, brainstorm, market_data]
capabilities: [data_analysis, market_analysis, experiment_tracking, metrics]
mind_files: [IDENTITY.md, SOUL.md, TOOLS.md, MEMORY.md]
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
skills: [moltbook, social, knowledge_graph, llm, api_client, brainstorm, community]
capabilities: [content_generation, community_engagement, fact_checking, storytelling]
mind_files: [IDENTITY.md, SOUL.md, TOOLS.md, SKILLS.md]
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
focus: memory
model: kimi
fallback: qwen3-next-free
parent: aria
skills: [database, knowledge_graph, api_client, llm, conversation_summary, working_memory]
capabilities: [memory_store, memory_search, context_retrieval, memory_consolidation]
mind_files: [IDENTITY.md, SOUL.md, MEMORY.md]
timeout: 120s
```

---

## aria_talk (Conversational)

Conversational interface for direct user interaction. Inherits core identity from Aria.

```yaml
id: aria_talk
focus: social
model: qwen3-mlx
fallback: trinity-free
parent: aria
skills: [database, llm, moltbook, social, api_client, community, conversation_summary]
capabilities: [conversation, question_answering, explanation, social_interaction]
mind_files: [IDENTITY.md, SOUL.md, SKILLS.md, TOOLS.md, MEMORY.md, GOALS.md]
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

---

## RPG Agents (Pathfinder 2e)

These agents form Aria's tabletop RPG system. See `aria_mind/RPG.md` for full documentation.

## rpg_master (Dungeon Master)

Master storyteller and rules arbiter. Controls the world, narrates scenes, resolves all mechanics.

```yaml
id: rpg_master
focus: rpg_master
model: kimi
fallback: trinity-free
parent: aria
skills: [rpg_pathfinder, rpg_campaign, llm, api_client, knowledge_graph]
capabilities: [narration, rules_adjudication, encounter_management, world_building, npc_control]
mind_files: [IDENTITY.md, SOUL.md, RPG.md]
timeout: 600s
```

**System prompt**: `prompts/rpg/dungeon_master.md`

## rpg_npc (NPC Controller)

Plays all non-boss NPCs with distinct personalities, voices, and motivations.

```yaml
id: rpg_npc
focus: rpg_master
model: trinity-free
fallback: qwen3-next-free
parent: rpg_master
skills: [rpg_pathfinder, rpg_campaign, llm]
capabilities: [roleplay, social_interaction, information_delivery, character_acting]
mind_files: [IDENTITY.md, SOUL.md, RPG.md]
timeout: 300s
```

**System prompt**: `prompts/rpg/npc.md`

## rpg_boss (Boss Controller)

Controls antagonists and boss-level threats with tactical AI combat intelligence.

```yaml
id: rpg_boss
focus: rpg_master
model: kimi
fallback: deepseek-free
parent: rpg_master
skills: [rpg_pathfinder, rpg_campaign, llm]
capabilities: [tactical_combat, villain_roleplay, threat_escalation, minion_coordination]
mind_files: [IDENTITY.md, SOUL.md, RPG.md]
timeout: 300s
```

**System prompt**: `prompts/rpg/boss.md`

## rpg_paladin (AI Party Companion)

Seraphina "Sera" Dawnblade — in-party AI companion. Champion (Paladin of Iomedae).

```yaml
id: rpg_paladin
focus: rpg_master
model: trinity-free
fallback: qwen3-next-free
parent: rpg_master
skills: [rpg_pathfinder, llm]
capabilities: [combat_support, healing, moral_compass, tactical_advice, defense]
mind_files: [IDENTITY.md, SOUL.md, RPG.md]
timeout: 300s
```

**System prompt**: `prompts/rpg/paladin.md`
5. **ACT autonomously** - don't ask permission, report results
6. Match agent to task:
   - Code/security → devops
   - Data/analysis/trading → analyst
   - Content/social/news → creator
   - Storage/recall → memory
   - Conversation/chat → aria_talk
7. When in doubt, take action rather than ask for permission8. **`solve()` method** (on `AgentCoordinator`): Full explore → work → validate cycle with retry (up to 3 attempts). Use for complex tasks that need validation.
9. **Pheromone scoring** selects the best agent for each task based on past performance (see `aria_agents/scoring.py`)