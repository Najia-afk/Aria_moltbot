#!/usr/bin/env python3
"""Test LiteLLM proxy"""
import requests
import json
import sys

LITELLM = "http://192.168.1.53:18793"
API_KEY = "sk-aria-local-key"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

print("=== Testing LiteLLM Proxy ===")

# Test health
print("\n1. Health check:")
try:
    r = requests.get(f"{LITELLM}/health", timeout=5)
    print(f"  Status: {r.status_code}")
    print(f"  Response: {r.text[:200]}")
except Exception as e:
    print(f"  Error: {e}")

# Test models list
print("\n2. List models:")
try:
    r = requests.get(f"{LITELLM}/v1/models", headers=headers, timeout=5)
    print(f"  Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        for m in data.get("data", [])[:5]:
            print(f"  - {m['id']}")
    else:
        print(f"  Response: {r.text[:200]}")
except Exception as e:
    print(f"  Error: {e}")

# Test chat completion with GLM
print("\n3. Test GLM chat completion:")
try:
    r = requests.post(f"{LITELLM}/v1/chat/completions", 
        headers=headers,
        json={
            "model": "glm-local",
            "messages": [{"role": "user", "content": "Say hello in one word"}],
            "max_tokens": 50
        },
        timeout=120
    )
    print(f"  Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        print(f"  Response: {content[:200]}")
    else:
        print(f"  Error: {r.text[:500]}")
except Exception as e:
    print(f"  Error: {e}")

# Test chat completion with Qwen3-VL
print("\n4. Test Qwen3-VL chat completion:")
try:
    r = requests.post(f"{LITELLM}/v1/chat/completions", 
        headers=headers,
        json={
            "model": "qwen3-vl",
            "messages": [{"role": "user", "content": "Say hello in one word"}],
            "max_tokens": 50
        },
        timeout=120
    )
    print(f"  Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        print(f"  Response: {content[:200]}")
    else:
        print(f"  Error: {r.text[:500]}")
except Exception as e:
    print(f"  Error: {e}")

print("\n=== Tests complete ===")
