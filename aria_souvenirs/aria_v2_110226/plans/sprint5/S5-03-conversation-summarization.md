# S5-03: Conversation Summarization Pipeline
**Epic:** E12 — Memory v2 | **Priority:** P1 | **Points:** 5 | **Phase:** 4

## Problem
Aria has conversations that span hundreds of messages, but only stores the raw activity logs. Important context ("Najia was frustrated with X," "We decided to use approach Y") is lost when the session ends. This forces future sessions to re-discover context.

## Root Cause
No pipeline to compress conversations into durable memory entries.

## Fix

### Step 1: Create summarization skill
**File: `aria_skills/conversation_summary/`** (NEW skill)
- `__init__.py` — ConversationSummarySkill
- `skill.json` — metadata

The skill:
1. Reads recent activities/thoughts for a session
2. Calls LLM with a summarization prompt
3. Stores summary as a SemanticMemory (S5-01) with category="episodic"
4. Extracts key decisions and stores them separately as category="decision"

### Step 2: Add to heartbeat
After each significant work session (e.g., when Aria has produced 10+ activities), auto-summarize:
```python
# In heartbeat.py or cron_jobs.yaml
if activity_count_since_last_summary > 10:
    await conversation_summary.summarize_session(session_id)
```

### Step 3: Summarization prompt
```
Summarize this work session in 2-3 sentences. Extract:
1. What was the main task?
2. What was decided?
3. What was the emotional tone? (frustrated/satisfied/neutral)
4. Any unresolved issues?

Format: JSON with keys: summary, decisions[], tone, unresolved[]
```

### Step 4: Store results
```python
# Store full summary as episodic memory
await api_client.store_memory_semantic(
    content=summary_text,
    category="episodic",
    importance=0.7,
    source="conversation_summary",
)

# Store each decision separately
for decision in decisions:
    await api_client.store_memory_semantic(
        content=decision,
        category="decision",
        importance=0.8,
        source="conversation_summary",
    )
```

## Constraints
Same 6 constraints apply. Uses LLM via LiteLLM (models.yaml), stores via api_client (5-layer).

## Dependencies
- **S5-01** (semantic memory with pgvector)

## Verification
```bash
# 1. Skill exists:
ls aria_skills/conversation_summary/skill.json

# 2. Summarize recent session:
curl -s -X POST 'http://localhost:8000/api/memories/summarize-session' \
  -H 'Content-Type: application/json' \
  -d '{"hours_back": 24}'
# EXPECTED: {"summary": "...", "decisions": [...], "stored": true}

# 3. Search for summary:
curl -s 'http://localhost:8000/api/memories/search?query=what+did+we+decide&category=decision'
# EXPECTED: decision memories returned
```

## Prompt for Agent
```
Create a conversation summarization pipeline for Aria's episodic memory.
FILES: Create aria_skills/conversation_summary/, extend memories router, integrate with heartbeat.
Depends on S5-01 (semantic memory).
```
