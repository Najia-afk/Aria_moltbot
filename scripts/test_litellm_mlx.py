#!/usr/bin/env python3
"""Test MLX via LiteLLM proxy."""
import requests

url = "http://localhost:4000/v1/chat/completions"
headers = {"Authorization": "Bearer sk-aria-local-key"}
payload = {
    "model": "qwen3-mlx",
    "messages": [{"role": "user", "content": "Hi, who are you? Answer in one sentence."}],
    "max_tokens": 100
}

try:
    r = requests.post(url, json=payload, headers=headers, timeout=120)
    print(r.status_code)
    print(r.json())
except Exception as e:
    print(f"Error: {e}")
