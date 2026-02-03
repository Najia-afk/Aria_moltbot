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
    'health': ('aria_skills.health', 'HealthSkill', lambda: {}),
    'llm': ('aria_skills.llm', 'LLMSkill', lambda: {
        'ollama_url': os.environ.get('OLLAMA_URL'),
        'model': os.environ.get('OLLAMA_MODEL', 'hf.co/unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF:Q3_K_S')
    }),
    'knowledge_graph': ('aria_skills.knowledge_graph', 'KnowledgeGraphSkill', lambda: {'dsn': os.environ.get('DATABASE_URL')}),
    'goals': ('aria_skills.goals', 'GoalSkill', lambda: {'dsn': os.environ.get('DATABASE_URL')}),
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
    'hourly_goals': ('aria_skills.hourly_goals', 'HourlyGoalSkill', lambda: {'dsn': os.environ.get('DATABASE_URL')}),
    'litellm': ('aria_skills.litellm_skill', 'LiteLLMSkill', lambda: {
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
        
        # Convert SkillResult to dict if needed
        if hasattr(result, '__dict__'):
            return {'success': result.success, 'data': result.data, 'error': result.error}
        return result
        
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

# Generate openclaw.json with LiteLLM provider config, skill definitions, and Aria identity
cat > /root/.openclaw/openclaw.json << EOF
{
  "commands": {
    "native": "auto",
    "nativeSkills": "auto"
  },
  "skills": {
    "load": {
      "extraDirs": ["/root/.openclaw/skills"]
    },
    "entries": {
      "aria-database": { "enabled": true },
      "aria-moltbook": { "enabled": true },
      "aria-goals": { "enabled": true },
      "aria-health": { "enabled": true },
      "aria-pytest": { "enabled": true },
      "aria-model-switcher": { "enabled": true },
      "aria-performance": { "enabled": true },
      "aria-social": { "enabled": true },
      "aria-hourly-goals": { "enabled": true },
      "aria-litellm": { "enabled": true },
      "aria-schedule": { "enabled": true },
      "aria-security-scan": { "enabled": true },
      "aria-ci-cd": { "enabled": true },
      "aria-data-pipeline": { "enabled": true },
      "aria-experiment": { "enabled": true },
      "aria-market-data": { "enabled": true },
      "aria-portfolio": { "enabled": true },
      "aria-brainstorm": { "enabled": true },
      "aria-research": { "enabled": true },
      "aria-fact-check": { "enabled": true },
      "aria-community": { "enabled": true }
    }
  },
  "gateway": {
    "port": 18789,
    "mode": "local",
    "bind": "lan",
    "trustedProxies": ["0.0.0.0/0", "::/0"],
    "controlUi": {
      "basePath": "/clawdbot",
      "allowInsecureAuth": true,
      "dangerouslyDisableDeviceAuth": true
    }
  },
  "ui": {
    "seamColor": "#3B82F6",
    "assistant": {
      "name": "Aria",
      "avatar": "⚡"
    }
  },
  "hooks": {
    "internal": {
      "enabled": true,
      "entries": {
        "soul-evil": {
          "enabled": true
        }
      }
    }
  },
  "agents": {
    "defaults": {
      "maxConcurrent": 4,
      "workspace": "/root/.openclaw/workspace",
      "model": {
        "primary": "litellm/qwen3-mlx",
        "fallbacks": ["litellm/trinity-free", "litellm/chimera-free", "litellm/kimi"]
      },
      "models": {
        "litellm/qwen3-mlx": { "alias": "Qwen3 VLTO (MLX Local)" },
        "litellm/trinity-free": { "alias": "Trinity 400B (OpenRouter FREE)" },
        "litellm/chimera-free": { "alias": "Chimera 671B (OpenRouter FREE)" },
        "litellm/qwen3-coder-free": { "alias": "Qwen3 Coder 480B (OpenRouter FREE)" },
        "litellm/glm-free": { "alias": "GLM 4.5 Air (OpenRouter FREE)" },
        "litellm/deepseek-free": { "alias": "DeepSeek R1 (OpenRouter FREE)" },
        "litellm/kimi": { "alias": "Kimi K2.5 (Moonshot Paid)" }
      },
      "subagents": {
        "maxConcurrent": 8
      },
      "heartbeat": {
        "every": "30m",
        "target": "last",
        "prompt": "Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not infer or repeat old tasks from prior chats. If nothing needs attention, reply HEARTBEAT_OK."
      },
      "memorySearch": {
        "enabled": false,
        "fallback": "none"
      }
    },
    "list": [
      {
        "id": "main",
        "default": true,
        "identity": {
          "name": "Aria",
          "theme": "intelligent autonomous assistant with electric blue energy",
          "emoji": "⚡",
          "avatar": "⚡"
        }
      }
    ]
  },
  "tools": {
    "exec": {
      "backgroundMs": 10000,
      "timeoutSec": 1800,
      "cleanupMs": 1800000,
      "notifyOnExit": true
    }
  },
  "models": {
    "mode": "merge",
    "providers": {
      "litellm": {
        "baseUrl": "http://litellm:4000/v1",
        "apiKey": "sk-aria-local-key",
        "api": "openai-completions",
        "models": [
          {
            "id": "qwen3-mlx",
            "name": "Qwen3 VLTO 8B (MLX Local)",
            "reasoning": false,
            "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 32768,
            "maxTokens": 8192
          },
          {
            "id": "trinity-free",
            "name": "Trinity 400B MoE (OpenRouter FREE)",
            "reasoning": true,
            "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 131072,
            "maxTokens": 8192
          },
          {
            "id": "chimera-free",
            "name": "Chimera 671B (OpenRouter FREE)",
            "reasoning": true,
            "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 164000,
            "maxTokens": 8192
          },
          {
            "id": "qwen3-coder-free",
            "name": "Qwen3 Coder 480B (OpenRouter FREE)",
            "reasoning": true,
            "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 131072,
            "maxTokens": 8192
          },
          {
            "id": "glm-free",
            "name": "GLM 4.5 Air (OpenRouter FREE)",
            "reasoning": true,
            "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 131072,
            "maxTokens": 8192
          },
          {
            "id": "deepseek-free",
            "name": "DeepSeek R1 (OpenRouter FREE)",
            "reasoning": true,
            "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 164000,
            "maxTokens": 8192
          },
          {
            "id": "kimi",
            "name": "Kimi K2.5 (Moonshot Paid)",
            "reasoning": true,
            "input": ["text"],
            "cost": { "input": 0.001, "output": 0.002, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 256000,
            "maxTokens": 16384
          }
        ]
      }
    }
  },
  "messages": {
    "ackReaction": "⚡",
    "ackReactionScope": "group-mentions",
    "responsePrefix": "[Aria]"
  }
}
EOF

echo "OpenClaw config created with DIRECT Ollama provider (no LiteLLM)"
cat /root/.openclaw/openclaw.json

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
