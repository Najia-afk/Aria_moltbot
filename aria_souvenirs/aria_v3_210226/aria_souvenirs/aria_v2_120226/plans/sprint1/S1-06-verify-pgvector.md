# S1-06: Verify pgvector & Semantic Memory Endpoints
**Epic:** Sprint 1 — Critical Bugs | **Priority:** P0 | **Points:** 3 | **Phase:** 1

## Problem
Sprint 5 (S5-01) and Sprint 6 (S6-01) from yesterday installed pgvector and implemented semantic memory endpoints. These are critical infrastructure — if they're not working, Aria's memory system is degraded.

**Endpoints to verify:**
- `POST /api/memories` with semantic content
- `GET /api/memories/search?query=...` (semantic search)
- `GET /api/memories` (standard list with JSONB)

**Tables to verify exist:**
- `semantic_memories` (Vector(768) column, IVFFlat index)
- All 36+ tables created by `ensure_schema()` without cascade failure

## Root Cause
pgvector requires the `pgvector/pgvector:pg16` Docker image (confirmed in docker-compose.yml). The `ensure_schema()` function must handle per-table errors gracefully — a failure in one table (e.g., pgvector extension not loaded) should not prevent other tables from being created.

## Fix
Verification-only. If issues found, document and fix.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Memory access through API → ORM → DB |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml SSOT | ✅ | Embedding model (nomic-embed-text) must be in models.yaml |
| 4 | Docker-first | ✅ | pgvector runs inside aria-db container |
| 5 | aria_memories writable | ❌ | DB access only |
| 6 | No soul modification | ❌ | Not touching soul |

## Dependencies
None — verification ticket.

## Verification
```bash
# 1. Check pgvector extension is installed:
docker compose -f stacks/brain/docker-compose.yml exec aria-db psql -U aria_admin -d aria -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
# EXPECTED: vector | 0.x.x (extension present)

# 2. Check semantic_memories table exists:
docker compose -f stacks/brain/docker-compose.yml exec aria-db psql -U aria_admin -d aria -c "\dt semantic_memories"
# EXPECTED: table listed (or "Did not find" if not created yet)

# 3. Check all expected tables exist:
docker compose -f stacks/brain/docker-compose.yml exec aria-db psql -U aria_admin -d aria -c "\dt" | wc -l
# EXPECTED: 36+ tables

# 4. Test health/db endpoint for table audit:
curl -s http://localhost:8000/api/health/db | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2))"
# EXPECTED: JSON with database status and table info

# 5. Test semantic memory store:
curl -s -X POST http://localhost:8000/api/memories -H "Content-Type: application/json" -d '{"key":"test_semantic_check","value":"Testing semantic memory functionality","category":"system"}' | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2))"
# EXPECTED: 200 with created memory

# 6. Test memory retrieval:
curl -s "http://localhost:8000/api/memories?limit=5" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Count: {len(d) if isinstance(d,list) else d}')"
# EXPECTED: Count: N (list of memories)

# 7. Check embedding model available:
curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; models=json.load(sys.stdin).get('models',[]); names=[m['name'] for m in models]; print('nomic-embed-text' in [n.split(':')[0] for n in names])"
# EXPECTED: True (nomic-embed-text available via Ollama)
```

## Prompt for Agent
```
Verify pgvector and semantic memory are working in production.

**Files to read:**
- src/api/db/models.py (search for SemanticMemory, Vector, pgvector)
- src/api/routers/memories.py (search for semantic, search, embed)
- src/api/main.py (search for ensure_schema)
- stacks/brain/docker-compose.yml (search for pgvector)

**Constraints:** READ-ONLY audit. Docker-first.

**Steps:**
1. Run all verification commands above
2. Document pgvector extension status
3. Document table count and list any missing tables
4. Test semantic store and retrieval
5. Report pass/fail for each check
6. If embedding fails, check if nomic-embed-text is available via Ollama
```
