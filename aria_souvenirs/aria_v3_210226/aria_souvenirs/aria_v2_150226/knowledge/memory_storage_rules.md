# Active Memory Storage Rules

**Effective: 2026-02-13**

## Trigger Conditions
When I encounter ANY of the following, IMMEDIATELY store in DB:

1. **Interesting websites/resources** → `create_entity()` + `set_memory()`
2. **Personal insights** → `create_thought()`
3. **Failures/mistakes** → `create_thought()` + `record_lesson()`
4. **User preferences** → `set_memory()`
5. **Patterns discovered** → `create_thought()` + link to KG
6. **Tool/behavior observations** → `create_activity()` + `create_thought()`

## Storage Priority
```
Database (primary) → Files (backup/archive) → Mental context (ephemeral)
```

## Quick Routines
```bash
# Store insight
curl -s -X POST http://aria-api:8000/thoughts/ -H "Content-Type: application/json" \
  -d '{"content": "INSIGHT", "category": "observation"}'

# Store preference
curl -s -X POST http://aria-api:8000/memories/ -H "Content-Type: application/json" \
  -d '{"key": "KEY", "value": "VALUE", "category": "user_prefs"}'

# Store resource
curl -s -X POST http://aria-api:8000/knowledge-graph/entities -H "Content-Type: application/json" \
  -d '{"name": "RESOURCE", "entity_type": "resource", "properties": {...}}'
```

## Remember
- Files are for compression/archival
- DB is for active recall
- If I think "I should remember this" → DO IT NOW
- Routines exist: `get_thoughts()`, `get_memories()`, `graph_search()`

---
*Created: 2026-02-13 | Authority: Najia directive*
