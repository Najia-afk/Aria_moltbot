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

# Create a Python skill runner script
cat > /root/.openclaw/workspace/skills/run_skill.py << 'PYEOF'
#!/usr/bin/env python3
"""
Aria Skill Runner - Execute Python skills from OpenClaw exec tool.

Usage:
    python3 run_skill.py <skill_name> <function_name> [args_json]
    
Example:
    python3 run_skill.py database query '{"sql": "SELECT * FROM activity_log LIMIT 5"}'
"""
import sys
import os
import json
import asyncio

# Add skill modules to path
sys.path.insert(0, '/root/.openclaw/workspace/skills')
sys.path.insert(0, '/root/.openclaw/workspace')

async def run_skill(skill_name: str, function_name: str, args: dict):
    """Run a skill function with the given arguments."""
    try:
        if skill_name == 'database':
            from aria_skills.database import DatabaseSkill
            from aria_skills.base import SkillConfig
            config = SkillConfig(name='database', config={'dsn': os.environ.get('DATABASE_URL')})
            skill = DatabaseSkill(config)
            await skill.initialize()
        elif skill_name == 'moltbook':
            from aria_skills.moltbook import MoltbookSkill
            from aria_skills.base import SkillConfig
            # Support both MOLTBOOK_API_KEY and MOLTBOOK_TOKEN
            api_key = os.environ.get('MOLTBOOK_API_KEY') or os.environ.get('MOLTBOOK_TOKEN')
            config = SkillConfig(name='moltbook', config={
                'api_url': os.environ.get('MOLTBOOK_API_URL', 'https://moltbook.com/api'),
                'auth': api_key
            })
            skill = MoltbookSkill(config)
            await skill.initialize()
        elif skill_name == 'health':
            from aria_skills.health import HealthSkill
            from aria_skills.base import SkillConfig
            config = SkillConfig(name='health')
            skill = HealthSkill(config)
            await skill.initialize()
        elif skill_name == 'llm':
            from aria_skills.llm import LLMSkill
            from aria_skills.base import SkillConfig
            config = SkillConfig(name='llm', config={
                'ollama_url': os.environ.get('OLLAMA_URL'),
                'model': os.environ.get('OLLAMA_MODEL', 'hf.co/unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF:Q3_K_S')
            })
            skill = LLMSkill(config)
            await skill.initialize()
        elif skill_name == 'knowledge_graph':
            from aria_skills.knowledge_graph import KnowledgeGraphSkill
            from aria_skills.base import SkillConfig
            config = SkillConfig(name='knowledge_graph', config={'dsn': os.environ.get('DATABASE_URL')})
            skill = KnowledgeGraphSkill(config)
            await skill.initialize()
        elif skill_name == 'goals':
            from aria_skills.goals import GoalSkill
            from aria_skills.base import SkillConfig
            config = SkillConfig(name='goals', config={'dsn': os.environ.get('DATABASE_URL')})
            skill = GoalSkill(config)
            await skill.initialize()
        elif skill_name == 'pytest':
          from aria_skills.pytest_runner import PytestSkill
          from aria_skills.base import SkillConfig
          config = SkillConfig(name='pytest', config={
            'workspace': os.environ.get('PYTEST_WORKSPACE', '/root/.openclaw/workspace'),
            'timeout_sec': int(os.environ.get('PYTEST_TIMEOUT_SEC', '600')),
            'default_args': os.environ.get('PYTEST_DEFAULT_ARGS', '-q')
          })
          skill = PytestSkill(config)
          await skill.initialize()
        elif skill_name == 'model_switcher':
          from aria_skills.model_switcher import ModelSwitcherSkill
          from aria_skills.base import SkillConfig
          config = SkillConfig(name='model_switcher', config={
            'url': os.environ.get('OLLAMA_URL', 'http://host.docker.internal:11434')
          })
          skill = ModelSwitcherSkill(config)
          await skill.initialize()
        else:
            return {'error': f'Unknown skill: {skill_name}'}
        
        # Get the function and call it
        func = getattr(skill, function_name, None)
        if func is None:
            return {'error': f'Unknown function: {function_name} in skill {skill_name}'}
        
        if asyncio.iscoroutinefunction(func):
            result = await func(**args)
        else:
            result = func(**args)
        
        # Convert SkillResult to dict if needed
        if hasattr(result, '__dict__'):
            return {'success': result.success, 'data': result.data, 'error': result.error}
        return result
        
    except Exception as e:
        return {'error': str(e)}

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(json.dumps({'error': 'Usage: run_skill.py <skill_name> <function_name> [args_json]'}))
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
      "aria-model-switcher": { "enabled": true }
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
    "defaults": {
      "provider": "litellm",
      "model": "trinity-free"
    },
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

# Function to send awakening message after gateway starts
send_awakening_message() {
    sleep 15  # Wait for gateway to be fully ready
    
    if [ ! -f "$FIRST_BOOT_MARKER" ]; then
        echo "=== FIRST BOOT DETECTED - Sending Awakening Message ==="
        
        # Read the awakening message
        if [ -f "/root/.openclaw/workspace/AWAKENING.md" ]; then
            AWAKENING_MSG=$(cat /root/.openclaw/workspace/AWAKENING.md | jq -Rs .)
            
            # Send via OpenClaw CLI (creates a new chat message)
            # Retrying loop to ensure gateway is ready
            echo "Waiting for gateway..."
            for i in {1..10}; do
                /usr/local/bin/openclaw agent --session-id main --message "$AWAKENING_MSG" --deliver > /tmp/awakening.log 2>&1
                if [ $? -eq 0 ]; then
                    echo "Awakening message sent successfully!"
                    touch "$FIRST_BOOT_MARKER"
                    echo "=== Aria is now alive! ==="
                    break
                fi
                echo "Gateway not ready yet, retrying in 5s..."
                sleep 5
            done
        else
            echo "Warning: AWAKENING.md not found in workspace"
        fi
    else
        echo "=== Aria already awakened (marker exists) === "
    fi
}

# Run awakening check in background
send_awakening_message &

# Start the gateway
exec /usr/local/bin/openclaw gateway run \
    --port 18789 \
    --bind lan \
    --token "${OPENCLAW_GATEWAY_TOKEN}" \
    --allow-unconfigured \
    --verbose
