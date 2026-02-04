#!/bin/bash
set -e

echo "=== Aria/OpenClaw Entrypoint ==="

# Install system dependencies
apt-get update && apt-get install -y curl jq python3 python3-pip python3-venv

# Install OpenClaw if not present
if [ ! -e /usr/local/bin/openclaw ]; then
    echo "Installing OpenClaw..."
    curl -fsSL https://openclaw.ai/install.sh | bash -s -- --no-onboard --no-prompt
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
  tenacity \
  pytest \
  pytest-asyncio \
  pytest-cov || echo "Warning: Some Python packages failed to install"

# Apply OpenClaw patch if present (idempotent)
# PATCH_MARKER_DIR="/root/.openclaw/.patches"
# PATCH_MARKER="$PATCH_MARKER_DIR/openclaw-litellm-fix"
# PATCH_SCRIPT="/root/.openclaw/patches/openclaw_patch.js"
# if [ -f "$PATCH_SCRIPT" ]; then
#   mkdir -p "$PATCH_MARKER_DIR"
#   if [ ! -f "$PATCH_MARKER" ]; then
#     echo "Applying OpenClaw patch..."
#     node "$PATCH_SCRIPT" && touch "$PATCH_MARKER"
#   else
#     echo "OpenClaw patch already applied"
#   fi
# fi

# Create a Python skill runner script with DYNAMIC skill loading
cat > /root/.openclaw/workspace/skills/run_skill.py << 'PYEOF'
#!/usr/bin/env python3
"""
Aria Skill Runner - Execute Python skills from OpenClaw exec tool.

Usage:
    python3 run_skill.py <skill_name> <function_name> [args_json]
    
Example:
    python3 run_skill.py database query '{"sql": "SELECT * FROM activity_log LIMIT 5"}'
    python3 run_skill.py security_scan scan_code '{"code": "import os; os.system(cmd)"}'
    python3 run_skill.py market_data get_price '{"symbol": "BTC"}'
"""
import sys
import os
import json
import asyncio

# Add skill modules to path
sys.path.insert(0, '/root/.openclaw/workspace/skills')
sys.path.insert(0, '/root/.openclaw/workspace')

# Dynamic skill registry - maps skill_name to (module_name, class_name, config_factory)
SKILL_REGISTRY = {
    # === Core Skills (v1.0) ===
    'database': ('aria_skills.database', 'DatabaseSkill', lambda: {'dsn': os.environ.get('DATABASE_URL')}),
    'moltbook': ('aria_skills.moltbook', 'MoltbookSkill', lambda: {
        'api_url': os.environ.get('MOLTBOOK_API_URL', 'https://moltbook.com/api'),
        'auth': os.environ.get('MOLTBOOK_API_KEY') or os.environ.get('MOLTBOOK_TOKEN')
    }),
    'health': ('aria_skills.health', 'HealthMonitorSkill', lambda: {}),
    'llm': ('aria_skills.llm', 'BaseLLMSkill', lambda: {
        'ollama_url': os.environ.get('OLLAMA_URL'),
        'model': os.environ.get('OLLAMA_MODEL', 'hf.co/unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF:Q3_K_S')
    }),
    'knowledge_graph': ('aria_skills.knowledge_graph', 'KnowledgeGraphSkill', lambda: {'dsn': os.environ.get('DATABASE_URL')}),
    'goals': ('aria_skills.goals', 'GoalSchedulerSkill', lambda: {'dsn': os.environ.get('DATABASE_URL')}),
    'pytest': ('aria_skills.pytest_runner', 'PytestSkill', lambda: {
        'workspace': os.environ.get('PYTEST_WORKSPACE', '/root/.openclaw/workspace'),
        'timeout_sec': int(os.environ.get('PYTEST_TIMEOUT_SEC', '600')),
        'default_args': os.environ.get('PYTEST_DEFAULT_ARGS', '-q')
    }),
    'model_switcher': ('aria_skills.model_switcher', 'ModelSwitcherSkill', lambda: {
        'url': os.environ.get('OLLAMA_URL', 'http://host.docker.internal:11434')
    }),
    
    # === Social & Communication Skills (v1.1) ===
    'performance': ('aria_skills.performance', 'PerformanceSkill', lambda: {
        'dsn': os.environ.get('DATABASE_URL'),
        'litellm_url': os.environ.get('LITELLM_URL', 'http://litellm:4000')
    }),
    'social': ('aria_skills.social', 'SocialSkill', lambda: {
        'telegram_token': os.environ.get('TELEGRAM_TOKEN'),
        'telegram_chat_id': os.environ.get('TELEGRAM_CHAT_ID')
    }),
    'hourly_goals': ('aria_skills.hourly_goals', 'HourlyGoalsSkill', lambda: {'dsn': os.environ.get('DATABASE_URL')}),
    'litellm': ('aria_skills.litellm', 'LiteLLMSkill', lambda: {
        'litellm_url': os.environ.get('LITELLM_URL', 'http://litellm:4000'),
        'api_key': os.environ.get('LITELLM_API_KEY', 'sk-aria')
    }),
    'schedule': ('aria_skills.schedule', 'ScheduleSkill', lambda: {'dsn': os.environ.get('DATABASE_URL')}),
    
    # === DevSecOps Skills (v1.2) ===
    'security_scan': ('aria_skills.security_scan', 'SecurityScanSkill', lambda: {
        'dsn': os.environ.get('DATABASE_URL'),
        'secret_patterns_file': os.environ.get('SECRET_PATTERNS_FILE')
    }),
    'ci_cd': ('aria_skills.ci_cd', 'CICDSkill', lambda: {
        'github_token': os.environ.get('GITHUB_TOKEN'),
        'default_registry': os.environ.get('DOCKER_REGISTRY', 'ghcr.io')
    }),
    
    # === Data & ML Skills (v1.2) ===
    'data_pipeline': ('aria_skills.data_pipeline', 'DataPipelineSkill', lambda: {
        'dsn': os.environ.get('DATABASE_URL'),
        'storage_path': os.environ.get('DATA_STORAGE_PATH', '/tmp/aria_data')
    }),
    'experiment': ('aria_skills.experiment', 'ExperimentSkill', lambda: {
        'dsn': os.environ.get('DATABASE_URL'),
        'mlflow_url': os.environ.get('MLFLOW_URL'),
        'artifacts_path': os.environ.get('ARTIFACTS_PATH', '/tmp/aria_experiments')
    }),
    
    # === Crypto Trading Skills (v1.2) ===
    'market_data': ('aria_skills.market_data', 'MarketDataSkill', lambda: {
        'coingecko_api_key': os.environ.get('COINGECKO_API_KEY'),
        'cache_ttl': int(os.environ.get('MARKET_CACHE_TTL', '60'))
    }),
    'portfolio': ('aria_skills.portfolio', 'PortfolioSkill', lambda: {
        'dsn': os.environ.get('DATABASE_URL'),
        'coingecko_api_key': os.environ.get('COINGECKO_API_KEY')
    }),
    
    # === Creative Skills (v1.2) ===
    'brainstorm': ('aria_skills.brainstorm', 'BrainstormSkill', lambda: {
        'dsn': os.environ.get('DATABASE_URL'),
        'llm_url': os.environ.get('OLLAMA_URL')
    }),
    
    # === Journalist Skills (v1.2) ===
    'research': ('aria_skills.research', 'ResearchSkill', lambda: {
        'dsn': os.environ.get('DATABASE_URL'),
        'search_api_key': os.environ.get('SEARCH_API_KEY')
    }),
    'fact_check': ('aria_skills.fact_check', 'FactCheckSkill', lambda: {
        'dsn': os.environ.get('DATABASE_URL'),
        'llm_url': os.environ.get('OLLAMA_URL')
    }),
    
    # === Community Skills (v1.2) ===
    'community': ('aria_skills.community', 'CommunitySkill', lambda: {
        'dsn': os.environ.get('DATABASE_URL'),
        'platform_tokens': {
            'telegram': os.environ.get('TELEGRAM_TOKEN'),
            'discord': os.environ.get('DISCORD_TOKEN'),
            'moltbook': os.environ.get('MOLTBOOK_TOKEN')
        }
    }),
    
    # === API Client Skill (v1.2) ===
    'api_client': ('aria_skills.api_client', 'AriaAPIClient', lambda: {
        'api_url': os.environ.get('ARIA_API_URL', 'http://aria-api:8000/api'),
        'timeout': int(os.environ.get('ARIA_API_TIMEOUT', '30'))
    }),
    
    # === Security Skills (v1.3) ===
    'input_guard': ('aria_skills.input_guard', 'InputGuardSkill', lambda: {
        'block_threshold': os.environ.get('ARIA_SECURITY_BLOCK_THRESHOLD', 'high'),
        'enable_logging': os.environ.get('ARIA_SECURITY_LOGGING', 'true').lower() == 'true',
        'rate_limit_rpm': int(os.environ.get('ARIA_RATE_LIMIT_RPM', '60'))
    }),
}

async def run_skill(skill_name: str, function_name: str, args: dict):
    """Run a skill function with the given arguments."""
    try:
        if skill_name not in SKILL_REGISTRY:
            available = ', '.join(sorted(SKILL_REGISTRY.keys()))
            return {'error': f'Unknown skill: {skill_name}. Available: {available}'}
        
        module_name, class_name, config_factory = SKILL_REGISTRY[skill_name]
        
        # Dynamic import
        import importlib
        module = importlib.import_module(module_name)
        skill_class = getattr(module, class_name)
        
        # Import SkillConfig
        from aria_skills.base import SkillConfig
        
        # Create and initialize skill
        config = SkillConfig(name=skill_name, config=config_factory())
        skill = skill_class(config)
        await skill.initialize()
        
        # Get the function and call it
        func = getattr(skill, function_name, None)
        if func is None:
            methods = [m for m in dir(skill) if not m.startswith('_') and callable(getattr(skill, m))]
            return {'error': f'Unknown function: {function_name} in skill {skill_name}. Available: {methods}'}
        
        if asyncio.iscoroutinefunction(func):
            result = await func(**args)
        else:
            result = func(**args)
        
        # Convert result to dict
        if hasattr(result, 'success') and hasattr(result, 'data'):
            # SkillResult object
            return {'success': result.success, 'data': result.data, 'error': result.error}
        elif hasattr(result, 'value'):
            # Enum (like SkillStatus)
            return {'success': True, 'data': result.value, 'error': None}
        elif isinstance(result, dict):
            return result
        else:
            return {'success': True, 'data': str(result), 'error': None}
        
    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(json.dumps({
            'error': 'Usage: run_skill.py <skill_name> <function_name> [args_json]',
            'available_skills': sorted(SKILL_REGISTRY.keys())
        }))
        sys.exit(1)
    
    skill_name = sys.argv[1]
    function_name = sys.argv[2]
    args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    
    result = asyncio.run(run_skill(skill_name, function_name, args))
    print(json.dumps(result, default=str))
PYEOF

chmod +x /root/.openclaw/workspace/skills/run_skill.py

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

echo "=== Generated openclaw.json ==="
cat "$OPENCLAW_CONFIG"

# Check if this is first boot (awakening)
FIRST_BOOT_MARKER="/root/.openclaw/.awakened"
NEEDS_AWAKENING_MARKER="/root/.openclaw/.needs_awakening"

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

# Start the gateway
exec /usr/local/bin/openclaw gateway run \
    --port 18789 \
    --bind lan \
    --token "${OPENCLAW_GATEWAY_TOKEN}" \
    --allow-unconfigured \
    --verbose
