#!/usr/bin/env python3
"""Test MLX server connection."""
import requests

url = "http://localhost:8080/v1/chat/completions"
payload = {
    "model": "nightmedia/Qwen3-VLTO-8B-Instruct-qx86x-hi-mlx",
    "messages": [{"role": "user", "content": "Hi, who are you? Answer briefly."}],
    "max_tokens": 100
}

try:
    r = requests.post(url, json=payload, timeout=60)
    print(r.json())
except Exception as e:
    print(f"Error: {e}")
