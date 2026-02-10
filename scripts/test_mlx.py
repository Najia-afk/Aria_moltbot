#!/usr/bin/env python3
"""Quick MLX inference test"""
import os
import urllib.request
import json

# Load MLX model name from models.yaml (single source of truth)
try:
    from aria_models.loader import load_catalog
    _cat = load_catalog()
    _mlx_litellm = _cat.get("models", {}).get("qwen3-mlx", {}).get("litellm", {}).get("model", "")
    _MLX_MODEL = _mlx_litellm.removeprefix("openai/") or "mlx-community/Qwen3-4B-Instruct-2507-4bit"
except Exception:
    _MLX_MODEL = "mlx-community/Qwen3-4B-Instruct-2507-4bit"

data = json.dumps({
    "model": _MLX_MODEL,
    "messages": [{"role": "user", "content": "Say hello in one short sentence"}],
    "max_tokens": 30
}).encode()

req = urllib.request.Request(
    os.environ.get("MLX_URL", "http://localhost:8080") + "/v1/chat/completions",
    data,
    {"Content-Type": "application/json"}
)
r = urllib.request.urlopen(req, timeout=60)
result = json.loads(r.read())
msg = result["choices"][0]["message"]["content"]
print(f"Model response: {msg}")
print(f"Tokens: {result.get('usage', {})}")
