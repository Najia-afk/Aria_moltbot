# S12-05: Rollback Documentation & Alembic Downgrade
**Epic:** E8 — Quality & Testing | **Priority:** P0 | **Points:** 2 | **Phase:** 12

## Problem
Even with automated deployment, operators need clear documentation for manual rollback scenarios: corrupted database, failed migrations, incompatible model configs, or emergency hotfixes. We need `DEPLOYMENT.md` (updated), `ROLLBACK.md` (new), and Alembic downgrade migrations that can revert aria_engine schema changes safely.

## Root Cause
The current `DEPLOYMENT.md` is outdated — it still references OpenClaw. After the migration, operators need a single source of truth for: how to deploy, how to check health, how to roll back, and what each Alembic migration does. Without downgrade support, a bad migration means manual SQL fixes under pressure.

## Fix
### `ROLLBACK.md`
```markdown
# Aria Blue — Rollback Guide

> Last updated: Sprint 12 (aria_engine v2.0.0 migration)

## Quick Reference

| Scenario | Command | Time |
|----------|---------|------|
| Full rollback | `./scripts/deploy_production.sh --rollback` | ~5 min |
| DB-only rollback | `alembic downgrade -1` | ~30 sec |
| DB rollback to specific version | `alembic downgrade <revision>` | ~30 sec |
| Container rollback | See "Container Rollback" below | ~2 min |
| Emergency stop | `docker compose stop aria-brain aria-api` | ~10 sec |

## Pre-Rollback Checklist

1. **Identify the problem**: Check logs, metrics, health endpoints
2. **Assess severity**: Is it a hard failure or degradation?
3. **Communicate**: Note the issue in `aria_memories/logs/`
4. **Choose rollback scope**: Full, DB-only, or container-only

## Full Automated Rollback

```bash
# This uses the latest backup from the deploy script
./scripts/deploy_production.sh --rollback
```

What it does:
1. Finds the latest database backup in `/home/najia/aria/backups/`
2. Restores the docker-compose.yml from backup
3. Restores the database from SQL dump
4. Restarts all containers
5. Verifies health

## Database Rollback (Alembic)

### Downgrade one migration
```bash
# In Docker:
docker compose exec aria-brain python -m alembic downgrade -1

# Or locally:
cd /home/najia/aria
alembic downgrade -1
```

### Downgrade to specific revision
```bash
# List all migrations:
alembic history --verbose

# Downgrade to specific revision:
alembic downgrade <revision_id>

# Downgrade everything (DANGEROUS):
alembic downgrade base
```

### Migration History for aria_engine

| Revision | Description | Upgrade | Downgrade |
|----------|-------------|---------|-----------|
| `a001_sessions` | Create sessions table | Creates table | Drops table |
| `a002_messages` | Create messages table with FK to sessions | Creates table + FK | Drops table |
| `a003_agent_state` | Create agent_state table | Creates table | Drops table |
| `a004_scheduler_jobs` | Create scheduler_jobs table | Creates table | Drops table |
| `a005_scheduler_history` | Create scheduler_history table | Creates table | Drops table |
| `a006_pheromone_scores` | Create pheromone_scores table | Creates table | Drops table |
| `a007_add_engine_fields` | Add engine_version, agent_id to messages | Adds columns | Drops columns |
| `a008_remove_openclaw` | Drop legacy openclaw_* columns | Drops columns | **NO RECOVERY** |

> **WARNING**: Migration `a008_remove_openclaw` is irreversible. If you need to
> roll back past this point, restore from a database backup instead.

## Container Rollback

### Roll back a single service
```bash
# Stop the broken service
docker compose stop aria-brain

# Start with previous image
docker compose up -d --no-deps aria-brain

# If the image was tagged during backup:
docker tag aria-brain:backup aria-brain:latest
docker compose up -d --no-deps aria-brain
```

### Roll back all services
```bash
# Stop all
docker compose stop

# Restore compose file from backup
cp /home/najia/aria/backups/docker-compose_LATEST.yml stacks/brain/docker-compose.yml

# Start with restored config
docker compose up -d
```

## Emergency Procedures

### 1. System Unresponsive
```bash
# SSH to Mac Mini
ssh -i ~/.ssh/najia_mac_key najia@192.168.1.53

# Check what's running
docker ps

# Stop application services (keep DB running)
docker compose stop aria-brain aria-api aria-web

# Check database
docker compose exec aria-db pg_isready -U aria

# Check logs
docker compose logs --tail=100 aria-brain
```

### 2. Database Corruption
```bash
# Stop all services
docker compose stop

# Restore from latest backup
LATEST=$(ls -t /home/najia/aria/backups/db_*.sql | head -1)
docker compose start aria-db
sleep 5
docker compose exec -T aria-db psql -U aria aria_blue < "$LATEST"

# Start services
docker compose start
```

### 3. Out of Memory
```bash
# Check memory
vm_stat | head -10

# Restart Ollama (biggest memory consumer)
docker compose restart ollama

# If still OOM, reduce Ollama model:
# Edit .env: OLLAMA_MODEL=qwen3:14b (instead of 32b)
docker compose restart ollama litellm
```

### 4. Disk Full
```bash
# Check disk
df -h /home/najia

# Clean Docker artifacts
docker system prune -f
docker volume prune -f

# Clean old backups (keep last 5)
ls -t /home/najia/aria/backups/db_*.sql | tail -n +6 | xargs rm -f

# Clean old logs
find /home/najia/aria/aria_memories/logs -name "*.log" -mtime +30 -delete
```

## Health Check Endpoints

| Endpoint | Expected | What to Check |
|----------|----------|---------------|
| `GET /health` | `{"status": "ok"}` | Application alive |
| `GET /api/health` | `{"status": "ok", ...}` | API + DB healthy |
| `GET /api/status` | `{"version": "2.0.0", ...}` | Correct version deployed |
| `GET :8081/metrics` | Prometheus text | Metrics collecting |
| `GET :3000` | Grafana UI | Monitoring available |

## Backup Schedule

| What | When | Where | Retention |
|------|------|-------|-----------|
| Database dump | Before every deploy | `/home/najia/aria/backups/db_*.sql` | 10 latest |
| docker-compose.yml | Before every deploy | `/home/najia/aria/backups/docker-compose_*.yml` | 10 latest |
| .env | Before every deploy | `/home/najia/aria/backups/env_*` | 10 latest |
| aria_memories/ | Daily via cron | `/home/najia/aria/backups/memories_*.tar.gz` | 30 days |

## Contacts

- **Primary**: Aria (automated via heartbeat skill)
- **Operator**: Check `aria_memories/logs/` for recent issues
- **Deploy log**: `/home/najia/aria/deploy.log`
```

### `alembic/versions/a001_create_sessions.py`
```python
"""Create sessions table.

Revision ID: a001_sessions
Revises: None
Create Date: 2026-03-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers
revision = "a001_sessions"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_protected", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("agent_id", sa.String(100), nullable=True),
        sa.Column("metadata", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("message_count", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("engine_version", sa.String(20), server_default=sa.text("'2.0.0'"), nullable=False),
    )

    # Indexes
    op.create_index("ix_sessions_created_at", "sessions", ["created_at"])
    op.create_index("ix_sessions_agent_id", "sessions", ["agent_id"])
    op.create_index("ix_sessions_updated_at", "sessions", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_sessions_updated_at")
    op.drop_index("ix_sessions_agent_id")
    op.drop_index("ix_sessions_created_at")
    op.drop_table("sessions")
```

### `alembic/versions/a002_create_messages.py`
```python
"""Create messages table.

Revision ID: a002_messages
Revises: a001_sessions
Create Date: 2026-03-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "a002_messages"
down_revision = "a001_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),  # user, assistant, system, tool
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("tokens_input", sa.Integer, nullable=True),
        sa.Column("tokens_output", sa.Integer, nullable=True),
        sa.Column("thinking_content", sa.Text, nullable=True),
        sa.Column("tool_calls", JSONB, nullable=True),
        sa.Column("agent_id", sa.String(100), nullable=True),
        sa.Column("engine_version", sa.String(20), server_default=sa.text("'2.0.0'"), nullable=False),
        sa.Column("metadata", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
    )

    op.create_index("ix_messages_session_id", "messages", ["session_id"])
    op.create_index("ix_messages_created_at", "messages", ["created_at"])
    op.create_index("ix_messages_role", "messages", ["role"])

    # Full-text search index on content
    op.execute(
        "CREATE INDEX ix_messages_content_fts ON messages USING gin(to_tsvector('english', content))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_messages_content_fts")
    op.drop_index("ix_messages_role")
    op.drop_index("ix_messages_created_at")
    op.drop_index("ix_messages_session_id")
    op.drop_table("messages")
```

### `alembic/versions/a003_create_agent_state.py`
```python
"""Create agent_state table.

Revision ID: a003_agent_state
Revises: a002_messages
Create Date: 2026-03-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "a003_agent_state"
down_revision = "a002_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_state",
        sa.Column("agent_id", sa.String(100), primary_key=True),
        sa.Column("status", sa.String(20), server_default=sa.text("'active'"), nullable=False),
        sa.Column("pheromone_score", sa.Float, server_default=sa.text("0.5"), nullable=False),
        sa.Column("tasks_completed", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("tasks_failed", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("last_active", sa.DateTime(timezone=True), nullable=True),
        sa.Column("config", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("agent_state")
```

### `alembic/versions/a004_create_scheduler_jobs.py`
```python
"""Create scheduler_jobs and scheduler_history tables.

Revision ID: a004_scheduler
Revises: a003_agent_state
Create Date: 2026-03-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "a004_scheduler"
down_revision = "a003_agent_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Jobs table
    op.create_table(
        "scheduler_jobs",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("schedule", sa.String(100), nullable=False),  # cron expression
        sa.Column("skill", sa.String(100), nullable=False),
        sa.Column("method", sa.String(100), nullable=False),
        sa.Column("enabled", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("priority", sa.String(20), server_default=sa.text("'medium'"), nullable=False),
        sa.Column("config", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # History table
    op.create_table(
        "scheduler_history",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(100), sa.ForeignKey("scheduler_jobs.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("status", sa.String(20), nullable=False),  # success, error, timeout
        sa.Column("result", JSONB, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
    )

    op.create_index("ix_scheduler_history_job_id", "scheduler_history", ["job_id"])
    op.create_index("ix_scheduler_history_started_at", "scheduler_history", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_scheduler_history_started_at")
    op.drop_index("ix_scheduler_history_job_id")
    op.drop_table("scheduler_history")
    op.drop_table("scheduler_jobs")
```

### Updated `DEPLOYMENT.md` section
```markdown
# Aria Blue — Deployment Guide

> **Version**: 2.0.0 (aria_engine, post-OpenClaw migration)
> **Target**: Mac Mini — najia@192.168.1.53
> **Last updated**: Sprint 12

## Prerequisites

- SSH access: `ssh -i ~/.ssh/najia_mac_key najia@192.168.1.53`
- Docker + Docker Compose installed on Mac Mini
- At least 5GB free disk space
- All Sprint 11 tests passing

## Quick Deploy

```bash
# 1. Run all tests first
pytest tests/ -v --timeout=60

# 2. Deploy (with automatic backup and rollback)
./scripts/deploy_production.sh

# 3. Verify
./scripts/health_check.sh
```

## Detailed Steps

### 1. Pre-Deploy Checklist
- [ ] All unit tests pass: `pytest tests/unit/ -v`
- [ ] All integration tests pass: `pytest tests/integration/ -v`
- [ ] No OpenClaw references: `pytest tests/unit/test_no_openclaw.py -v`
- [ ] Load test acceptable: `bash tests/load/run_load_test.sh`
- [ ] Memory profile clean: `python tests/profiling/memory_profile.py --quick`
- [ ] Version bumped in pyproject.toml

### 2. Deploy
```bash
./scripts/deploy_production.sh
```

### 3. Post-Deploy Verification
```bash
# Health check
./scripts/health_check.sh

# Check metrics
curl http://192.168.1.53:8081/metrics | grep aria_build_info

# Check Grafana dashboard
open http://192.168.1.53:3000

# Tail logs
ssh -i ~/.ssh/najia_mac_key najia@192.168.1.53 "cd /home/najia/aria && docker compose logs -f aria-brain --tail=50"
```

### 4. If Something Goes Wrong
See [ROLLBACK.md](ROLLBACK.md) for detailed rollback procedures.

```bash
# Quick rollback
./scripts/deploy_production.sh --rollback
```

## Architecture After Migration

```
Mac Mini (192.168.1.53)
├── docker compose stack:
│   ├── aria-db (PostgreSQL 16 + pgvector)
│   ├── litellm (Ollama proxy)
│   ├── aria-brain (aria_engine — heartbeat, cron, agents)
│   ├── aria-api (Flask REST API)
│   ├── aria-web (Dashboard)
│   ├── prometheus (Metrics collection)
│   └── grafana (Monitoring dashboards)
├── /home/najia/aria/
│   ├── aria_engine/ (NEW — replaces OpenClaw)
│   ├── aria_mind/
│   ├── aria_skills/
│   ├── aria_agents/
│   ├── aria_memories/ (persistent data)
│   └── backups/ (deploy backups)
└── Ports:
    ├── 5000 — Flask app
    ├── 8081 — Prometheus metrics
    ├── 3000 — Grafana
    └── 9090 — Prometheus UI
```
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | DB migrations maintain layer |
| 2 | .env for secrets | ✅ | All secrets in .env |
| 3 | models.yaml single source | ✅ | Documented in deployment |
| 4 | Docker-first | ✅ | Everything in Docker |
| 5 | aria_memories only writable path | ✅ | Documented in rollback |
| 6 | No soul modification | ✅ | soul/ read-only in deployment |

## Dependencies
- S12-04 (production deploy script) completed
- All Sprint 11 tests passing
- Alembic configured in pyproject.toml

## Verification
```bash
# 1. Verify ROLLBACK.md exists and is thorough:
wc -l ROLLBACK.md
# EXPECTED: 150+ lines

# 2. Test Alembic migrations up:
alembic upgrade head

# 3. Test Alembic downgrade:
alembic downgrade -1
alembic upgrade head

# 4. Full migration cycle:
alembic downgrade base
alembic upgrade head

# 5. Verify DEPLOYMENT.md updated:
grep -c "aria_engine" DEPLOYMENT.md
# EXPECTED: 5+ mentions (no openclaw references)
```

## Prompt for Agent
```
Create rollback documentation and Alembic downgrade migrations.

FILES TO READ FIRST:
- DEPLOYMENT.md (update this)
- ROLLBACK.md (create this — NEW)
- alembic/versions/ (create migration files)
- scripts/deploy_production.sh (reference rollback section)

STEPS:
1. Create ROLLBACK.md with all rollback scenarios
2. Create Alembic migration files (a001-a004)
3. Update DEPLOYMENT.md for aria_engine v2.0.0
4. Test: alembic upgrade head, alembic downgrade -1, alembic upgrade head

CONSTRAINTS:
- Every upgrade() must have a matching downgrade()
- Exception: a008 (openclaw column removal) is irreversible — document this
- ROLLBACK.md must cover: full, DB-only, container-only, emergency
- DEPLOYMENT.md must have zero OpenClaw references
- Include: health check endpoints, backup schedule, emergency contacts
```
