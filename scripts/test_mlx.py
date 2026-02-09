#!/usr/bin/env python3
"""Quick MLX inference test"""
import os
import urllib.request
import json

data = json.dumps({
    "model": "nightmedia/Qwen3-VLTO-8B-Instruct-qx86x-hi-mlx",
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
