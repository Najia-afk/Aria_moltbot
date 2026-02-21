# S1-07: Verify Knowledge Graph Auto-Sync on Startup
**Epic:** Sprint 1 — Critical Bugs | **Priority:** P1 | **Points:** 3 | **Phase:** 1

## Problem
Sprint 4 (S4-01, S4-07) implemented knowledge graph auto-generation from `skill.json` files and auto-sync on API startup. We need to verify:
1. The `sync_skill_graph()` function runs on API startup (confirmed in `main.py` lifespan)
2. Knowledge graph entities exist (skills, tools, focus modes)
3. Graph query endpoints work
4. The `scripts/generate_skill_graph.py` script can be run manually
5. The vis.js skill graph page (`/knowledge`) shows nodes

## Root Cause
The knowledge graph is the foundation for Aria's efficient skill discovery (S4-04: 20x token savings). If it's empty or broken, Aria falls back to reading TOOLS.md (~2000 tokens per query) instead of graph traversal (~100 tokens).

## Fix
Verification-only. If graph is empty, trigger manual sync.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | KG access through API endpoints |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml SSOT | ❌ | No model references |
| 4 | Docker-first | ✅ | API runs in container |
| 5 | aria_memories writable | ❌ | DB writes via API |
| 6 | No soul modification | ❌ | Not touching soul |

## Dependencies
None — verification ticket.

## Verification
```bash
# 1. Check knowledge graph has entities:
curl -s "http://localhost:8000/api/knowledge-graph/entities?limit=10" | python3 -c "
import sys, json
d = json.load(sys.stdin)
if isinstance(d, list):
    print(f'Entities: {len(d)}')
    for e in d[:5]:
        print(f'  - {e.get(\"name\", \"?\")} ({e.get(\"entity_type\", \"?\")})')
elif isinstance(d, dict) and 'items' in d:
    print(f'Entities: {len(d[\"items\"])}')
else:
    print(f'Response: {d}')
"
# EXPECTED: Entities: N (with skill names like moltbook, api_client, etc.)

# 2. Check graph relations:
curl -s "http://localhost:8000/api/knowledge-graph/relations?limit=10" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'Relations: {len(d) if isinstance(d, list) else d}')
"
# EXPECTED: Relations: N (edges between skills, focuses, tools)

# 3. Check graph traversal:
curl -s "http://localhost:8000/api/knowledge-graph/traverse?entity=api_client&depth=1" 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(f'Traverse result: {type(d).__name__}, keys: {list(d.keys()) if isinstance(d,dict) else len(d)}')
except: print('Traverse endpoint may not exist or returned non-JSON')
"
# EXPECTED: Dict with traversal results

# 4. Check graph sync runs on startup (look in API logs):
docker compose -f stacks/brain/docker-compose.yml logs aria-api 2>/dev/null | grep -i "graph\|sync\|skill" | tail -5
# EXPECTED: log lines about skill graph sync

# 5. Knowledge page loads:
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/knowledge
# EXPECTED: 200

# 6. Skill graph page loads:
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/skill-graph 2>/dev/null || echo "skill-graph page may not exist"
# EXPECTED: 200 or note if page doesn't exist

# 7. Manual graph generation script exists:
ls -la scripts/generate_skill_graph.py
# EXPECTED: file exists
```

## Prompt for Agent
```
Verify the knowledge graph auto-sync and query system is working.

**Files to read:**
- src/api/main.py (search for sync_skill_graph, lifespan)
- src/api/graph_sync.py (full file — sync logic)
- scripts/generate_skill_graph.py (first 50 lines — manual sync)
- src/api/routers/knowledge.py (first 80 lines — KG endpoints)

**Constraints:** READ-ONLY audit. Docker-first.

**Steps:**
1. Run verification commands above
2. Count entities and relations in the graph
3. If graph is empty, run manual sync: `python3 scripts/generate_skill_graph.py`
4. Verify graph traversal endpoint
5. Check vis.js knowledge page loads with nodes
6. Report pass/fail
```
