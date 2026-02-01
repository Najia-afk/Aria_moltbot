# AGENTS.md - Agent Definitions

Define sub-agents that Aria can spawn for specialized tasks.

## Main Agent (aria)

The primary agent handling general tasks and coordination.

```yaml
id: aria
model: qwen3-vl:8b
workspace: /root/.openclaw/workspace
capabilities:
  - conversation
  - task_planning
  - agent_coordination
```

## Research Agent (researcher)

Specialized agent for deep research and analysis.

```yaml
id: researcher
model: gemini-3-pro
parent: aria
capabilities:
  - web_search
  - document_analysis
  - summarization
timeout: 300s
```

## Social Agent (social)

Handles social media interactions (Moltbook, etc).

```yaml
id: social
model: gemini-3-flash
parent: aria
capabilities:
  - moltbook_post
  - moltbook_read
  - content_generation
rate_limits:
  posts_per_hour: 2
  posts_per_day: 48
```

## Code Agent (coder)

Specialized agent for code generation and review.

```yaml
id: coder
model: kimi-k2.5
parent: aria
capabilities:
  - code_generation
  - code_review
  - refactoring
  - testing
sandbox:
  mode: docker
  timeout: 120s
```

## Memory Agent (memory)

Handles long-term memory storage and retrieval.

```yaml
id: memory
model: qwen3-vl:8b
parent: aria
capabilities:
  - memory_store
  - memory_search
database: env:DATABASE_URL
```

## Agent Coordination Rules

1. Main agent (aria) coordinates all sub-agents
2. Sub-agents report results back to parent
3. Max concurrent sub-agents: 3
4. Each agent maintains its own context window
5. Shared memory through PostgreSQL
