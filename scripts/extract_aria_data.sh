#!/bin/bash
# Aria Data Extraction Script
# Run this on the Mac after SSH connection
# Usage: ./extract_aria_data.sh

set -e

BACKUP_DIR="/tmp/aria_backup_$(date +%Y%m%d_%H%M%S)"
echo "Creating backup directory: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

ARIA_HOME="${ARIA_HOME:-$HOME/aria_brain}"
if [ -f "$ARIA_HOME/.env" ]; then
    set -a
    source "$ARIA_HOME/.env"
    set +a
else
    echo "  ✗ Missing $ARIA_HOME/.env (DB credentials required)"
    exit 1
fi

echo ""
echo "=== Checking Docker ==="
if docker ps > /dev/null 2>&1; then
    echo "Docker is running"
    
    # Check if aria-db container exists
    if docker ps -a | grep -q aria-db; then
        echo "Found aria-db container"
        
        if docker ps | grep -q aria-db; then
            echo "aria-db is running - extracting database..."
            docker exec aria-db pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP_DIR/aria_warehouse_full.sql" && echo "  ✓ Full dump created"
            docker exec aria-db pg_dump -U "$DB_USER" --schema-only "$DB_NAME" > "$BACKUP_DIR/aria_warehouse_schema.sql" && echo "  ✓ Schema dump created"
            docker exec aria-db pg_dump -U "$DB_USER" --data-only "$DB_NAME" > "$BACKUP_DIR/aria_warehouse_data.sql" && echo "  ✓ Data dump created"
        else
            echo "aria-db exists but not running - attempting to start..."
            docker start aria-db
            sleep 5
            if docker ps | grep -q aria-db; then
                echo "aria-db started - extracting database..."
                docker exec aria-db pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP_DIR/aria_warehouse_full.sql"
            else
                echo "  ✗ Failed to start aria-db"
            fi
        fi
    else
        echo "  ⚠ No aria-db container found"
    fi
else
    echo "  ✗ Docker is not running"
fi

echo ""
echo "=== Extracting Clawdbot Sessions ==="
if [ -d ~/.clawdbot/agents ]; then
    cp -r ~/.clawdbot/agents "$BACKUP_DIR/clawdbot_agents"
    echo "  ✓ Clawdbot agents copied"
else
    echo "  ⚠ No ~/.clawdbot/agents found"
fi

if [ -d ~/.clawdbot/logs ]; then
    cp -r ~/.clawdbot/logs "$BACKUP_DIR/clawdbot_logs"
    echo "  ✓ Clawdbot logs copied"
else
    echo "  ⚠ No ~/.clawdbot/logs found"
fi

if [ -f ~/.clawdbot/clawdbot.json ]; then
    cp ~/.clawdbot/clawdbot.json "$BACKUP_DIR/"
    echo "  ✓ Clawdbot config copied"
fi

echo ""
echo "=== Extracting OpenClaw Sessions ==="
if [ -d ~/.openclaw/agents ]; then
    cp -r ~/.openclaw/agents "$BACKUP_DIR/openclaw_agents"
    echo "  ✓ OpenClaw agents copied"
else
    echo "  ⚠ No ~/.openclaw/agents found"
fi

echo ""
echo "=== Extracting Clawd Workspace ==="
if [ -d ~/clawd ]; then
    mkdir -p "$BACKUP_DIR/clawd"
    
    # Soul files
    for f in SOUL.md IDENTITY.md USER.md AGENTS.md TOOLS.md HEARTBEAT.md BOOTSTRAP.md MEMORY.md; do
        if [ -f ~/clawd/$f ]; then
            cp ~/clawd/$f "$BACKUP_DIR/clawd/"
            echo "  ✓ $f copied"
        fi
    done
    
    # Memory folder
    if [ -d ~/clawd/memory ]; then
        cp -r ~/clawd/memory "$BACKUP_DIR/clawd_memory"
        echo "  ✓ Memory folder copied"
    fi
    
    # Docker stacks
    if [ -d ~/clawd/stacks ]; then
        cp -r ~/clawd/stacks "$BACKUP_DIR/clawd_stacks"
        echo "  ✓ Docker stacks copied"
    fi
else
    echo "  ⚠ No ~/clawd found"
fi

echo ""
echo "=== Creating Archive ==="
cd /tmp
ARCHIVE_NAME="aria_backup_$(date +%Y%m%d_%H%M%S).tar.gz"
tar -czvf "$ARCHIVE_NAME" "$(basename $BACKUP_DIR)"
echo "  ✓ Archive created: /tmp/$ARCHIVE_NAME"

echo ""
echo "=== Summary ==="
echo "Backup directory: $BACKUP_DIR"
echo "Archive file: /tmp/$ARCHIVE_NAME"
echo ""
echo "Contents:"
ls -la "$BACKUP_DIR"
echo ""
echo "Archive size: $(du -h /tmp/$ARCHIVE_NAME | cut -f1)"
echo ""
echo "To transfer to Windows, run from PowerShell:"
echo "scp -i <SSH_KEY_PATH> <USER>@<HOST>:/tmp/$ARCHIVE_NAME <LOCAL_PATH>"
