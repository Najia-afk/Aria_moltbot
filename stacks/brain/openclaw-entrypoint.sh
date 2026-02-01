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
    tenacity || echo "Warning: Some Python packages failed to install"

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
                'model': os.environ.get('OLLAMA_MODEL', 'qwen3-vl:8b')
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

# Generate openclaw.json with LiteLLM provider config and skill definitions
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
      "aria-health": { "enabled": true }
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
  "agents": {
    "defaults": {
      "maxConcurrent": 4,
      "workspace": "/root/.openclaw/workspace",
      "model": {
        "primary": "litellm/qwen3-local",
        "fallbacks": ["google/gemini-2.0-flash", "google/gemini-2.5-flash"]
      },
      "models": {
        "litellm/qwen3-local": { "alias": "Qwen3-VL 8B Local" },
        "google/gemini-2.0-flash": { "alias": "Gemini 2.0 Flash" },
        "google/gemini-2.5-flash": { "alias": "Gemini 2.5 Flash" }
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
        "enabled": true,
        "provider": "openai",
        "fallback": "none"
      }
    }
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
        "apiKey": "${LITELLM_MASTER_KEY}",
        "api": "openai-completions",
        "models": [
          {
            "id": "qwen3-local",
            "name": "Qwen3-VL 8B via LiteLLM",
            "reasoning": true,
            "input": ["text", "image"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 32768,
            "maxTokens": 8192
          }
        ]
      }
    }
  },
  "messages": {
    "ackReactionScope": "group-mentions"
  }
}
EOF

echo "OpenClaw config created with LiteLLM provider"
cat /root/.openclaw/openclaw.json

# Start the gateway
exec /usr/local/bin/openclaw gateway run \
    --port 18789 \
    --bind lan \
    --token "${OPENCLAW_GATEWAY_TOKEN}" \
    --allow-unconfigured \
    --verbose
