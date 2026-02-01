#!/bin/bash
set -e

# Install OpenClaw if not present
if [ ! -e /usr/local/bin/openclaw ]; then
    apt-get update && apt-get install -y curl jq
    curl -fsSL https://openclaw.ai/install.sh | bash -s -- --no-onboard --no-prompt
fi

# Create directories
mkdir -p /root/.openclaw

# Generate openclaw.json with LiteLLM provider config
cat > /root/.openclaw/openclaw.json << EOF
{
  "commands": {
    "native": "auto",
    "nativeSkills": "auto"
  },
  "gateway": {
    "port": 18789,
    "mode": "local",
    "bind": "lan",
    "auth": {
      "mode": "token",
      "token": "${OPENCLAW_GATEWAY_TOKEN}"
    },
    "trustedProxies": ["0.0.0.0/0", "::0/0"]
  },
  "agents": {
    "defaults": {
      "maxConcurrent": 4,
      "model": {
        "primary": "litellm/qwen3-local",
        "fallbacks": ["google/gemini-2.0-flash", "google/gemini-2.5-flash"]
      },
      "models": {
        "litellm/qwen3-local": { "alias": "Qwen3 Local" },
        "google/gemini-2.0-flash": { "alias": "Gemini 2.0 Flash" },
        "google/gemini-2.5-flash": { "alias": "Gemini 2.5 Flash" }
      },
      "subagents": {
        "maxConcurrent": 8
      }
    }
  },
  "models": {
    "mode": "merge",
    "providers": {
      "litellm": {
        "baseUrl": "http://litellm:4000/v1",
        "apiKey": "${LITELLM_MASTER_KEY}",
        "api": "openai-responses",
        "models": [
          {
            "id": "qwen3-local",
            "name": "Qwen3-VL 8B via LiteLLM",
            "reasoning": false,
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
