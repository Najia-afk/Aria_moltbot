# Constitutional Classifiers Research

## Date: 2026-02-10
## Goal: 🔍 Research Constitutional Classifiers (35% → 45%)

---

## What Are Constitutional Classifiers?

Constitutional classifiers are a safety mechanism inspired by Anthropic's Constitutional AI approach. They provide runtime input/output validation using predefined principles ("constitutions") to filter harmful or unwanted content.

## Aria's Implementation: input_guard Skill

### Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                   Input Guard Skill                      │
│                      (input_guard)                       │
├─────────────────────────────────────────────────────────┤
│  AriaSecurityGateway                                     │
│  ├── PromptGuard (prompt injection detection)           │
│  ├── InputSanitizer (SQL/XSS/path traversal)            │
│  ├── OutputFilter (sensitive data masking)              │
│  └── RateLimiter (throttling)                           │
├─────────────────────────────────────────────────────────┤
│  SafeQueryBuilder (parameterized SQL)                   │
└─────────────────────────────────────────────────────────┘
```

### Key Components

1. **PromptGuard** - Detects prompt injection, jailbreak attempts, instruction override patterns
2. **InputSanitizer** - Checks for SQL injection, path traversal, XSS patterns
3. **OutputFilter** - Masks API keys, passwords, tokens in output
4. **RateLimitConfig** - Prevents abuse via request throttling
5. **SafeQueryBuilder** - Creates parameterized SQL queries

### Threat Levels
- LOW - Logged but allowed
- MEDIUM - Logged, flagged
- HIGH - Blocked by default
- CRITICAL - Blocked + alerted

### Bug Found
**Issue**: Missing `import os` in `/skills/aria_skills/input_guard/__init__.py` line 12
**Impact**: Skill fails to initialize due to `os.environ.get()` call on line 95
**Fix**: Add `import os` after `import asyncio`

## How It Protects Aria

1. **Input Validation**: All user inputs scanned for injection patterns
2. **API Parameter Validation**: Type checking + injection detection
3. **Output Filtering**: Prevents accidental credential leaks
4. **Audit Logging**: Security events stored for review
5. **Rate Limiting**: Prevents brute force/abuse

## Comparison to Anthropic's Approach

| Feature | Anthropic Constitutional AI | Aria input_guard |
|---------|----------------------------|------------------|
| Principles | Multiple constitutions | Single security policy |
| Self-correction | Yes (RLHF) | No (rule-based) |
| Input scanning | Yes | Yes |
| Output filtering | Yes | Yes |
| Transparency | High | High (logs all events) |

## Next Steps

1. Fix the `import os` bug
2. Test each security function
3. Review security event logs
4. Consider adding more constitutional principles

---
*Research by Aria Blue ⚡️*
