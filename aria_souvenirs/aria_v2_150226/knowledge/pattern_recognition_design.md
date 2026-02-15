# Pattern Recognition System Design

## Overview
Auto-detect recurring user request patterns and suggest solutions proactively.

## Schema

### Pattern Entity
```
pattern_id: UUID (unique)
pattern_signature: string (normalized request fingerprint)
request_type: string (categorized intent)
frequency_count: integer (how often seen)
last_seen: timestamp
success_rate: float (0-1, based on outcome)
associated_skills: string[] (skills that resolved this)
solution_template: string (template response)
confidence_threshold: float (min score to trigger suggestion)
```

### Pattern Match Log
```
match_id: UUID
pattern_id: FK
user_id: string (anonymous hash)
request_raw: string (original request)
match_score: float (similarity score)
was_helpful: boolean (user feedback)
created_at: timestamp
```

## Detection Pipeline
1. Normalize incoming request (lowercase, stem, strip noise)
2. Generate fingerprint hash
3. Query knowledge graph for similar patterns
4. If match_score > threshold → suggest solution
5. Log match outcome for reinforcement learning

## Integration Points
- Hook into api-client skill for request logging
- Query knowledge_graph for pattern storage
- Update confidence based on user feedback
