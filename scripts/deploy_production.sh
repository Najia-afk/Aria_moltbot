#!/bin/bash
set -euo pipefail

# ============================================================================
# Aria Blue — Production Deployment Script
# ============================================================================
#
# Deploys aria_engine to the production Mac Mini.
#
# Usage:
#   ./scripts/deploy_production.sh                    # Full deploy
#   ./scripts/deploy_production.sh --dry-run          # Preview only
#   ./scripts/deploy_production.sh --skip-backup      # Skip backup step
#   ./scripts/deploy_production.sh --rollback         # Rollback to previous
#
# Requirements:
#   - SSH key: ~/.ssh/najia_mac_key
#   - Target: najia@192.168.1.53
#   - Docker + Docker Compose on target
#
# ============================================================================

# --- Configuration ---
REMOTE_USER="najia"
REMOTE_HOST="192.168.1.53"
SSH_KEY="$HOME/.ssh/najia_mac_key"
REMOTE_DIR="/home/najia/aria"
COMPOSE_FILE="stacks/brain/docker-compose.yml"
BACKUP_DIR="/home/najia/aria/backups"
DEPLOY_LOG="/home/najia/aria/deploy.log"

# --- Flags ---
DRY_RUN=false
SKIP_BACKUP=false
ROLLBACK=false

for arg in "$@"; do
    case $arg in
        --dry-run)    DRY_RUN=true ;;
        --skip-backup) SKIP_BACKUP=true ;;
        --rollback)   ROLLBACK=true ;;
        *)            echo "Unknown argument: $arg"; exit 1 ;;
    esac
done

# --- Helpers ---
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() { echo -e "${GREEN}[DEPLOY]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

ssh_cmd() {
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$REMOTE_USER@$REMOTE_HOST" "$@"
}

scp_to() {
    scp -i "$SSH_KEY" -o StrictHostKeyChecking=no "$1" "$REMOTE_USER@$REMOTE_HOST:$2"
}

# --- Pre-flight checks ---
preflight() {
    log "Running pre-flight checks..."

    # SSH connectivity
    if ! ssh_cmd "echo 'SSH OK'" > /dev/null 2>&1; then
        error "Cannot connect to $REMOTE_HOST"
        exit 1
    fi
    log "  SSH: OK"

    # Docker available
    if ! ssh_cmd "docker --version" > /dev/null 2>&1; then
        error "Docker not available on remote host"
        exit 1
    fi
    log "  Docker: OK"

    # Docker Compose available
    if ! ssh_cmd "docker compose version" > /dev/null 2>&1; then
        error "Docker Compose not available on remote host"
        exit 1
    fi
    log "  Docker Compose: OK"

    # Disk space (need at least 5GB free)
    FREE_KB=$(ssh_cmd "df -k /home/najia | tail -1 | awk '{print \$4}'")
    FREE_GB=$((FREE_KB / 1024 / 1024))
    if [ "$FREE_GB" -lt 5 ]; then
        error "Insufficient disk space: ${FREE_GB}GB free (need 5GB)"
        exit 1
    fi
    log "  Disk space: ${FREE_GB}GB free"

    # Remote directory exists
    if ! ssh_cmd "test -d $REMOTE_DIR"; then
        error "Remote directory $REMOTE_DIR does not exist"
        exit 1
    fi
    log "  Remote directory: OK"

    log "Pre-flight checks passed!"
}

# --- Backup ---
backup() {
    if [ "$SKIP_BACKUP" = true ]; then
        warn "Skipping backup (--skip-backup)"
        return
    fi

    log "Creating backup..."
    ssh_cmd "mkdir -p $BACKUP_DIR"

    # Backup database
    log "  Backing up database..."
    ssh_cmd "cd $REMOTE_DIR && docker compose exec -T aria-db pg_dump -U ${DB_USER:-admin} ${DB_NAME:-aria_warehouse} > $BACKUP_DIR/db_${TIMESTAMP}.sql"

    # Backup docker-compose.yml
    ssh_cmd "cp $REMOTE_DIR/$COMPOSE_FILE $BACKUP_DIR/docker-compose_${TIMESTAMP}.yml"

    # Backup .env
    ssh_cmd "cp $REMOTE_DIR/.env $BACKUP_DIR/env_${TIMESTAMP}" 2>/dev/null || true

    # Tag current images
    ssh_cmd "cd $REMOTE_DIR && docker compose images --format json | python3 -c '
import sys, json
for line in sys.stdin:
    data = json.loads(line)
    print(data.get(\"Repository\", \"\") + \":\" + data.get(\"Tag\", \"\"))
' > $BACKUP_DIR/images_${TIMESTAMP}.txt" || true

    log "  Backup saved to $BACKUP_DIR/*_${TIMESTAMP}.*"
}

# --- Deploy ---
deploy() {
    log "Starting deployment (${TIMESTAMP})..."

    if [ "$DRY_RUN" = true ]; then
        warn "DRY RUN — no changes will be made"
    fi

    # Step 1: Sync files
    log "Step 1/7: Syncing project files..."
    if [ "$DRY_RUN" = false ]; then
        rsync -avz --delete \
            --exclude '.git' \
            --exclude '__pycache__' \
            --exclude '.venv' \
            --exclude 'node_modules' \
            --exclude 'aria_memories/logs' \
            --exclude '*.pyc' \
            --exclude '.env' \
            -e "ssh -i $SSH_KEY" \
            ./ "$REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR/"
    fi

    # Step 2: Pull new images
    log "Step 2/7: Pulling updated images..."
    if [ "$DRY_RUN" = false ]; then
        ssh_cmd "cd $REMOTE_DIR && docker compose pull --quiet"
    fi

    # Step 3: Build custom images
    log "Step 3/7: Building aria-engine image..."
    if [ "$DRY_RUN" = false ]; then
        ssh_cmd "cd $REMOTE_DIR && docker compose build --no-cache aria-brain aria-api"
    fi

    # Step 4: Run database migrations
    log "Step 4/7: Running database migrations..."
    if [ "$DRY_RUN" = false ]; then
        ssh_cmd "cd $REMOTE_DIR && docker compose exec -T aria-api sh -c 'cd /app && python -m alembic upgrade head'" || {
            error "Database migration failed!"
            warn "Rolling back..."
            rollback
            exit 1
        }
    fi

    # Step 5: Rolling restart (zero-downtime)
    log "Step 5/7: Rolling restart..."
    if [ "$DRY_RUN" = false ]; then
        # Start new containers alongside old ones
        # Order matters: DB first, then services, then web
        SERVICES="aria-db litellm aria-brain aria-api aria-web"
        for SERVICE in $SERVICES; do
            log "  Restarting $SERVICE..."
            ssh_cmd "cd $REMOTE_DIR && docker compose up -d --no-deps --build $SERVICE"
            sleep 5  # Allow service to stabilize

            # Quick health check per service
            if ! ssh_cmd "cd $REMOTE_DIR && docker compose ps $SERVICE | grep -q 'Up'" 2>/dev/null; then
                error "  $SERVICE failed to start!"
                warn "  Rolling back..."
                rollback
                exit 1
            fi
            log "  $SERVICE: UP"
        done
    fi

    # Step 6: Health verification
    log "Step 6/7: Verifying health..."
    if [ "$DRY_RUN" = false ]; then
        verify_health || {
            error "Health check failed!"
            warn "Rolling back..."
            rollback
            exit 1
        }
    fi

    # Step 7: Cleanup
    log "Step 7/7: Cleaning up..."
    if [ "$DRY_RUN" = false ]; then
        ssh_cmd "cd $REMOTE_DIR && docker image prune -f" || true
        ssh_cmd "echo '[${TIMESTAMP}] Deploy successful' >> $DEPLOY_LOG"
    fi

    log "Deployment complete! (${TIMESTAMP})"
}

# --- Health verification ---
verify_health() {
    log "  Running health checks..."

    # Check all containers are running
    RUNNING=$(ssh_cmd "cd $REMOTE_DIR && docker compose ps --status running -q | wc -l")
    EXPECTED=10  # aria-db, aria-browser, aria-engine, tor-proxy, traefik, litellm, aria-brain, aria-web, aria-api, docker-socket-proxy
    if [ "$RUNNING" -lt "$EXPECTED" ]; then
        error "  Only $RUNNING/$EXPECTED containers running"
        return 1
    fi
    log "  Containers: $RUNNING/$EXPECTED running"

    # HTTP health check
    for endpoint in "http://localhost:8000/health" "http://localhost:8000/api/health" "http://localhost:8081/metrics"; do
        STATUS=$(ssh_cmd "curl -s -o /dev/null -w '%{http_code}' $endpoint" 2>/dev/null || echo "000")
        if [ "$STATUS" != "200" ]; then
            error "  Health check failed: $endpoint returned $STATUS"
            return 1
        fi
        log "  $endpoint: OK ($STATUS)"
    done

    # Database connectivity
    DB_STATUS=$(ssh_cmd "cd $REMOTE_DIR && docker compose exec -T aria-db pg_isready -U ${DB_USER:-admin}" 2>/dev/null || echo "FAIL")
    if echo "$DB_STATUS" | grep -q "accepting connections"; then
        log "  Database: OK"
    else
        error "  Database health check failed"
        return 1
    fi

    # Check aria_engine version
    VERSION=$(ssh_cmd "curl -s http://localhost:8000/api/status | python3 -c 'import sys,json; print(json.load(sys.stdin).get(\"version\",\"unknown\"))'" 2>/dev/null || echo "unknown")
    log "  Version: $VERSION"

    # Check metrics endpoint
    METRICS=$(ssh_cmd "curl -s http://localhost:8081/metrics | grep -c 'aria_'" 2>/dev/null || echo "0")
    log "  Metrics: $METRICS aria_* metrics exposed"

    log "  All health checks passed!"
    return 0
}

# --- Rollback ---
rollback() {
    log "Starting rollback..."

    # Find latest backup
    LATEST_BACKUP=$(ssh_cmd "ls -t $BACKUP_DIR/db_*.sql 2>/dev/null | head -1")
    LATEST_COMPOSE=$(ssh_cmd "ls -t $BACKUP_DIR/docker-compose_*.yml 2>/dev/null | head -1")

    if [ -z "$LATEST_BACKUP" ]; then
        error "No backup found! Manual intervention required."
        exit 1
    fi

    log "  Restoring from: $LATEST_BACKUP"

    # Restore docker-compose.yml
    if [ -n "$LATEST_COMPOSE" ]; then
        ssh_cmd "cp $LATEST_COMPOSE $REMOTE_DIR/$COMPOSE_FILE"
    fi

    # Restore database
    ssh_cmd "cd $REMOTE_DIR && docker compose exec -T aria-db psql -U ${DB_USER:-admin} ${DB_NAME:-aria_warehouse} < $LATEST_BACKUP"

    # Restart with restored config
    ssh_cmd "cd $REMOTE_DIR && docker compose up -d"

    # Wait and verify
    sleep 10
    if verify_health 2>/dev/null; then
        log "Rollback successful!"
        ssh_cmd "echo '[${TIMESTAMP}] Rollback successful' >> $DEPLOY_LOG"
    else
        error "Rollback health check failed! MANUAL INTERVENTION REQUIRED."
        ssh_cmd "echo '[${TIMESTAMP}] ROLLBACK FAILED - NEEDS MANUAL FIX' >> $DEPLOY_LOG"
        exit 1
    fi
}

# ============================================================================
# Main
# ============================================================================

echo "============================================"
echo "  ARIA BLUE - PRODUCTION DEPLOYMENT"
echo "  Target: $REMOTE_USER@$REMOTE_HOST"
echo "  Time:   $TIMESTAMP"
if [ "$DRY_RUN" = true ]; then
    echo "  Mode:   DRY RUN"
fi
if [ "$ROLLBACK" = true ]; then
    echo "  Mode:   ROLLBACK"
fi
echo "============================================"
echo ""

preflight

if [ "$ROLLBACK" = true ]; then
    rollback
else
    backup
    deploy
fi

echo ""
echo "Done."
