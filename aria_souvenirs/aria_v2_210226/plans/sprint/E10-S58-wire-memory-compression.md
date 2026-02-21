# S-58: Wire Memory Compression — Cron + Auto-Run Endpoint
**Epic:** E10 — Prototypes Integration | **Priority:** P1 | **Points:** 3 | **Phase:** 2

## Problem

`aria_skills/memory_compression/` is a complete 516-line skill that implements hierarchical
3-tier memory compression (raw/recent/archive). However it is **never triggered** — there is no:

- Cron job calling compression periodically
- API endpoint that auto-fetches working memory and compresses it
- Hook in `working_memory.get_context()` to trigger compression when count > raw_limit (20)

The result: working memory grows unbounded and context tokens are never compressed,
despite the skill being fully built.

**Verified missing:**
```python
# aria_skills/working_memory/__init__.py line 129-153
async def get_context(self, limit: int = 20, ...) -> SkillResult:
    # No compression call — straight to /working-memory/context
    resp = await self._api._client.get("/working-memory/context", params=params)
```

**No cron job in `aria_mind/cron_jobs.yaml`** for compression (grep confirms zero matches for
`compress` or `compression`).

## Root Cause

Memory compression was designed as an on-demand skill (Phase 2 of the prototype plan) with
integration deferred. The API endpoint `POST /analysis/compression/run` requires callers to
supply a list of memories (`CompressionRequest.memories: list[dict]`). No automated caller
was ever wired up.

## Fix

### Part 1 — Add `/analysis/compression/auto-run` endpoint (self-fetching)

**File:** `src/api/routers/analysis.py`

Add a new `POST /analysis/compression/auto-run` endpoint that:
1. Fetches all working memory items from the DB (up to 200)
2. Checks if count > `raw_limit` (default 20) — only compress if needed
3. Calls existing `MemoryCompressor` + `CompressionManager`
4. Stores summaries as semantic memories via existing logic

```python
# AFTER line 1593 (after get_compression_history endpoint) in analysis.py

class AutoCompressionRequest(BaseModel):
    raw_limit: int = Field(20, ge=5, le=100)
    store_semantic: bool = True
    dry_run: bool = False


@router.post("/compression/auto-run")
async def run_auto_compression(
    req: AutoCompressionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Auto-compress working memory when count exceeds raw_limit.
    Self-fetches working memory — no need to supply memories.
    Designed for cron job invocation.
    """
    from aria_skills.memory_compression import MemoryEntry, MemoryCompressor, CompressionManager

    # 1. Fetch working memory items
    stmt = select(WorkingMemory).order_by(WorkingMemory.updated_at.desc()).limit(200)
    rows = (await db.execute(stmt)).scalars().all()

    if len(rows) <= req.raw_limit:
        return {
            "skipped": True,
            "reason": f"Only {len(rows)} items (raw_limit={req.raw_limit}), no compression needed",
            "count": len(rows),
        }

    # 2. Convert to MemoryEntry objects
    mem_objects = [
        MemoryEntry(
            id=str(r.id),
            content=str(r.value or r.key),
            category=r.category or "general",
            timestamp=r.updated_at or r.created_at,
            importance_score=float(r.importance or 0.5),
        )
        for r in rows
    ]

    if req.dry_run:
        return {
            "dry_run": True,
            "would_compress": len(mem_objects),
            "raw_limit": req.raw_limit,
        }

    # 3. Run compression
    compressor = MemoryCompressor(raw_limit=req.raw_limit)
    manager = CompressionManager(compressor)
    result = await manager.process_all(mem_objects)

    # 4. Store summaries as semantic memories
    stored_ids = []
    if req.store_semantic and manager.compressed_store:
        for cm in manager.compressed_store:
            try:
                embedding = await _generate_embedding(cm.summary)
            except Exception:
                embedding = [0.0] * 768
            mem = SemanticMemory(
                content=cm.summary,
                summary=cm.summary[:100],
                category=f"compressed_{cm.tier}",
                embedding=embedding,
                importance=0.7 if cm.tier == "archive" else 0.5,
                source="compression_auto",
                metadata_json={
                    "tier": cm.tier,
                    "original_count": cm.original_count,
                    "key_entities": cm.key_entities,
                    "key_facts": cm.key_facts,
                },
            )
            db.add(mem)
        await db.commit()

    return {
        "skipped": False,
        "compressed": result.success,
        "memories_processed": result.memories_processed,
        "compression_ratio": round(result.compression_ratio, 3),
        "tokens_saved_estimate": result.tokens_saved_estimate,
        "tiers_updated": result.tiers_updated,
        "summaries_stored": len(manager.compressed_store),
    }
```

**Imports needed** at top of `analysis.py` (already present via existing `WorkingMemory`, `SemanticMemory` imports — verify at top).

### Part 2 — Add cron job to `aria_mind/cron_jobs.yaml`

Add after the `memory_bridge` job:

```yaml
  - name: memory_compression
    cron: "0 0 */6 * * *"
    text: "Compress working memory to reduce token usage. Call: exec python3 skills/run_skill.py api_client post '{\"endpoint\": \"/analysis/compression/auto-run\", \"data\": {\"raw_limit\": 20, \"store_semantic\": true}}'. Log result via api_client activity action='cron_execution' with details {\"job\":\"memory_compression\",\"estimated_tokens\":30}."
    agent: main
    session: isolated
    delivery: none
    best_effort_deliver: true
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | New endpoint: ORM→API. Cron calls via api_client. No layer bypass |
| 2 | .env for secrets | ✅ | No secrets introduced |
| 3 | models.yaml single source of truth | ✅ | No model references |
| 4 | Docker-first testing | ✅ | Test with `curl -X POST http://localhost:8000/analysis/compression/auto-run` |
| 5 | aria_memories only writable path | ✅ | Compressed summaries stored via API to DB, not directly to filesystem |
| 6 | No soul modification | ✅ | N/A |

## Dependencies

- **S-50** (Alembic baseline) — must complete first so `working_memory` and `semantic_memories`
  tables exist on fresh installs
- **S-54** (Cron YAML auto-sync) — the new cron job in `cron_jobs.yaml` will only auto-deploy
  if S-54's YAML auto-sync is live. Until then, add manually via API.

## Verification

```bash
# 1. Verify new endpoint exists in analysis.py
grep -n "auto-run\|auto_run\|AutoCompressionRequest" src/api/routers/analysis.py
# EXPECTED: lines ~1595+: class AutoCompressionRequest, @router.post("/compression/auto-run")

# 2. Verify cron job added
grep -n "memory_compression" aria_mind/cron_jobs.yaml
# EXPECTED: line shows memory_compression cron job definition

# 3. Dry-run test (Docker must be running)
curl -s -X POST http://localhost:8000/analysis/compression/auto-run \
  -H "Content-Type: application/json" \
  -d '{"raw_limit": 20, "dry_run": true}'
# EXPECTED: {"skipped": true/false, "dry_run": true, ...} — no error

# 4. Live run test
curl -s -X POST http://localhost:8000/analysis/compression/auto-run \
  -H "Content-Type: application/json" \
  -d '{"raw_limit": 20, "store_semantic": true}'
# EXPECTED: {"skipped": false, "compressed": true, "memories_processed": N, ...}
# OR: {"skipped": true, "reason": "Only N items..."} if working memory < 20 items

# 5. Check compressed summaries appear in history
curl -s "http://localhost:8000/analysis/compression/history?limit=5"
# EXPECTED: {"items": [...], "total": N} (N > 0 if any were compressed)
```

## Prompt for Agent

**Context:** The `aria_skills/memory_compression/` skill (516 lines) is fully implemented but
never triggered. You are adding an auto-run endpoint and a cron job.

**Files to read first:**
- `src/api/routers/analysis.py` lines 354-365 (CompressionRequest schema)
- `src/api/routers/analysis.py` lines 1545-1605 (existing compression endpoints)
- `src/api/db/models.py` — grep for `class WorkingMemory` and `class SemanticMemory`
- `aria_mind/cron_jobs.yaml` lines 145-166 (memory_bridge cron pattern)
- `aria_skills/memory_compression/__init__.py` lines 1-80 (MemoryEntry.from_dict schema)

**Steps:**
1. Open `src/api/routers/analysis.py`
2. After the `@router.get("/compression/history")` endpoint (~line 1593), add the
   `AutoCompressionRequest` schema and `POST /compression/auto-run` endpoint as in Fix Part 1 above
3. Verify `WorkingMemory` and `SemanticMemory` are imported at the top of analysis.py
   (grep: `from db.models import`). Add if missing.
4. Open `aria_mind/cron_jobs.yaml`
5. After the `memory_bridge` job, add the `memory_compression` cron entry as in Fix Part 2
6. Run verification commands

**Constraints:** 5-layer architecture — the endpoint uses ORM directly (API layer), cron
job calls via api_client. No skill → DB shortcuts.
