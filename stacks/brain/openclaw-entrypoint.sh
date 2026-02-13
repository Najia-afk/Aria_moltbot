#!/bin/bash
set -e

echo "=== Aria/OpenClaw Entrypoint ==="

# ── OpenClaw version pinning ────────────────────────────────────────
# Pin to a known-good version to prevent random updates from breaking Aria.
# To upgrade: change OPENCLAW_VERSION in docker-compose.yml, then recreate.
# Fork backup: https://github.com/Najia-afk/openclaw (commit 9f703a4)
# Current pin: 2026.2.6-3 (frozen 2026-02-07)
OPENCLAW_PIN="${OPENCLAW_VERSION:-2026.2.6-3}"
echo "OpenClaw target version: $OPENCLAW_PIN"

# Clean up any stale lock files from previous runs (prevents lock issues after container restart)
echo "Cleaning up stale lock files..."
find /root/.openclaw/agents -name "*.lock" -type f 2>/dev/null | while read lock; do
    rm -f "$lock" && echo "  Removed stale lock: $lock"
done

# Install system dependencies
apt-get update && apt-get install -y curl git jq python3 python3-pip python3-venv

# Install OpenClaw at pinned version (skip if already correct version)
# Uses npm directly instead of install.sh to prevent pulling unexpected versions.
# If npm registry is ever unavailable, build from fork:
#   git clone https://github.com/Najia-afk/openclaw.git /tmp/oc && cd /tmp/oc
#   git checkout 9f703a44dc954349d4c9571cba2f16b7fb3d2adc
#   npm install -g pnpm && pnpm install && pnpm build && npm install -g .
INSTALLED_VERSION=$(openclaw --version 2>/dev/null || echo "none")
if [ "$INSTALLED_VERSION" = "$OPENCLAW_PIN" ]; then
    echo "OpenClaw $OPENCLAW_PIN already installed, skipping."
else
    echo "Installing OpenClaw $OPENCLAW_PIN (was: $INSTALLED_VERSION)..."
    npm install -g "openclaw@$OPENCLAW_PIN" --no-fund --no-audit 2>&1
    INSTALLED_VERSION=$(openclaw --version 2>/dev/null || echo "failed")
    if [ "$INSTALLED_VERSION" != "$OPENCLAW_PIN" ]; then
        echo "WARNING: npm install got $INSTALLED_VERSION instead of $OPENCLAW_PIN"
        echo "Attempting install from fork..."
        git clone --depth 1 https://github.com/Najia-afk/openclaw.git /tmp/openclaw-fork
        cd /tmp/openclaw-fork
        git fetch --depth 1 origin 9f703a44dc954349d4c9571cba2f16b7fb3d2adc
        git checkout 9f703a44dc954349d4c9571cba2f16b7fb3d2adc
        npm install -g pnpm
        pnpm install --frozen-lockfile
        pnpm build
        npm install -g .
        cd /root
        rm -rf /tmp/openclaw-fork
    fi
    echo "OpenClaw installed: $(openclaw --version 2>/dev/null)"
fi

# ── Fix: OpenClaw UI sends NaN for empty optional number fields ──────
# The Control UI form serialises empty number inputs as NaN via Number("").
# Zod's z.coerce.number().positive().optional() rejects NaN before
# applyModelDefaults() can fill in sensible values.
# Fix: append .catch(undefined) so NaN gracefully becomes undefined.
# Upstream bug: https://github.com/openclaw/openclaw  (ui/src/ui/views/config-form.node.ts renderNumberInput)
# Affects: config-*.js in dist/ (3 files, identical schema)
OC_DIST="/usr/local/lib/node_modules/openclaw/dist"
if [ -d "$OC_DIST" ]; then
    echo "Applying NaN-safe Zod fix to OpenClaw config schemas..."
    for f in "$OC_DIST"/config-*.js; do
        [ -f "$f" ] || continue
        # Handle both z.number() and z.coerce.number() variants (build output varies)
        # Order matters: longest match first to avoid double-replacement
        sed -i \
            -e 's/z\.coerce\.number()\.int()\.positive()\.optional()/z.coerce.number().int().positive().optional().catch(undefined)/g' \
            -e 's/z\.coerce\.number()\.positive()\.optional()/z.coerce.number().positive().optional().catch(undefined)/g' \
            -e 's/z\.coerce\.number()\.optional()/z.coerce.number().optional().catch(undefined)/g' \
            -e 's/z\.number()\.int()\.positive()\.optional()/z.number().int().positive().optional().catch(undefined)/g' \
            -e 's/z\.number()\.positive()\.optional()/z.number().positive().optional().catch(undefined)/g' \
            -e 's/z\.number()\.optional()/z.number().optional().catch(undefined)/g' \
            "$f"
    done
    echo "  NaN-safe fix applied to config-*.js"
fi

# Create directories
mkdir -p /root/.openclaw
mkdir -p /root/.openclaw/workspace/skills
mkdir -p /root/.openclaw/workspace/memory
mkdir -p /root/.openclaw/skills

# Create symlinks for OpenClaw skill manifests
# Skills are now consolidated under aria_skills/<skill>/ with skill.json inside
echo "Creating skill manifest symlinks..."
ARIA_SKILLS_DIR="/root/.openclaw/workspace/skills/aria_skills"
OPENCLAW_SKILLS_DIR="/root/.openclaw/skills"

# Clean up any existing aria-* skill directories to ensure fresh symlinks
echo "Cleaning up existing aria-* skill directories..."
rm -rf "$OPENCLAW_SKILLS_DIR"/aria-*

if [ -d "$ARIA_SKILLS_DIR" ]; then
    for skill_dir in "$ARIA_SKILLS_DIR"/*/; do
        if [ -d "$skill_dir" ]; then
            manifest="$skill_dir/skill.json"
            
            if [ -f "$manifest" ]; then
                # Extract skill name from skill.json (the authoritative source)
                skill_name=$(jq -r '.name' "$manifest" 2>/dev/null)
                
                if [ -n "$skill_name" ] && [ "$skill_name" != "null" ]; then
                    # Create directory matching the skill name from skill.json
                    target_dir="$OPENCLAW_SKILLS_DIR/$skill_name"
                    mkdir -p "$target_dir"
                    
                    # Create symlink to skill.json
                    ln -sf "$manifest" "$target_dir/skill.json"
                    echo "  Linked: $skill_name -> $manifest"
                    
                    # Also link SKILL.md if it exists
                    if [ -f "$skill_dir/SKILL.md" ]; then
                        ln -sf "$skill_dir/SKILL.md" "$target_dir/SKILL.md"
                    fi
                else
                    echo "  WARNING: Could not extract name from $manifest"
                fi
            fi
        fi
    done
    echo "Skill manifest symlinks created."
else
    echo "WARNING: aria_skills directory not found at $ARIA_SKILLS_DIR"
fi

# Install Python dependencies for Aria skills
echo "Installing Python dependencies for Aria skills..."
pip3 install --break-system-packages --quiet \
    asyncpg \
    aiohttp \
    pydantic \
    python-dateutil \
    httpx \
    pyyaml \
    tenacity \
    pytest \
    pytest-asyncio \
    pytest-cov \
    structlog \
    prometheus_client || echo "Warning: Some Python packages failed to install"

# Skill runner: use the MOUNTED file from aria_mind/skills/run_skill.py
# Do NOT generate an inline copy — it drifts from the real file and overwrites it.
if [ -f /root/.openclaw/workspace/skills/run_skill.py ]; then
    chmod +x /root/.openclaw/workspace/skills/run_skill.py
    echo "Skill runner found at /root/.openclaw/workspace/skills/run_skill.py"
    mkdir -p /root/.openclaw/workspace/aria_mind/skills
    ln -sf /root/.openclaw/workspace/skills/run_skill.py /root/.openclaw/workspace/aria_mind/skills/run_skill.py
    echo "Compatibility symlink: /root/.openclaw/workspace/aria_mind/skills/run_skill.py"
else
    echo "WARNING: run_skill.py not found — check aria_mind volume mount"
fi

# Read BOOTSTRAP.md for system prompt
BOOTSTRAP_FILE="/root/.openclaw/workspace/BOOTSTRAP.md"
DEFAULT_PROMPT="You are Aria, an intelligent autonomous assistant. You exist to help the user."

if [ -f "$BOOTSTRAP_FILE" ]; then
  echo "Found BOOTSTRAP.md, using as system prompt..."
  SYSTEM_PROMPT_JSON=$(cat "$BOOTSTRAP_FILE" | jq -Rs .)
else
  echo "BOOTSTRAP.md not found, using default prompt..."
  SYSTEM_PROMPT_JSON=$(echo "$DEFAULT_PROMPT" | jq -Rs .)
fi

# Generate openclaw.json from models.yaml (REQUIRED - no inline fallback)
OPENCLAW_CONFIG="/root/.openclaw/openclaw.json"
MODELS_CATALOG="/root/.openclaw/workspace/aria_models/models.yaml"
OPENCLAW_TEMPLATE="/root/.openclaw/openclaw-config-template.json"
AUTH_TEMPLATE="/root/.openclaw/auth-profiles-template.json"
AUTH_PROFILES="/root/.openclaw/auth-profiles.json"
OPENCLAW_RENDERER="/root/.openclaw/workspace/aria_models/openclaw_config.py"

echo "=== Generating openclaw.json from models.yaml ==="

# Validate required files exist
if [ ! -f "$OPENCLAW_TEMPLATE" ]; then
  echo "ERROR: Template not found: $OPENCLAW_TEMPLATE"
  echo "Mount openclaw-config.json as openclaw-config-template.json"
  exit 1
fi

if [ ! -f "$MODELS_CATALOG" ]; then
  echo "ERROR: Models catalog not found: $MODELS_CATALOG"
  echo "Mount aria_models/ directory"
  exit 1
fi

if [ ! -f "$OPENCLAW_RENDERER" ]; then
  echo "ERROR: Renderer not found: $OPENCLAW_RENDERER"
  exit 1
fi

# Generate config from YAML - fail if this doesn't work
echo "Rendering: $OPENCLAW_RENDERER"
echo "  Template: $OPENCLAW_TEMPLATE"
echo "  Models:   $MODELS_CATALOG"
echo "  Output:   $OPENCLAW_CONFIG"

if ! python3 "$OPENCLAW_RENDERER" --template "$OPENCLAW_TEMPLATE" --models "$MODELS_CATALOG" --output "$OPENCLAW_CONFIG"; then
  echo "ERROR: Failed to render openclaw.json from models.yaml"
  echo "Fix the renderer or models.yaml and restart"
  exit 1
fi

# Inject gateway token from environment variable
if [ -n "$OPENCLAW_GATEWAY_TOKEN" ]; then
  echo "=== Injecting gateway token from OPENCLAW_GATEWAY_TOKEN ==="
  jq --arg token "$OPENCLAW_GATEWAY_TOKEN" '.gateway.auth.token = $token' "$OPENCLAW_CONFIG" > "${OPENCLAW_CONFIG}.tmp" && mv "${OPENCLAW_CONFIG}.tmp" "$OPENCLAW_CONFIG"
fi

# Inject LiteLLM master key into provider config
if [ -n "$LITELLM_MASTER_KEY" ]; then
  echo "=== Injecting LiteLLM API key from LITELLM_MASTER_KEY ==="
  jq --arg key "$LITELLM_MASTER_KEY" '.models.providers.litellm.apiKey = $key' "$OPENCLAW_CONFIG" > "${OPENCLAW_CONFIG}.tmp" && mv "${OPENCLAW_CONFIG}.tmp" "$OPENCLAW_CONFIG"
fi

# Generate auth profiles from template and inject LiteLLM API key
if [ -f "$AUTH_TEMPLATE" ]; then
    echo "=== Rendering auth-profiles.json from template ==="
    cp "$AUTH_TEMPLATE" "$AUTH_PROFILES"
    if [ -n "$LITELLM_MASTER_KEY" ]; then
        jq --arg key "$LITELLM_MASTER_KEY" '
            if .profiles then
                .profiles = (
                    .profiles
                    | with_entries(
                            .value.apiKey = (
                                if (.value.apiKey | type) == "string" and (.value.apiKey | startswith("${"))
                                then $key
                                else .value.apiKey
                                end
                            )
                        )
                )
            else . end
        ' "$AUTH_PROFILES" > "${AUTH_PROFILES}.tmp" && mv "${AUTH_PROFILES}.tmp" "$AUTH_PROFILES"
    fi
fi

# SECURITY: Remove any direct OpenRouter/cloud provider access from OpenClaw config.
# All model routing MUST go through LiteLLM — OpenClaw should never talk to OpenRouter directly.
echo "=== Stripping non-litellm providers from openclaw.json ==="
jq 'if .models.providers then .models.providers = {litellm: .models.providers.litellm} else . end' "$OPENCLAW_CONFIG" > "${OPENCLAW_CONFIG}.tmp" && mv "${OPENCLAW_CONFIG}.tmp" "$OPENCLAW_CONFIG"

# Also remove any stale auth profiles that reference direct cloud providers
if [ -f "$AUTH_PROFILES" ]; then
  echo "=== Cleaning auth-profiles: keeping only litellm profiles ==="
  jq '{profiles: (.profiles // {} | with_entries(select(.key | test("litellm"))))}' "$AUTH_PROFILES" > "${AUTH_PROFILES}.tmp" && mv "${AUTH_PROFILES}.tmp" "$AUTH_PROFILES"
fi

# Inject remote browser profile pointing to aria-browser container (browserless/chrome)
if [ -n "$BROWSER_CDP_URL" ]; then
  echo "=== Injecting remote browser profile (sandbox -> $BROWSER_CDP_URL) ==="
  jq --arg url "$BROWSER_CDP_URL" '.browser += {"defaultProfile": "sandbox", "profiles": {"sandbox": {"cdpUrl": $url, "color": "#1E90FF"}}}' "$OPENCLAW_CONFIG" > "${OPENCLAW_CONFIG}.tmp" && mv "${OPENCLAW_CONFIG}.tmp" "$OPENCLAW_CONFIG"
fi

echo "=== Generated openclaw.json ==="
jq '
    if .models and .models.providers and .models.providers.litellm then
        .models.providers.litellm.apiKey = "***REDACTED***"
    else . end
    | if .gateway and .gateway.auth then
            .gateway.auth.token = "***REDACTED***"
        else . end
' "$OPENCLAW_CONFIG"

if [ -f "$AUTH_PROFILES" ]; then
    echo "=== Generated auth-profiles.json ==="
    jq '
        if .profiles then
            .profiles = (
                .profiles
                | with_entries(
                        .value.apiKey = "***REDACTED***"
                    )
            )
        else . end
    ' "$AUTH_PROFILES"
fi

# Check if this is first boot (awakening)
FIRST_BOOT_MARKER="/root/.openclaw/.awakened"
NEEDS_AWAKENING_MARKER="/root/.openclaw/.needs_awakening"

# Function to inject cron jobs from YAML definition
inject_cron_jobs() {
    CRON_YAML="/root/.openclaw/workspace/cron_jobs.yaml"
    CRON_MARKER="/root/.openclaw/.cron_injected"
    
    if [ ! -f "$CRON_YAML" ]; then
        echo "No cron_jobs.yaml found, skipping cron injection"
        return
    fi
    
    # Always re-inject cron jobs (idempotent - openclaw handles duplicates by name)
    echo "=== Injecting Cron Jobs from cron_jobs.yaml ==="
    
    # Parse YAML and create jobs using Python (jq can't parse YAML)
    python3 << 'PYINJECT'
import json
import yaml
import subprocess
import os

cron_yaml = "/root/.openclaw/workspace/cron_jobs.yaml"

with open(cron_yaml) as f:
    data = yaml.safe_load(f)


def _list_jobs_json():
    result = subprocess.run(['openclaw', 'cron', 'list', '--json'], capture_output=True, text=True)
    if result.returncode != 0:
        return None, (result.stderr or result.stdout or '').strip()
    try:
        payload = json.loads(result.stdout or '{}')
        jobs = payload.get('jobs', []) if isinstance(payload, dict) else []
        if not isinstance(jobs, list):
            jobs = []
        return jobs, ''
    except Exception as exc:
        return None, f'json-parse-error: {exc}'


def _job_rank(job):
    return int(job.get('updatedAtMs') or job.get('createdAtMs') or 0)

for job in data.get('jobs', []):
    name = job['name']
    enabled = job.get('enabled', True)
    # OpenClaw 2026.2.6+ uses --message (not --text)
    text = job.get('text') or job.get('message', '')
    agent = job.get('agent', 'main')
    session = job.get('session', 'isolated')
    delivery = job.get('delivery', 'none')
    
    # Check exact-name existence via JSON list (and self-heal duplicate names if present)
    listed_jobs, list_err = _list_jobs_json()
    if listed_jobs is None:
        print(f"  SKIP {name}: unable to list cron jobs safely ({list_err})")
        continue

    same_name = [j for j in listed_jobs if j.get('name') == name]
    if same_name and len(same_name) > 1:
        keep = max(same_name, key=_job_rank)
        keep_id = keep.get('id')
        for dup in same_name:
            dup_id = dup.get('id')
            if not dup_id or dup_id == keep_id:
                continue
            rm = subprocess.run(['openclaw', 'cron', 'rm', dup_id], capture_output=True, text=True)
            if rm.returncode == 0:
                print(f"  Removed duplicate cron job '{name}' id={dup_id}")
            else:
                print(f"  WARN failed to remove duplicate '{name}' id={dup_id}: {(rm.stderr or rm.stdout).strip()}")

    if not enabled:
        if same_name:
            for existing in same_name:
                existing_id = existing.get('id')
                if not existing_id:
                    continue
                rm = subprocess.run(['openclaw', 'cron', 'rm', existing_id], capture_output=True, text=True)
                if rm.returncode == 0:
                    print(f"  Removed disabled cron job: {name} (id={existing_id})")
                else:
                    print(f"  WARN failed to remove disabled cron '{name}' id={existing_id}: {(rm.stderr or rm.stdout).strip()}")
        else:
            print(f"  Cron job '{name}' disabled in YAML, skipping")
        continue

    # Build command - use --message for 2026.2.6+ CLI
    cmd = ['openclaw', 'cron', 'add', '--name', name]
    
    if 'every' in job:
        cmd.extend(['--every', job['every']])
    elif 'cron' in job:
        cmd.extend(['--cron', job['cron']])
    
    cmd.extend(['--message', text, '--agent', agent, '--session', session])
    
    # Add delivery mode: --announce flag (2026.2.6+ replaces --delivery)
    if delivery == 'announce':
        cmd.append('--announce')
    elif delivery in ('none', 'silent', 'chat'):
        cmd.append('--no-deliver')
    
    # Best-effort: don't fail job if delivery target is missing (isolated sessions)
    if job.get('best_effort_deliver'):
        cmd.append('--best-effort-deliver')
    
    if same_name:
        print(f"  Cron job '{name}' already exists, skipping")
        continue
    
    # Create job
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  Created cron job: {name}")
    else:
        print(f"  FAILED {name}: rc={result.returncode} err={result.stderr.strip()}")
        # If add returned non-zero but job now exists, do NOT fallback-add again.
        listed_after_fail, _ = _list_jobs_json()
        if listed_after_fail is not None and any(j.get('name') == name for j in listed_after_fail):
            print(f"  Job '{name}' appears present after failed add; skipping fallback")
            continue
        # Fallback: try without --announce for minimal compatibility
        cmd_fallback = [c for c in cmd if c not in ('--announce', '--no-deliver')]
        result2 = subprocess.run(cmd_fallback, capture_output=True, text=True)
        if result2.returncode == 0:
            print(f"  Created cron job (fallback): {name}")
        else:
            print(f"  FAILED to create {name}: {result2.stderr.strip()}")
PYINJECT
    
    touch "$CRON_MARKER"
    echo "=== Cron job injection complete ==="
}

# Function to prepare awakening (don't send via CLI - causes lock issues)
prepare_awakening() {
    sleep 5  # Brief wait for filesystem
    
    if [ ! -f "$FIRST_BOOT_MARKER" ]; then
        echo "=== FIRST BOOT DETECTED ==="
        echo "Creating awakening marker for Aria to process..."
        
        # Create marker that tells Aria she needs to awaken
        echo "$(date -Iseconds)" > "$NEEDS_AWAKENING_MARKER"
        
        # Also copy AWAKENING.md content to a prompt file the hook can read
        if [ -f "/root/.openclaw/workspace/AWAKENING.md" ]; then
            cp /root/.openclaw/workspace/AWAKENING.md /root/.openclaw/BOOT_PROMPT.md
            echo "Boot prompt prepared at /root/.openclaw/BOOT_PROMPT.md"
        fi
        
        # Mark as awakened (Aria will see the markers)
        touch "$FIRST_BOOT_MARKER"
        echo "=== Aria awakening prepared - she will process on first interaction ==="
    else
        echo "=== Aria already awakened (marker exists) ==="
    fi
}

# Run awakening preparation in background
prepare_awakening &

# Run cron job injection in background (needs gateway to be up)
(sleep 10 && inject_cron_jobs) &

# Background maintenance loop - cleans stale locks every 5 minutes
(
    while true; do
        sleep 300  # 5 minutes
        # Clean lock files older than 2 minutes
        find /root/.openclaw/agents -name "*.lock" -type f -mmin +2 2>/dev/null | while read lock; do
            rm -f "$lock" && echo "[$(date '+%Y-%m-%d %H:%M:%S')] Maintenance: removed stale lock $lock"
        done
    done
) &

# Auto-fix any unrecognized config keys (e.g. stale systemPrompt)
echo "=== Running openclaw doctor --fix to clean config ==="
openclaw doctor --fix 2>/dev/null || true

# Start the gateway
exec /usr/local/bin/openclaw gateway run \
    --port 18789 \
    --bind lan \
    --token "${OPENCLAW_GATEWAY_TOKEN}" \
    --allow-unconfigured \
    --verbose
