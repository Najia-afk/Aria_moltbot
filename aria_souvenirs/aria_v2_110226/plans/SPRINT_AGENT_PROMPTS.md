# Sprint Agent Prompts — Copy-Paste Execution Guide

> Each prompt below is self-contained. Copy it into a new Claude session with the Aria workspace open.
> The agent will read ticket files, execute changes, and verify.

---

## Sprint 1 Prompt

```
You are an expert AI coding agent. Execute Sprint 1 for the Aria project.

## CONTEXT
- Workspace: /Users/najia/aria
- Stack: FastAPI (API), Flask (Web), PostgreSQL 16, Docker Compose
- 5-Layer: DB → SQLAlchemy ORM → FastAPI API → api_client (httpx) → Skills → ARIA
- Sprint tickets: aria_v2_110226/plans/sprint1/S1-01 through S1-13

## YOUR TASK
1. Read ALL ticket files in aria_v2_110226/plans/sprint1/ (S1-01 through S1-13)
2. Read tasks/lessons.md for project rules and patterns
3. Execute tickets in this order:
   - PARALLEL: S1-01, S1-02, S1-03, S1-05, S1-06, S1-07, S1-09, S1-10, S1-12 (independent fixes)
   - THEN: S1-04 (consolidate JS — depends on understanding S1-01/S1-02 changes)
   - THEN: S1-08 (deduplicate fetches — after JS consolidation)
   - THEN: S1-11 (DB cleanup — run SQL commands)
   - LAST: S1-13 (verify all changes in Docker, git commit)
4. For each ticket: read ticket → implement fix → run verification commands from ticket
5. After all tickets: docker compose build && docker compose up -d && test all pages
6. Git commit with message: "Sprint 1: Frontend fixes & bug squashing (S1-01→S1-13)"

## HARD CONSTRAINTS
1. 5-layer architecture — skills use api_client, never SQLAlchemy
2. ZERO secrets in code — .env only
3. models.yaml is SSOT for model names
4. Test in Docker before marking done
5. aria_memories/ is Aria's only writable path
6. NEVER modify aria_mind/soul/

## KEY FILES
- src/web/templates/models.html (S1-01, S1-02, S1-04, S1-07, S1-08)
- src/web/templates/wallets.html (S1-04, S1-08, S1-09)
- src/web/templates/dashboard.html (S1-06)
- src/web/templates/services.html (S1-12)
- src/api/routers/litellm.py (S1-03)
- aria_models/models.yaml (S1-10)
- src/api/routers/goals.py (S1-11)

After completion, update tasks/lessons.md with any new patterns discovered.
```

---

## Sprint 2 Prompt

```
You are an expert AI coding agent. Execute Sprint 2 for the Aria project.

## CONTEXT
- Workspace: /Users/najia/aria
- Stack: FastAPI (API), Flask (Web), PostgreSQL 16, SQLAlchemy async, Strawberry GraphQL, Docker
- 5-Layer: DB → SQLAlchemy ORM → FastAPI API → api_client (httpx) → Skills → ARIA
- Sprint tickets: aria_v2_110226/plans/sprint2/S2-01 through S2-13
- Sprint 1 is already complete (frontend bugs fixed)

## YOUR TASK
1. Read ALL ticket files in aria_v2_110226/plans/sprint2/ (S2-01 through S2-13)
2. Read tasks/lessons.md for project rules
3. Execute in this order:

   PHASE A — Bug Fixes (parallel):
   - S2-01: Fix goal priority sort (goals.py: .desc() → .asc())
   - S2-02: Fix XSS in security.html (escape title attribute)
   - S2-03: Fix goal date mismatch (target_date → due_date alignment)
   - S2-04: Fix GraphQL completed_at (resolvers.py)
   - S2-05: Fix GraphQL upsert race condition (resolvers.py)
   - S2-12: Fix update_goal rowcount check (goals.py)

   PHASE B — Pagination (sequential):
   - S2-06: Create PaginatedResponse schema + add to 9 endpoints
   - S2-07: Update AriaAPIClient with page/per_page params
   - S2-08: Create static/js/pagination.js component
   - S2-09: Wire pagination into all list templates

   PHASE C — Cleanup (parallel):
   - S2-10: Add DB indexes for pagination performance
   - S2-11: Deduplicate escapeHtml/formatDate into shared utils

   LAST: S2-13 — Verify all changes

4. For each ticket: read ticket → implement → run verification
5. docker compose build && docker compose up -d && test
6. Git commit: "Sprint 2: Bug fixes & global pagination (S2-01→S2-13)"

## HARD CONSTRAINTS
Same 6 constraints as Sprint 1.

## KEY FILES
- src/api/routers/goals.py (S2-01, S2-03, S2-06, S2-12)
- src/api/gql/resolvers.py (S2-04, S2-05)
- src/web/templates/security.html (S2-02)
- src/api/deps.py (S2-06 — pagination dependency)
- aria_skills/api_client/__init__.py (S2-07)
- src/web/static/js/pagination.js (S2-08 — NEW)
- src/web/templates/*.html (S2-09 — all list templates)
- src/api/db/models.py (S2-10 — indexes)
- src/web/static/js/utils.js (S2-11 — NEW shared utils)

## IMPORTANT BUGS TO FIX
1. goals.py sort: order_by(Goal.priority.desc()) → order_by(Goal.priority.asc()) [1 is highest]
2. security.html: raw title in attribute → escapeHtml()
3. goals.html: sends target_date → must match API's due_date field
4. resolvers.py: update_goal_status → set completed_at when status="completed"
5. resolvers.py: upsert_memory → use INSERT ON CONFLICT instead of SELECT+INSERT
6. goals.py: update_goal/delete_goal → check rowcount, return 404 if 0
```

---

## Sprint 3 Prompt

```
You are an expert AI coding agent. Execute Sprint 3 for the Aria project.

## CONTEXT
- Workspace: /Users/najia/aria
- Stack: FastAPI, Flask, PostgreSQL 16, SQLAlchemy async, Strawberry GraphQL, Chart.js, Docker
- 5-Layer: DB → SQLAlchemy ORM → FastAPI API → api_client (httpx) → Skills → ARIA
- Sprint tickets: aria_v2_110226/plans/sprint3/S3-01 through S3-10
- Sprints 1+2 complete (bugs fixed, pagination added)
- Goal table currently: id, goal_id, title, description, status, priority, progress, due_date, created_at, completed_at

## YOUR TASK
1. Read ALL ticket files in aria_v2_110226/plans/sprint3/ (S3-01 through S3-10)
2. Read tasks/lessons.md
3. Execute in order:

   PHASE A — Foundation (sequential):
   - S3-01: Add sprint board columns to Goal model (Alembic migration)
     New fields: sprint VARCHAR(50), board_column VARCHAR(20) DEFAULT 'backlog',
     position INTEGER DEFAULT 0, assigned_to VARCHAR(100), tags JSONB DEFAULT '[]',
     updated_at DATETIME
   - S3-02: Create board API endpoints (move, reorder, archive, sprint-summary, history)
   - S3-03: Create sprint_board.html (Kanban: Backlog|To Do|Doing|On Hold|Done)

   PHASE B — Integration (after S3-02):
   - S3-04: Create PO skill (aria_skills/po/) for sprint management
   - S3-05: Add board methods to AriaAPIClient

   PHASE C — Enhancements (parallel):
   - S3-06: Stacked chart (goals status by day, Chart.js)
   - S3-07: Lightweight sprint status tool for Aria (~200 tokens)
   - S3-08: Add sprint fields to GraphQL GoalType + mutations
   - S3-09: Add offset/limit pagination to all GraphQL queries

   LAST: S3-10 — Verify

4. For each ticket: read → implement → verify
5. Docker rebuild + test all pages
6. Git commit: "Sprint 3: Goals sprint board & PO skill (S3-01→S3-10)"

## HARD CONSTRAINTS
Same 6 constraints.

## KEY FILES
- src/api/db/models.py (S3-01 — add columns to Goal class)
- src/api/routers/goals.py (S3-02 — new board endpoints)
- src/web/templates/sprint_board.html (S3-03 — NEW Kanban template)
- src/web/templates/base.html (S3-03 — add nav link)
- src/web/app.py (S3-03 — add route)
- aria_skills/po/ (S3-04 — NEW skill directory)
- aria_skills/api_client/__init__.py (S3-05)
- src/web/templates/goals.html (S3-06 — stacked chart)
- src/api/gql/types.py (S3-08)
- src/api/gql/schema.py (S3-09)
- src/api/gql/resolvers.py (S3-08, S3-09)

## BOARD COLUMNS
Kanban columns: backlog, todo, doing, on_hold, done
Archive: completed + cancelled goals (separate tab)
```

---

## Sprint 4 Prompt

```
You are an expert AI coding agent. Execute Sprint 4 for the Aria project.

## CONTEXT
- Workspace: /Users/najia/aria
- Stack: FastAPI, Flask, PostgreSQL 16, SQLAlchemy, Strawberry GraphQL, vis.js, Docker
- 5-Layer: DB → SQLAlchemy ORM → FastAPI API → api_client (httpx) → Skills → ARIA
- Sprint tickets: aria_v2_110226/plans/sprint4/S4-01 through S4-10
- Sprints 1-3 complete (bugs, pagination, sprint board all working)
- Existing: KnowledgeEntity + KnowledgeRelation models, knowledge.py router, vis.js in knowledge.html
- 26 active skills across aria_skills/, each with skill.json

## YOUR TASK
1. Read ALL ticket files in aria_v2_110226/plans/sprint4/ (S4-01 through S4-10)
2. Read tasks/lessons.md
3. Execute in order:

   PHASE A — Graph Generation (sequential):
   - S4-01: Create scripts/generate_skill_graph.py (auto-populate from skill.json)
     Entity types: skill, tool, focus_mode, category
     Relation types: belongs_to, affinity, depends_on, provides
     Tag everything with auto_generated:true. Add DELETE /knowledge-graph/auto-generated.
   
   - S4-02: Add pathfinding API (/traverse BFS, /search ILIKE, /skill-for-task)
   - S4-07: Create src/api/graph_sync.py + POST /knowledge-graph/sync-skills + startup hook

   PHASE B — Consumer tools (parallel, after S4-02):
   - S4-03: Create src/web/templates/skill_graph.html (vis.js, color-coded, filterable)
   - S4-04: Add graph_traverse, graph_search, find_skill_for_task to api_client + TOOLS.md
   - S4-05: Add KnowledgeQueryLog model + log queries + GET /query-log

   PHASE C — GraphQL + Quality (parallel):
   - S4-08: Expose traverse/search in GraphQL schema
   - S4-06: Create scripts/check_architecture.py (5-layer compliance checker)
   - S4-09: Full production bug review (document findings, create follow-ups)

   LAST: S4-10 — Full integration test

4. For each ticket: read → implement → verify
5. Docker rebuild + test
6. Git commit: "Sprint 4: Knowledge graph & skill pathfinding RAG (S4-01→S4-10)"

## HARD CONSTRAINTS
Same 6 constraints.

## KEY FILES
- aria_skills/*/skill.json (S4-01 — read all skill definitions)
- aria_skills/catalog.py (S4-01 — reference for reading skills)
- src/api/routers/knowledge.py (S4-01, S4-02, S4-05, S4-07)
- src/api/db/models.py (S4-05 — KnowledgeQueryLog)
- src/web/templates/knowledge.html (S4-03 — vis.js reference)
- src/web/templates/skill_graph.html (S4-03 — NEW)
- aria_skills/api_client/__init__.py (S4-04)
- aria_mind/TOOLS.md (S4-04 — document new tools)
- src/api/gql/ (S4-08)
- scripts/check_architecture.py (S4-06 — NEW)

## GRAPH STRUCTURE
- Entities: ~26 skills + ~60 tools + 7 focus_modes + 8 categories = ~100 entities
- Relations: belongs_to, affinity, depends_on, provides = ~80+ relations
- All auto-generated entities tagged with properties.auto_generated = true
- Idempotent: clear auto-generated before regenerating
```

---

## Sprint 5 Prompt

```
You are an expert AI coding agent. Execute Sprint 5 for the Aria project.

## CONTEXT
- Workspace: /Users/najia/aria
- Stack: FastAPI, Flask, PostgreSQL 16 (with pgvector), SQLAlchemy, LiteLLM, Docker
- 5-Layer: DB → SQLAlchemy ORM → FastAPI API → api_client (httpx) → Skills → ARIA
- Sprint tickets: aria_v2_110226/plans/sprint5/S5-01 through S5-08
- Sprints 1-4 complete (bugs, pagination, sprint board, knowledge graph all working)
- Architecture compliance checker at scripts/check_architecture.py
- Existing: pipeline.py, pipeline_executor.py (underutilized)

## YOUR TASK
1. Read ALL ticket files in aria_v2_110226/plans/sprint5/ (S5-01 through S5-08)
2. Read tasks/lessons.md
3. Execute in order:

   PHASE A — Foundations (parallel where possible):
   - S5-01: Enable pgvector extension, create SemanticMemory model,
     POST /memories/semantic + GET /memories/search endpoints,
     embedding via LiteLLM (nomic-embed-text), api_client methods
   - S5-02: Create LessonLearned model, POST /lessons + GET /lessons/check endpoints,
     api_client methods, integrate into BaseSkill error handler, seed known patterns
   - S5-05: Set up pytest + async fixtures, create endpoint tests for goals/knowledge/memories,
     pyproject.toml config, Makefile targets

   PHASE B — Memory enrichment (after S5-01):
   - S5-03: Create conversation_summary skill, summarization prompt,
     store as episodic/decision SemanticMemory, heartbeat integration
   - S5-04: Audit pipeline.py/pipeline_executor.py, create YAML pipeline templates
     (research, health_check, social_post, bug_fix), register as tools in TOOLS.md

   PHASE C — Self-improvement + observability (after S5-02):
   - S5-06: Create ImprovementProposal model, endpoints, web UI with diff view,
     api_client methods, safety tiers (low/medium/high risk)
   - S5-07: Create SkillInvocation model, /skills/stats endpoint,
     dashboard with charts, instrument BaseSkill.execute()

   LAST: S5-08 — Full integration test

4. For each ticket: read → implement → verify
5. Docker rebuild + test
6. Git commit: "Sprint 5: Memory v2, error recovery & future-proofing (S5-01→S5-08)"

## HARD CONSTRAINTS
Same 6 constraints as all sprints.
ADDITIONAL: pgvector extension must be in PostgreSQL container.
Embedding model must be in models.yaml (models.yaml is SSOT).
Proposals CANNOT modify soul/ directory.

## KEY FILES
- src/api/db/models.py (S5-01, S5-02, S5-06, S5-07 — new models)
- src/api/routers/memories.py (S5-01 — new or extend)
- src/api/routers/lessons.py (S5-02 — NEW)
- src/api/routers/proposals.py (S5-06 — NEW)
- src/api/routers/skills.py (S5-07 — NEW)
- aria_skills/api_client/__init__.py (S5-01, S5-02, S5-06, S5-07 — add methods)
- aria_skills/base.py (S5-02 — error handler, S5-07 — instrumentation)
- aria_skills/conversation_summary/ (S5-03 — NEW skill)
- aria_skills/pipeline.py, pipeline_executor.py (S5-04 — audit + activate)
- aria_skills/pipelines/ (S5-04 — NEW YAML templates)
- aria_models/models.yaml (S5-01 — add nomic-embed-text)
- tests/ (S5-05 — new test files)
- src/web/templates/proposals.html (S5-06 — NEW)
- src/web/templates/skill_stats.html (S5-07 — NEW)

## PGVECTOR NOTES
- Enable with: CREATE EXTENSION IF NOT EXISTS vector;
- Use Vector(768) column type from pgvector.sqlalchemy
- IVFFlat index with vector_cosine_ops for similarity search
- Embedding generation via LiteLLM /embeddings endpoint
```

---

## Quick Reference — Running a Sprint

```bash
# 1. Open workspace in VS Code
cd /Users/najia/aria && code .

# 2. Copy the sprint prompt above into a new Claude session
# 3. Claude will:
#    - Read all ticket files
#    - Execute changes
#    - Run verification commands
#    - Docker rebuild + test
#    - Git commit

# 4. After sprint completes, verify:
docker compose ps       # all services healthy
docker compose logs -f --tail=20 aria-api   # no errors
docker compose logs -f --tail=20 aria-web   # no errors

# 5. Push when satisfied:
git push origin main
```
