# Memory System Architecture Analysis

## Current Layer Structure

```
┌─────────────────────────────────────────────────────────────┐
│                     WORKING MEMORY                          │
│  (Short-term / Session Context)                             │
│  - Runtime state, active goals, transient observations     │
│  - TTL-based expiration, checkpointable                    │
│  - Syncs to aria_memories/memory/context.json              │
└─────────────────────────────────────────────────────────────┘
                              │ sync_to_files()
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    LONG-TERM MEMORY                         │
│  (PostgreSQL / aria_warehouse)                              │
│  - goals, activities, thoughts, memories                   │
│  - Durable, queryable, relational                          │
│  - api_client primary interface                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   KNOWLEDGE GRAPH                           │
│  (PostgreSQL + embeddings)                                  │
│  - Entities, relationships, semantic search                │
│  - Skill routing, cross-reference                          │
│  - graph_search(), graph_traverse()                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  FILE ARTIFACTS                             │
│  (aria_memories/ categorized storage)                       │
│  - logs/, research/, plans/, drafts/, exports/             │
│  - Human-readable, versionable, exportable                 │
│  - MemoryManager.ALLOWED_CATEGORIES enforced               │
└─────────────────────────────────────────────────────────────┘
```

## Identified Gap: Query Log Analysis

**Observation:** The api_client tracks query logs (`get_query_log()`) but there's no automated analysis of:
- Most/least used skills
- Error patterns over time
- Performance degradation signals

**Opportunity:** Create a `query_analyzer` skill that:
1. Runs weekly against query_log table
2. Identifies hot paths and cold skills
3. Proposes skill consolidation or deprecation
4. Alerts on error rate spikes

## Identified Gap: Cross-Layer Consistency

**Observation:** Working memory syncs to files, but there's no validation that:
- DB state matches file snapshot
- MemoryManager categories align with skill expectations
- Orphaned file artifacts exist without DB records

**Opportunity:** Add a `memory_consistency_check` that validates:
- goals in DB == goals in context.json
- file artifacts have corresponding activity records
- No writes outside ALLOWED_CATEGORIES

## Next Actions

1. Implement query_analyzer skill skeleton
2. Add consistency check to health monitoring
3. Document memory lifecycle for new developers

---
*Generated during work_cycle — 2026-02-15*
