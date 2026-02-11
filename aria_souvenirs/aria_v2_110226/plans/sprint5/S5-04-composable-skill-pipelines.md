# S5-04: Activate Composable Skill Pipelines
**Epic:** E14 — Skill Orchestration | **Priority:** P1 | **Points:** 5 | **Phase:** 4

## Problem
Aria's skills are atomic — she calls one at a time, waits for result, decides next step. Complex tasks like "research a topic" require 5-6 sequential skill calls, each consuming LLM tokens to decide the next step.

The pipeline infrastructure exists (`aria_skills/pipeline.py`, `aria_skills/pipeline_executor.py`) but is underutilized.

## Root Cause  
No pre-built pipeline templates. The pipeline executor exists but no pipelines are defined.

## Fix

### Step 1: Audit existing pipeline code
Read `aria_skills/pipeline.py` and `pipeline_executor.py` — understand the existing API.

### Step 2: Create pipeline templates
**File: `aria_skills/pipelines/research.yaml`** (NEW)
```yaml
name: deep_research
description: "Full research pipeline: search → browse → extract → summarize → store"
steps:
  - skill: api_client
    tool: search_knowledge
    input: {query: "{{topic}}"}
    output: existing_knowledge
    
  - skill: browser
    tool: web_search
    input: {query: "{{topic}} latest 2026"}
    output: search_results
    condition: "existing_knowledge.count < 3"
    
  - skill: browser
    tool: extract_content
    input: {urls: "{{search_results.top_3_urls}}"}
    output: raw_content
    
  - skill: llm
    tool: summarize
    input: {content: "{{raw_content}}", max_tokens: 500}
    output: summary
    
  - skill: api_client
    tool: store_memory_semantic
    input: {content: "{{summary}}", category: "research", importance: 0.7}
    output: stored
```

### Step 3: Create more pipeline templates
- `pipelines/health_check.yaml` — check all services → log issues → create goals for failures
- `pipelines/social_post.yaml` — research topic → draft post → fact check → post
- `pipelines/bug_fix.yaml` — reproduce → analyze → fix → test → commit

### Step 4: Register pipelines as tools
Add pipeline invocation to TOOLS.md so Aria can trigger pipelines:
```yaml
aria-pipeline.run({"pipeline": "deep_research", "params": {"topic": "AI safety"}})
```

### Step 5: Add error handling per step
Each pipeline step should have:
- `on_error: skip | retry | abort`
- `timeout: 30s`
- `retry_count: 2`

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Pipelines orchestrate via api_client |
| 2 | .env | ❌ | No secrets |
| 3 | models.yaml | ✅ | LLM calls use models.yaml |
| 4 | Docker-first | ✅ | Test in Docker |
| 5 | aria_memories | ❌ | Stores via API |
| 6 | No soul mod | ❌ | No soul changes |

## Dependencies
- S5-01 (semantic memory for storing pipeline outputs)
- Existing pipeline.py and pipeline_executor.py

## Verification
```bash
# 1. Pipeline templates exist:
ls aria_skills/pipelines/*.yaml

# 2. Run a pipeline:
curl -s -X POST http://localhost:8000/api/pipelines/run \
  -H 'Content-Type: application/json' \
  -d '{"pipeline": "deep_research", "params": {"topic": "AI safety"}}'
# EXPECTED: pipeline execution result

# 3. TOOLS.md documents pipelines:
grep 'aria-pipeline' aria_mind/TOOLS.md
```

## Prompt for Agent
```
Activate Aria's composable skill pipelines.
FILES: aria_skills/pipeline.py, pipeline_executor.py, create pipelines/ dir with YAML templates.
STEPS: 1. Audit existing code 2. Create 4 pipeline templates 3. Register as tools 4. Add error handling
```
