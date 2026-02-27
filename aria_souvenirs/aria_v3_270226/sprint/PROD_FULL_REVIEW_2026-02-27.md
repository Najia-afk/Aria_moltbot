# Production Full Review — 2026-02-27

## Scope
Server-side full review from this environment (you are outside):
- Last 8h `aria_memories` artifacts
- Current production runtime logs (`aria-api` container)
- Current code state vs ticketed fixes
- Sprint coverage and duplicates

## Evidence Window
- Server clock at audit: `2026-02-27 10:48:58 PST`
- Last-8h files:
  - `aria_memories/logs/work_cycle_2026-02-27_14-01.md`
  - `aria_memories/logs/work_cycle_2026-02-27_1416.json`
  - `aria_memories/logs/work_cycle_2026-02-27_15.json`
  - `aria_memories/memory/logs/work_cycle_2026-02-27_1531.json`
  - `aria_memories/memory/logs/work_cycle_2026-02-27_1616.json`
  - `aria_memories/memory/logs/work_cycle_2026-02-27_1731.json`
  - `aria_memories/logs/cron_work_cycle_2026-02-27-12-46.json`
  - `aria_memories/memory/work_cycle_2026-02-27-12-46.json`
  - `aria_memories/memory/context.json`

## Hard Findings (Confirmed)

### 1) Artifact/session integrity issues are real
- Inconsistent work-cycle/session statistics across adjacent artifacts.
- Mixed payload format quality (including markdown-like content in `.json` context from earlier findings).
- Status: **Not implemented yet** in code.
- Ticket: `S-39`.

### 2) Sub-agent artifact read/list confusion is real
- API route requires nested path in filename for category subfolders:
  - `/artifacts/{category}/{filename:path}` in `src/api/routers/artifacts.py`.
  - For file at `memory/logs/work_cycle_*.json`, caller must use category `memory` + filename `logs/work_cycle_*.json`.
- `api_client.read_artifact()` currently has no helper to read by canonical listed `path`, increasing false-404 risk.
- Status: **Not implemented yet** in code.
- Ticket: `S-40`.

### 3) HEARTBEAT confusion in sub-agent output is explainable
- `aria_mind/HEARTBEAT.md` exists (confirmed).
- Runtime logs show request to `/api/artifacts/memory/HEARTBEAT.md` with 404, which is expected if looking under `aria_memories/memory` category.
- Root issue: conflating code/docs file (`aria_mind/HEARTBEAT.md`) with memory artifact API paths.

### 4) Additional production failures discovered in logs
- Repeated scheduler tool error:
  - `schedule__create_job ... unexpected keyword argument 'type'`
  - Indicates arg compatibility gap in `aria_skills/schedule/__init__.py` `create_job(...)` signature.
  - Ticket: `S-41`.
- Heartbeat API validation noise:
  - `POST /api/heartbeat ... 422 Unprocessable Content`
  - Endpoint uses strict schema (`CreateHeartbeat`), likely rejecting some autonomous payload shapes.
  - Ticket: `S-42`.

## What is actually solved right now?
- ✅ Full production triage/review completed from server side.
- ✅ All identified issue classes are mapped to non-duplicate AA+ tickets.
- ✅ Sprint updated with priorities and execution order.
- ❌ Code fixes are **not yet applied** for S-39/S-40/S-41/S-42.

## Sprint Coverage (Now)
- Updated overview includes E19 integrity track with 4 tickets:
  - `S-39` log/session integrity guardrails
  - `S-40` artifact path resolution for sub-agents
  - `S-41` schedule create_job arg compatibility
  - `S-42` heartbeat payload contract hardening
- No duplicates against visualization/testing tickets.

## Priority Execution Order (Prod-safe)
1. **S-41** — stop scheduler tool failures (`unexpected keyword argument 'type'`)
2. **S-42** — remove heartbeat 422 noise and telemetry gaps
3. **S-39** — enforce work-cycle artifact/session consistency
4. **S-40** — eliminate sub-agent artifact path confusion/false 404 conclusions

## Risks if deferred
- Autonomous scheduler actions continue to fail silently/noisily.
- Heartbeat telemetry remains incomplete due to 422 drops.
- Sub-agent investigations can produce wrong conclusions from path errors.
- Sprint analytics can stay misleading until S-39 is implemented.

## Recommendation
Proceed immediately with implementation of **S-41 + S-42 first**, then **S-39 + S-40**, and run their verification commands in Docker-local context before marking DONE.
