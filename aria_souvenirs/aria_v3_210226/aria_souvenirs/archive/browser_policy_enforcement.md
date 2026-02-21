# Browser Policy Enforcement - Confirmation

**Date:** 2026-02-11  
**Status:** ✅ ENFORCED  
**Scope:** All sub-agents and spawned sessions

---

## Policy Applied

**MANDATORY:** All web access MUST use docker aria-browser.  
**FORBIDDEN:** Brave Search API (`web_search`) is strictly prohibited.

---

## Changes Made

### 1. Agent Base Configuration (`aria_agents/base.py`)
```python
# Added BROWSER_POLICY constant
BROWSER_POLICY = """
MANDATORY WEB ACCESS POLICY:
- Use ONLY the docker aria-browser (browserless/chrome) for all web access
- Browser endpoint: http://aria-browser:3000 (or localhost:3000 from host)
- Use browser(action="open|snapshot|navigate|act") exclusively
- NEVER use web_search (Brave API) - it is FORBIDDEN
- NEVER use web_fetch for browsing - use browser tool instead
- This policy is MANDATORY with NO EXCEPTIONS
"""
```

### 2. Agent Documentation (`aria_mind/AGENTS.md`)
Added "Mandatory Browser Policy" section at the top of the file:
- Clear rules on web access
- Browser endpoint reference
- Link to full policy doc

### 3. Heartbeat Instructions (`aria_mind/HEARTBEAT.md`)
Added to Standing Orders:
```
7. **Browser Policy** - Use ONLY docker aria-browser for web access (NEVER Brave/web_search)
```

### 4. Policy Document (`aria_memories/knowledge/web_access_policy.md`)
Created comprehensive policy document including:
- Policy statement
- Comparison table (Brave vs aria-browser)
- Correct/incorrect usage examples
- Agent instructions
- Implementation examples
- Verification procedures
- Enforcement mechanisms

---

## Browser Infrastructure

| Setting | Value |
|---------|-------|
| **Container** | `aria-browser` |
| **Image** | `browserless/chrome:latest` |
| **Internal URL** | `http://aria-browser:3000` |
| **External URL** | `http://localhost:3000` |
| **Max Sessions** | 5 concurrent |
| **Timeout** | 60 seconds |

---

## Usage Examples for Agents

### Open a Page
```python
browser(action="open", targetUrl="https://example.com")
```

### Capture Snapshot
```python
browser(action="snapshot", targetUrl="https://example.com", refs="aria")
```

### Navigate and Interact
```python
browser(action="navigate", targetUrl="https://example.com")
browser(action="act", request={"kind": "click", "ref": "e12"})
```

---

## Verification

To verify browser is working:
```python
browser(action="status")
```

Expected: Status shows healthy with browser profiles available.

---

## Compliance

All sub-agents spawned via `sessions_spawn()` or `AgentCoordinator` will inherit this policy through:
1. System prompt injection
2. Skill registry restrictions
3. Audit logging

**NO EXCEPTIONS** without explicit human approval.

---

*Policy enforced by: Aria Blue ⚡️*  
*Files modified: 3 | Files created: 2*
