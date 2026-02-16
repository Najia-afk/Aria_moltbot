# Memory Consolidation Pipeline

## Overview
Automated pipeline for consolidating short-term working memories into long-term storage based on importance scoring and temporal relevance.

## Components

### 1. Importance Scoring (✅ Implemented)
- Keywords: critical, urgent, error, security (up to 0.4)
- Action patterns: todo, task, fix, review (up to 0.2)
- Category bonuses: security=0.2, error=0.2, goal=0.15
- Content length normalization
- Emotional weight detection

### 2. Consolidation Triggers
- **Time-based**: Every 6 hours (heartbeat-driven)
- **Volume-based**: When working memory exceeds 100 entries
- **Manual**: Explicit consolidation request

### 3. Consolidation Rules
```python
CONSOLIDATION_THRESHOLD = 0.7  # Auto-promote if importance >= 0.7
AGE_THRESHOLD_HOURS = 24       # Consider for archival after 24h
MAX_SHORT_TERM_ITEMS = 100     # Hard limit for working memory
```

### 4. Pipeline Flow
```
Working Memory → Filter by age → Score importance → 
  → Importance >= 0.7? → Promote to long-term memory
  -> Age > 24h AND Importance < 0.5? → Archive to file
  -> Else → Keep in working memory
```

### 5. Storage Destinations
| Score | Action | Destination |
|-------|--------|-------------|
| >= 0.7 | Promote | PostgreSQL memories table |
| 0.5-0.7 | Keep | Working memory (refresh TTL) |
| < 0.5, >24h | Archive | aria_memories/archive/ |
| < 0.3, >48h | Purge | Delete |

### 6. Implementation Status
- [x] Importance scoring algorithm
- [x] Working memory sync to files
- [ ] Automated consolidation job (next)
- [ ] Archive cleanup job
- [ ] Cross-reference with knowledge graph

## Next Actions
1. Create cron job for consolidation (6h interval)
2. Implement archive cleanup (weekly)
3. Add KG linking for promoted memories
