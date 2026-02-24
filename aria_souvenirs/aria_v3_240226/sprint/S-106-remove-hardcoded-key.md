# S-106: Remove Hardcoded sk-aria-internal Credential
**Epic:** E4 — Security Hardening | **Priority:** P0 | **Points:** 2 | **Phase:** 1

## Problem
`aria_skills/conversation_summary/__init__.py` hardcodes `sk-aria-internal` as a fallback LiteLLM API key. This credential is visible in source code and could be used to access the LiteLLM proxy directly.

Additionally, this skill makes direct `httpx` calls to the LiteLLM proxy instead of routing through the `litellm` skill or `api_client`, which violates the 5-layer architecture.

## Root Cause
The conversation_summary skill was built to directly call LiteLLM for summarization instead of using the established skill chain (api_client → litellm skill).

## Fix
1. Remove hardcoded `sk-aria-internal` key
2. Route LLM calls through the `litellm` skill or `api_client`
3. If direct LiteLLM access is required, read the key from environment variable

```python
# BEFORE:
headers = {"Authorization": f"Bearer sk-aria-internal"}
async with httpx.AsyncClient() as client:
    response = await client.post("http://litellm:18793/v1/chat/completions", ...)

# AFTER:
# Option 1: Use litellm skill
from aria_skills.litellm import LiteLLMSkill
litellm = LiteLLMSkill()
result = await litellm.chat_completion(messages=messages, model=model)

# Option 2: Use environment variable (if direct access needed)
import os
LITELLM_KEY = os.environ.get("LITELLM_MASTER_KEY", "")
headers = {"Authorization": f"Bearer {LITELLM_KEY}"}
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | Fix also resolves architecture violation |
| 2 | .env for secrets | ✅ | Key must come from env, not code |
| 3 | models.yaml single source | ❌ | No model changes |
| 4 | Docker-first testing | ✅ | Test in Docker with LiteLLM service |
| 5 | aria_memories writable path | ❌ | No memory changes |
| 6 | No soul modification | ❌ | No soul changes |

## Dependencies
- None

## Verification
```bash
# 1. Verify hardcoded key is removed
grep -rn "sk-aria-internal" aria_skills/
# EXPECTED: no matches

# 2. Verify no hardcoded API keys in skills
grep -rn "sk-" aria_skills/ | grep -v ".pyc" | grep -v "__pycache__"
# EXPECTED: no hardcoded sk- keys

# 3. Run tests
pytest tests/ -k "conversation" -v
# EXPECTED: all pass
```

## Prompt for Agent
```
Read: aria_skills/conversation_summary/__init__.py (full file)

Steps:
1. Find the hardcoded "sk-aria-internal" string
2. Replace with os.environ.get("LITELLM_MASTER_KEY", "")
3. Better: refactor to use litellm skill instead of direct httpx
4. Remove independent httpx.AsyncClient creation
5. Verify: grep -rn "sk-aria-internal" aria_skills/ returns nothing
6. Test in Docker with LiteLLM service running
```
