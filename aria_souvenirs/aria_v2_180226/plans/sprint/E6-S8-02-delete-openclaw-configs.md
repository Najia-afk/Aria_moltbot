# S8-02: Delete OpenClaw Config Files
**Epic:** E6 — OpenClaw Removal | **Priority:** P0 | **Points:** 1 | **Phase:** 8

## Problem
Three OpenClaw-specific config files remain in `stacks/brain/` after the clawdbot service is removed. These files are dead artifacts that confuse future maintainers.

## Root Cause
These files were created to configure the OpenClaw Node.js gateway. With clawdbot removed from docker-compose, they serve no purpose.

## Fix

### 1. Delete these files from `stacks/brain/`:

```bash
# Files to delete:
rm stacks/brain/openclaw-config.json
rm stacks/brain/openclaw-entrypoint.sh
rm stacks/brain/openclaw-auth-profiles.json
```

### 2. File inventory (for reference):

**`stacks/brain/openclaw-config.json`** — OpenClaw gateway configuration template. Contains model definitions, gateway port, workspace paths. Mounted as `/root/.openclaw/openclaw-config-template.json`. The entrypoint script rendered it with environment variable substitution.

**`stacks/brain/openclaw-entrypoint.sh`** — Bash entrypoint for the clawdbot container. Downloads a specific OpenClaw version, renders config templates, sets up workspace symlinks, and starts the Node.js gateway process.

**`stacks/brain/openclaw-auth-profiles.json`** — Authentication profiles for OpenClaw's multi-model routing. Defined API keys and endpoints for Ollama, LiteLLM, OpenRouter, and Moonshot.

### 3. Clean stray OpenClaw path references in config:

**`aria_mind/config/research_websites/sources.yaml`** (line 100):
```yaml
# BEFORE:
  storage_path: "/root/.openclaw/aria_memories/research/"

# AFTER:
  storage_path: "/app/aria_memories/research/"
```

### 4. Grep validation script:

```bash
#!/bin/bash
# scripts/verify_openclaw_configs_removed.sh

echo "=== Checking for stale OpenClaw config files ==="

files_to_check=(
    "stacks/brain/openclaw-config.json"
    "stacks/brain/openclaw-entrypoint.sh"
    "stacks/brain/openclaw-auth-profiles.json"
)

all_clean=true
for f in "${files_to_check[@]}"; do
    if [ -f "$f" ]; then
        echo "FAIL: $f still exists"
        all_clean=false
    else
        echo "OK:   $f removed"
    fi
done

echo ""
echo "=== Checking for .openclaw path references ==="
refs=$(grep -rn "\.openclaw" aria_mind/ aria_models/ src/ stacks/ --include="*.yaml" --include="*.yml" --include="*.py" --include="*.json" --include="*.sh" 2>/dev/null | grep -v node_modules | grep -v __pycache__)

if [ -z "$refs" ]; then
    echo "OK: No .openclaw path references found"
else
    echo "WARN: Found .openclaw references:"
    echo "$refs"
    all_clean=false
fi

if $all_clean; then
    echo ""
    echo "✅ All OpenClaw config files cleaned"
else
    echo ""
    echo "⚠️  Some cleanup remaining"
fi
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ❌ | File deletion only |
| 2 | .env for secrets (zero in code) | ❌ | No secrets in these files |
| 3 | models.yaml single source of truth | ✅ | models.yaml replaces openclaw-config.json model defs |
| 4 | Docker-first testing | ✅ | Verify docker compose config still valid |
| 5 | aria_memories only writable path | ❌ | N/A |
| 6 | No soul modification | ❌ | N/A |

## Dependencies
- S8-01 (Remove clawdbot service — these files are no longer mounted)

## Verification
```bash
# 1. Files deleted:
test ! -f stacks/brain/openclaw-config.json && echo "PASS" || echo "FAIL"
test ! -f stacks/brain/openclaw-entrypoint.sh && echo "PASS" || echo "FAIL"
test ! -f stacks/brain/openclaw-auth-profiles.json && echo "PASS" || echo "FAIL"
# EXPECTED: PASS PASS PASS

# 2. No .openclaw path references remain:
grep -rn "\.openclaw" aria_mind/ src/ stacks/ --include="*.yaml" --include="*.yml" --include="*.py" | grep -v __pycache__ | wc -l
# EXPECTED: 0

# 3. Docker compose still valid:
cd stacks/brain && docker compose config > /dev/null && echo "VALID"
# EXPECTED: VALID
```

## Prompt for Agent
```
Delete the three OpenClaw config files and clean stray path references.

FILES TO READ FIRST:
- stacks/brain/openclaw-config.json (to verify it's the right file, then delete)
- stacks/brain/openclaw-entrypoint.sh (to verify, then delete)
- stacks/brain/openclaw-auth-profiles.json (to verify, then delete)
- aria_mind/config/research_websites/sources.yaml (has .openclaw path to fix)

STEPS:
1. Delete stacks/brain/openclaw-config.json
2. Delete stacks/brain/openclaw-entrypoint.sh
3. Delete stacks/brain/openclaw-auth-profiles.json
4. Fix storage_path in sources.yaml: /root/.openclaw/aria_memories/research/ → /app/aria_memories/research/
5. Run: grep -rn ".openclaw" aria_mind/ src/ stacks/ to find any remaining references
6. Fix any remaining .openclaw path references

SAFETY:
- These files were only mounted into the clawdbot container (removed in S8-01)
- No other service references them
- Git history preserves the files if ever needed
```
