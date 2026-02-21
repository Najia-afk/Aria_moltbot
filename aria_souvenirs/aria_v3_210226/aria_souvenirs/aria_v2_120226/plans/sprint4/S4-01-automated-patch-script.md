# S4-01: Create Automated Patch Script
**Epic:** Sprint 4 — Reliability & Self-Healing | **Priority:** P0 | **Points:** 5 | **Phase:** 4

## Problem
Patches are currently applied manually:
1. SSH into server
2. Edit files by hand or paste diffs
3. Restart containers one at a time
4. Hope nothing breaks

There is no rollback mechanism, no atomic application, no verification step, and no audit trail. A bad patch can leave the system in a half-applied state.

## Root Cause
No deployment automation exists. The current workflow is "edit in VSCode, docker compose restart." This is fragile and error-prone for a production system.

## Fix
Create `scripts/apply_patch.sh` — an atomic patch application script with:

```bash
#!/bin/bash
# scripts/apply_patch.sh — Atomic Patch Application
# Usage: ./scripts/apply_patch.sh <patch_dir>
#
# Patch directory structure:
#   patch_name/
#     manifest.yaml      # Files to modify, containers to restart
#     files/              # Replacement files (relative paths match project root)
#     rollback/           # Auto-populated during apply
#
# Workflow:
#   1. Validate manifest
#   2. Backup current files to rollback/
#   3. Apply new files atomically
#   4. Restart specified containers
#   5. Run verify_deployment.sh
#   6. If verify fails → auto-rollback + restart
#   7. Log result to aria_memories/logs/

set -euo pipefail

PATCH_DIR="${1:?Usage: apply_patch.sh <patch_dir>}"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$PROJECT_ROOT/aria_memories/logs/patch_${TIMESTAMP}.log"

# ... (implement full script)
```

### manifest.yaml format:
```yaml
name: "fix-python39-compat"
description: "Fix Python 3.10+ syntax for 3.9 compatibility"
files:
  - src: "files/aria_agents/context.py"
    dst: "aria_agents/context.py"
  - src: "files/aria_agents/base.py"
    dst: "aria_agents/base.py"
containers:
  - aria-api
  - aria-brain
verify:
  - "curl -sf http://localhost:8000/health"
  - "docker exec aria-api python -c 'from aria_agents.context import AgentContext'"
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ❌ | Infrastructure script |
| 2 | .env secrets | ✅ | Script must NOT read or log .env values |
| 3 | models.yaml SSOT | ❌ | No model changes |
| 4 | Docker-first | ✅ | Script restarts containers via docker compose |
| 5 | aria_memories writable | ✅ | Writes patch logs to aria_memories/logs/ |
| 6 | No soul modification | ❌ | Not touching soul |

## Dependencies
None — this is infrastructure.

## Verification
```bash
# 1. Script exists and is executable:
ls -la scripts/apply_patch.sh
# EXPECTED: -rwxr-xr-x

# 2. Create a test patch:
mkdir -p /tmp/test_patch/files
cat > /tmp/test_patch/manifest.yaml << 'EOF'
name: test-patch
description: Test the patch system
files: []
containers: []
verify:
  - "echo 'test passed'"
EOF

# 3. Run test patch:
./scripts/apply_patch.sh /tmp/test_patch
# EXPECTED: Patch applied successfully, logged to aria_memories/logs/

# 4. Check log:
ls aria_memories/logs/patch_*.log | tail -1
# EXPECTED: recent log file exists

# 5. Test rollback by creating a patch that fails verify:
cat > /tmp/bad_patch/manifest.yaml << 'EOF'
name: bad-patch
description: This should rollback
files: []
containers: []
verify:
  - "false"
EOF
./scripts/apply_patch.sh /tmp/bad_patch 2>&1
# EXPECTED: "Verification failed, rolling back..."
```

## Prompt for Agent
```
Create an automated patch application script with rollback support.

**Files to read:**
- scripts/ (list existing scripts for style reference)
- stacks/brain/docker-compose.yml (container names for restart commands)
- Makefile (existing automation patterns)

**Steps:**
1. Create scripts/apply_patch.sh with the following features:
   - Parse manifest.yaml from patch directory
   - Backup target files to rollback/ before overwriting
   - Apply file replacements atomically
   - Restart specified containers via docker compose
   - Run verification commands
   - Auto-rollback on verification failure
   - Log everything to aria_memories/logs/
2. Make it executable (chmod +x)
3. Create an example patch directory under patch/ as template
4. Test with a dry-run patch
5. Document usage in the script header
```
