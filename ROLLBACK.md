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
| `s42` | Add FK constraints | Adds FKs | Drops FKs |
| `s37` | Drop orphan tables | Drops tables | **NO RECOVERY** |
| `s44` | Add GIN indexes | Creates indexes | Drops indexes |
| `s46` | Legacy session ID index | Adds index | Drops index |
| `s47` | Create sentiment events | Creates table | Drops table |
| `s48` | Add aria_engine tables (6 tables) | Creates tables + indexes | Drops tables |

> **WARNING**: Migration `s37` (drop orphan tables) is irreversible. If you need to
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
