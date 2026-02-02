#!/usr/bin/env python3
"""Test Ollama API directly"""
import requests
import json

BASE = "http://localhost:11434"

print("=== Testing Ollama API ===")

# Test models list
print("\n1. List models:")
r = requests.get(f"{BASE}/api/tags")
models = r.json().get("models", [])
for m in models:
    print(f"  - {m['name']}")

# Test generation with GLM
print("\n2. Test GLM generation:")
r = requests.post(f"{BASE}/api/generate", json={
    "model": "hf.co/unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF:Q3_K_S",
    "prompt": "Say hello in one sentence.",
    "stream": False
})
print(f"  Response: {r.json().get('response', r.text)[:200]}")

# Test generation with Qwen3-VL
print("\n3. Test Qwen3-VL generation:")
r = requests.post(f"{BASE}/api/generate", json={
    "model": "qwen3-vl:8b",
    "prompt": "Say hello in one sentence.",
    "stream": False
})
print(f"  Response: {r.json().get('response', r.text)[:200]}")

# Test OpenAI-compatible endpoint
print("\n4. Test OpenAI-compatible chat completions:")
r = requests.post(f"{BASE}/v1/chat/completions", json={
    "model": "qwen3-vl:8b",
    "messages": [{"role": "user", "content": "Say hello"}],
    "max_tokens": 50
})
print(f"  Response: {json.dumps(r.json(), indent=2)[:500]}")

print("\n=== Tests complete ===")
