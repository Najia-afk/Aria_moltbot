# Lessons

## General
- Do not use SSH or remote commands unless explicitly requested; prefer local scripts that the user can run on the server.
- Avoid writing secrets or tokens into repo files; prompt for them at runtime or keep them unset by default.
- When refactoring skills, verify file content after edits to avoid duplicated blocks and syntax errors; re-read the file before running tests.

## Sprint Planning (v1.2 — 2026-02-10)
- **Read EVERYTHING before acting.** Full codebase read (200+ files) via parallel subagents is the fastest way. Never plan from summary alone.
- **Parallel subagents work well** for codebase ingestion. 6 subagents reading different directories simultaneously gives full context in minutes.
- **Filename consistency matters.** When a master index references ticket filenames, verify the actual filenames on disk match. Found 5 mismatches in first pass.
- **Dependencies between tickets must be explicit.** If S-17 reads fields that S-16 creates, that's a dependency — write it on the ticket header. Found 8 undocumented dependencies in first cross-review.
- **Watch for ticket overlaps.** S-10/S-11 (both touching DB credentials) and S-13/S-15 (both touching six_hour_review) had overlapping scope. Add cross-reference notes defining ownership boundaries.
- **Epic priority ≠ ticket priority.** An E2 (P0) epic can contain P2 tickets. Note this in sprint overview to avoid confusion during execution.
- **Verification sections are mandatory.** 20/35 tickets were created without explicit verification steps. Every ticket needs testable commands.
- **PO/Scrum prompt lives in prompts/.** Reusable sprint prompt template at `prompts/PO_SCRUM_SPRINT.md` — copy-paste to start any sprint session.

## Architecture
- **5-layer rule:** DB → SQLAlchemy ORM → FastAPI API → api_client (httpx) → Skills → ARIA. No exceptions.
- **9 skills bypass api_client** as of v1.1 — must be migrated (S-08).
- **models.yaml is single source of truth.** Found 3 places with hardcoded model names (S-09).
- **aria_memories/ is the ONLY writable path** for Aria. Code directories are read-only.
- **Container mounts matter.** Verify docker-compose volumes mount aria_memories as rw before assuming file writes work.

## Bugs & Patterns
- **import os missing** in input_guard — always check imports after refactoring.
- **SkillConfig.settings is a dict**, not an object with attributes. Use `config.settings.get()` not `config.settings.attr`.
- **Cron 6-field vs 5-field format** caused massive over-firing. Always validate cron expressions.
- **Empty registries from constructors:** `PipelineExecutor(SkillRegistry())` creates a fresh empty registry instead of using the shared one. Pass the existing registry instance.

## Sprint v1.2 Execution (2025)
- **Swarm execution works.** 44 tickets across 9 epics completed autonomously via parallel subagent dispatch. Tickets grouped into dependency waves avoid blocking.
- **Deprecated code removal (S-18) must happen before init cleanup (S-19).** Removing imports of deleted skills first prevents ImportError cascades.
- **Duplicate index=True + standalone Index() is common.** S-36 found 3 instances. Always check before adding standalone indexes whether inline `index=True` exists.
- **Raw SQL→ORM migration requires reading actual code first.** Ticket diffs may reference stale line numbers. Always read-then-edit.
- **Frontend tickets are independent once routes exist.** S-39/S-40/S-41 ran in parallel with zero conflicts because they touch separate templates and routes.
- **ForeignKey constraints need orphan cleanup first.** S-42 migration DELETEs orphan rows before adding FK to avoid constraint violations on existing data.
- **GIN indexes require pg_trgm extension.** Must `CREATE EXTENSION IF NOT EXISTS pg_trgm` before creating trigram indexes (S-44).
- **Brain→API communication via shared DB table.** SkillStatusRecord pattern (S-40) — brain writes, API reads — is the correct cross-container data sharing approach.
- **AA+ ticket format with Constraints table is essential.** Tickets without explicit constraint evaluation led to architecture violations in v1.1. The full template (Problem, Root Cause, Fix, Constraints, Dependencies, Verification, Prompt) is now the standard.
- **Gateway abstraction (S-31) enables future LLM provider swaps.** GatewayInterface ABC + AriaGateway isolates vendor-specific logic.

## Sprint 1 Execution (2026-02-11)
- **Token counting formula: prefer `total_tokens || (prompt + completion)`.** Never add all three — `total_tokens` already equals `prompt + completion`. Copy-paste bugs made this 3× inflated in two locations.
- **API response shape changes need frontend + backend in same commit.** Changing from bare array to `{logs, total, offset, limit}` broke frontends until both sides deployed together.
- **Shared JS extraction (`aria-common.js`) eliminates template drift.** Balance/spend logic was duplicated across models.html and wallets.html with subtle differences. Centralizing into `fetchBalances()` / `fetchSpendSummary()` ensures consistency.
- **Deduplicate fetch with promise caching pattern.** Store the in-flight promise, return it for concurrent callers, expire after 30s. Reduced 3 `/litellm/spend` calls per page load to 1.
- **Dead code from API migrations lingers.** CNY_TO_USD constant survived months after Kimi switched to USD international API. Always grep for removed-feature references.
- **`tool_calling: false` must be explicit in models.yaml.** Without it, the coordinator assigns tool-needing tasks to models that 404 on tool calls. Chimera-free and trinity-free now marked.
- **DB garbage cleanup via SQL file, not inline shell quotes.** Complex SQL with single quotes inside double-quoted docker exec commands causes shell escaping chaos. Use `docker cp` + `psql -f` instead.
- **`console.log` in production templates leaks internal state.** Gate debug logs behind `window.ARIA_DEBUG` flag so developers can re-enable when needed.

## Sprint 3 Execution (2026-02-11)
- **Direct SQL ALTER TABLE for running containers beats Alembic rebuild.** When containers are up, adding columns via `docker compose exec aria-db psql -c "ALTER TABLE..."` is instant. Save Alembic for cold-start scenarios.
- **Board column mapping must be canonical.** Sprint board uses 5 fixed columns (backlog, todo, doing, on_hold, done). Status-to-column mapping lives in the move endpoint, not the frontend.
- **Token-efficient endpoints save 10x context.** `sprint-summary` returns ~460 bytes vs ~5000 for `get_goals(limit=100)`. Always provide compact alternatives for Aria's cognitive loop.
- **Vanilla drag-and-drop is sufficient for Kanban.** HTML5 `draggable="true"` + `ondragstart/ondrop` events work cleanly without libraries. The `PATCH /goals/{id}/move` endpoint handles column + position + status sync atomically.
- **GraphQL pagination should default to 25, not 100.** Large default limits waste tokens and DB resources. Adding `offset: int = 0` to all resolvers enables cursor-free pagination matching REST endpoints.

## Sprint 5 Execution (2026-02-11)
- **pgvector needs a dedicated Docker image.** `postgres:16-alpine` does not include pgvector. Use `pgvector/pgvector:pg16` instead. Init-scripts only run on first volume creation — use `patch/*.sql` + `docker cp`/`psql -f` for existing databases.
- **FastAPI route order matters for parameterized paths.** `/memories/{key}` intercepted `/memories/search` because it was registered first. Always place specific-path routes BEFORE parameterized `{key}` or `{id}` routes.
- **Integration tests must match actual API response shapes.** Don't guess — read the router to find exact payload format (`{key, value}` not `{content}`), response keys (`{created: true, id}` not the full object), and route prefixes (`/knowledge-graph/` not `/knowledge/`).
- **No `/api` prefix in runtime.** Despite `root_path="/api"`, internal container requests use bare paths (`/goals`, `/memories`). The `/api` prefix is only for reverse-proxy rewriting.
- **Embedding-dependent endpoints should accept 502 in tests.** When the embedding model isn't configured in LiteLLM, semantic endpoints return 502. Tests should `assert status in (200, 502)` rather than hard-failing.
- **DB user comes from `.env`, not convention.** Don't assume `postgres` or `admin` — always check `stacks/brain/.env` for actual credentials (`aria_admin`).

## Sprint Final Review (2026-02-12)
- **Host Python and container Python can diverge hard.** Validate in-container paths (`/app`) before treating host interpreter mismatches as code failures.
- **`configure_python_environment` may return a stale venv path if the venv is missing.** Confirm executable exists before running test commands.
- **Operational scripts need writable artifact targets.** Keep logs, state, backups, and alerts under `aria_memories/` to preserve write-boundary constraints.
- **Deployment verification should include both API and web probes.** Checking container status alone misses route regressions.

## Sprint S-47 — Sentiment Pipeline (2026-02-16)
- **Cognition fire-and-forget pattern is a trap.** Computing analysis in `process()` and injecting into `context` dict without persistence means insights are lost. Any analysis step should persist results via api_client in a non-blocking try/except.
- **Dual storage creates ghost data.** Skill wrote to `semantic_memories` (category=sentiment), dashboard read from `sentiment_events`. Always verify the full read/write path end-to-end before marking a feature done.
- **Hardcoded model names accumulate silently.** Kimi was hardcoded at sentiment skill line 202, burning paid API credits on every call. models.yaml profiles must cover every use case — add profiles proactively.
- **Alembic migrations for every new table.** Relying on `create_all()` is fragile in production with partial schemas. Always create an idempotent migration with `IF NOT EXISTS`.
- **api_client needs methods for every persistence path.** If a table exists in the DB, there must be a corresponding api_client method. The absence of `store_sentiment_event()` was the direct cause of the broken pipeline.
- **Legacy JSONL `content` is a list, not a string.** The legacy gateway stores message content as `[{"type":"text","text":"..."}]`. Any parser that does `isinstance(content, str)` silently drops ALL messages. Always handle both `str` and `list[dict]` formats.
- **Lexicon word lists need common conversational words.** "better", "clean", "easy", "works" were missing — causing 0% confidence on obviously positive messages. Expand lexicon proactively with everyday language, not just strong emotion words.
- **Silent exception swallowing hides critical failures.** `except: pass` in the LLM sentiment fallback meant we had no idea the model calls were failing. Always log at least a warning on fallback paths.
- **Backfill endpoints must write to the correct tables.** `backfill-sessions` wrote to `semantic_memories` only, while the dashboard reads from `sentiment_events`. Both tables need writes for the feature to work end-to-end.

## Sprint S-50→S-57 — Operation Integration (2026-02-19)
- **Routers exist ≠ Routers mounted.** `engine_chat`, `engine_agents`, `engine_agent_metrics` were fully implemented (800+ lines combined) but never added to `main.py`. Always verify new routers appear in the main app's include_router calls.
- **`configure_engine()` must be called in lifespan.** Dependency-injected routers that use module-level globals need explicit initialization during app startup. A mounted but unconfigured router returns 503 on every endpoint.
- **Alembic baseline migration is essential.** 29/36 tables had no migration — `ensure_schema()` at runtime is not enough for fresh installs or CI. Every ORM table needs a corresponding Alembic migration with IF NOT EXISTS for idempotency.
- **Disconnected Alembic heads break `upgrade head`.** s42 had `down_revision = None`, creating two heads. Always run `alembic heads` after adding migrations to verify single-head linear chain.
- **Cron YAML→DB sync must be automatic.** Manual `scripts/migrate_cron_jobs.py` is a deployment trap. Auto-sync on startup with upsert logic (insert new, update changed, preserve runtime state) eliminates deployment drift.
- **Heartbeat tables unused = dashboard shows nothing.** Two heartbeat systems existed but neither wrote to `heartbeat_log`. Always verify the full write→read→display pipeline end-to-end.
- **Swarm execution with dependency waves works.** 8 tickets executed in 4 waves (parallel within wave, sequential between waves). S-52/S-53 combined since both touched main.py. Total: ~10 min wall-clock for 34 points.
- **Subagent also resolved S-51 inside S-50.** When a subagent sees adjacent work (fixing s42 chain while creating baseline), let it do both — saves a round trip.
- **Skills layer was clean — audit confirmed it.** 0 SQLAlchemy violations, 33 skills registered. The architecture boundary between skills and DB held. 4 skills were unregistered due to missing __init__.py imports (not architecture violations, just wiring gaps).
## Epic E10  Prototype Integration Audit (2026-02-19)
- **Subagent file-existence audits can return false negatives.** Subagent reported `aria_skills/sentiment_analysis/` as missing  it existed with 962 lines. Always confirm with `read_file` or `grep_search` before creating a replacement file.
- **Real gaps are often operational, not architectural.** All 6 prototype skills were already implemented in production. The only true gap was that memory compression was never triggered (no cron job). Check the runtime path (cron/event/API call) before auditing the code.
- **"Stopped as over-engineered" in sprint notes does not mean not shipped.** The 2026-02-16 sprint note said `embedding_memory.py` and `pattern_recognition.py` were stopped  both ended up implemented anyway. Sprint decisions evolve; read the code, not only the docs.
- **Import-test pattern for skill verification.** `mcp_pylance_mcp_s_pylanceRunCodeSnippet` with a simple import plus print (no emoji, no unicode) is the fastest way to confirm all exports resolve correctly. Emoji in print strings cause codec errors in some terminals.
- **Compression needs a cron, not just an endpoint.** A skill that is never invoked is the same as a skill that does not exist. For any background-processing skill, creating the cron job is part of the implementation  the endpoint alone is not enough.
- **Self-fetching endpoints simplify cron integration.** `POST /compression/auto-run` fetches its own data from the DB internally. Cron agents need zero payload knowledge  they just call the endpoint. This pattern (self-fetch + skip-if-not-needed guard) is reusable for any scheduled operation.
- **Prototype folder should be archived, not deleted.** `aria_mind/prototypes/` contains design rationale and trade-off notes. Move to `aria_souvenirs/` to preserve the research lineage.
