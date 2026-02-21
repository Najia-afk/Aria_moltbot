# Aria Database Schema Reference
## aria_warehouse — PostgreSQL 16 + pgvector
### Snapshot: 2026-02-16

**Driver:** pgvector/pgvector:pg16  
**ORM:** SQLAlchemy 2.0 async + psycopg3  
**Extensions:** uuid-ossp, pg_trgm, vector (pgvector 768-dim)  
**Canonical source:** `src/api/db/models.py` (686 lines, 28 ORM models)

---

## Table Inventory — 44 Tables by Row Count

| Table | Rows | Domain | ORM Model |
|-------|------|--------|-----------|
| `skill_invocations` | 18,083 | Telemetry | `SkillInvocation` |
| `agent_sessions` | 8,444 | Operations | `AgentSession` |
| `activity_log` | 7,297 | Core | `ActivityLog` |
| `model_usage` | 7,024 | Operations | `ModelUsage` |
| `skill_graph_entities` | 278 | Knowledge | `SkillGraphEntity` |
| `skill_graph_relations` | 270 | Knowledge | `SkillGraphRelation` |
| `social_posts` | 162 | Social | `SocialPost` |
| `knowledge_query_log` | 144 | Knowledge | `KnowledgeQueryLog` |
| `goals` | 109 | Core | `Goal` |
| `thoughts` | 80 | Core | `Thought` |
| `lessons_learned` | 80 | Self-Improve | `LessonLearned` |
| `hourly_goals` | 62 | Scheduling | `HourlyGoal` |
| `skill_status` | 35 | Registry | `SkillStatusRecord` |
| `memories` | 32 | Core | `Memory` |
| `pending_complex_tasks` | 30 | Operations | `PendingComplexTask` |
| `knowledge_entities` | 19 | Knowledge | `KnowledgeEntity` |
| `security_events` | 16 | Security | `SecurityEvent` |
| `performance_log` | 15 | Performance | `PerformanceLog` |
| `knowledge_relations` | 15 | Knowledge | `KnowledgeRelation` |
| `heartbeat_log` | 15 | Operations | `HeartbeatLog` |
| `api_key_rotations` | 14 | Security | `ApiKeyRotation` |
| `schema_migrations` | 13 | System | (alembic) |
| `model_cost_reference` | 10 | Operations | (raw SQL) |
| `working_memory` | 8 | Core | `WorkingMemory` |
| `scheduled_jobs` | 7 | Scheduling | `ScheduledJob` |
| `improvement_proposals` | 6 | Self-Improve | `ImprovementProposal` |
| `moltbook_posts` | 3 | Social | (raw SQL) |
| `semantic_memories` | 0 | Memory | `SemanticMemory` |
| `agent_performance` | 0 | Operations | `AgentPerformance` |
| `rate_limits` | 1 | Operations | `RateLimit` |
| `schedule_tick` | 0 | Scheduling | `ScheduleTick` |
| *+13 legacy/moltbook tables* | 0–1 | Legacy | (raw SQL) |

---

## Core Models — Column Details

### Memory (`memories`)
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | auto-generated |
| key | VARCHAR(255) | unique, indexed |
| value | JSONB | GIN indexed |
| category | VARCHAR(100) | default 'general' |
| created_at / updated_at | TIMESTAMPTZ | auto |

### SemanticMemory (`semantic_memories`)
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | auto-generated |
| content | TEXT | not null |
| summary | TEXT | nullable |
| category | VARCHAR(50) | default 'general' |
| embedding | VECTOR(768) | pgvector, not null |
| metadata | JSONB | default '{}' |
| importance | FLOAT | default 0.5 |
| source | VARCHAR(100) | nullable |
| created_at | TIMESTAMPTZ | auto |
| accessed_at | TIMESTAMPTZ | nullable |
| access_count | INTEGER | default 0 |

### WorkingMemory (`working_memory`)
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | auto-generated |
| category | VARCHAR(50) | not null |
| key | VARCHAR(200) | not null |
| value | JSONB | not null |
| importance | FLOAT | default 0.5 |
| ttl_hours | INTEGER | nullable |
| source | VARCHAR(100) | nullable |
| checkpoint_id | VARCHAR(100) | nullable |
| created_at / updated_at / accessed_at | TIMESTAMPTZ | auto |
| access_count | INTEGER | default 0 |
| **unique constraint** | (category, key) | |

### AgentSession (`agent_sessions`)
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | auto-generated |
| agent_id | VARCHAR(100) | not null, indexed |
| session_type | VARCHAR(50) | default 'interactive' |
| started_at / ended_at | TIMESTAMPTZ | auto / nullable |
| messages_count | INTEGER | default 0 |
| tokens_used | INTEGER | default 0 |
| cost_usd | NUMERIC(10,6) | default 0 |
| status | VARCHAR(50) | default 'active' |
| metadata | JSONB | GIN indexed |
| **expression index** | `metadata->>'openclaw_session_id'` | |

### Goal (`goals`)
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | auto-generated |
| goal_id | VARCHAR(100) | unique |
| title | VARCHAR(255) | not null |
| description | TEXT | nullable |
| status | VARCHAR(50) | default 'pending' |
| priority | INTEGER | default 2 |
| progress | NUMERIC(5,2) | default 0 |
| sprint | VARCHAR(100) | default 'backlog' |
| board_column | VARCHAR(50) | default 'backlog' |
| position | INTEGER | default 0 |
| assigned_to | VARCHAR(100) | nullable |
| tags | JSONB | default '[]' |
| due_date / created_at / completed_at / updated_at | TIMESTAMPTZ | |

### KnowledgeEntity + KnowledgeRelation (`knowledge_entities`, `knowledge_relations`)
- Organic knowledge graph (user-curated, research)
- Entity: name, type, properties (JSONB), timestamps
- Relation: from_entity FK → to_entity FK, relation_type, properties

### SkillGraphEntity + SkillGraphRelation (`skill_graph_entities`, `skill_graph_relations`)
- Auto-generated from skill.json files (idempotent sync)
- Separate from organic KG to prevent collision
- Entity types: skill, tool, focus_mode, category
- Relation types: provides, belongs_to, affinity, depends_on

---

## Index Strategy

| Pattern | Tables | Type |
|---------|--------|------|
| `_created` (DESC) | All tables | B-tree |
| `_gin` | memories.value, activity_log.details, thoughts.content | GIN / gin_trgm_ops |
| `_status` | goals, sessions, tasks | B-tree |
| Combined (status + priority + created) | goals | Composite B-tree |
| Expression index | agent_sessions | `metadata->>'openclaw_session_id'` |
| Unique constraints | working_memory(category,key), skill_graph(name,type) | |

---

## Architecture Layer Map

```
5-Layer Architecture (NEVER violate):

Database (PostgreSQL 16 + pgvector)
    ↕
SQLAlchemy ORM (src/api/db/models.py)
    ↕
FastAPI API (src/api/routers/*.py — ~105 endpoints)
    ↕
api_client (aria_skills/api_client/ — httpx AsyncClient)
    ↕
Skills (aria_skills/*/) + ARIA Mind/Agents
```

**Rules:**
- Skills NEVER import SQLAlchemy or make raw SQL
- Skills NEVER call other skills directly  
- All DB access through ORM → API → api_client
- api_client has circuit breaker (5 fails → 30s cooldown) + retry (3x, 0.5s backoff)
