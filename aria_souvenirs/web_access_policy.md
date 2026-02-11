# Web Access Policy for All Aria Sub-Agents

**Date:** 2026-02-11  
**Policy Version:** 1.0  
**Enforcement:** MANDATORY for all sub-agents and spawned sessions

---

## Policy Statement

ALL web access MUST use the **docker aria-browser** (Headless Chrome via browserless/chrome).  
**NEVER** use Brave Search API (`web_search` tool) or direct `web_fetch` for internet access.

---

## Why This Policy

| Aspect | Brave/web_search | aria-browser (Docker) |
|--------|------------------|----------------------|
| **Privacy** | External API call | Local container |
| **Control** | Limited by Brave | Full browser automation |
| **Security** | Third-party dependency | Self-hosted, isolated |
| **Capability** | Search only | Full browsing, screenshots, forms |
| **Cost** | API limits/rate limits | Unlimited local use |

---

## Correct Usage

### ✅ Use Browser Tool (MANDATORY)

```python
# CORRECT: Use docker browser for all web access
browser(
    action="open",
    targetUrl="https://example.com"
)

browser(
    action="snapshot",
    targetUrl="https://example.com",
    refs="aria"
)
```

**Browser Container Details:**
- **Endpoint:** `http://aria-browser:3000` (internal Docker network)
- **External Port:** `localhost:3000` (from host)
- **Service Name:** `aria-browser`
- **Image:** `browserless/chrome:latest`

### ❌ Never Use (FORBIDDEN)

```python
# FORBIDDEN: Do not use Brave search
web_search(query="...")  # ❌ NEVER

# FORBIDDEN: Do not use direct web fetch for browsing
web_fetch(url="...")  # ❌ NEVER (unless for simple API calls)
```

---

## Agent Instructions

When spawning sub-agents, include this directive:

```
MANDATORY WEB ACCESS POLICY:
- Use ONLY the docker aria-browser for all web access
- URL: http://aria-browser:3000 (or localhost:3000 from host)
- NEVER use web_search (Brave) or web_fetch for browsing
- Use browser(action="open|snapshot|navigate") exclusively
```

---

## Implementation Examples

### Research Task
```python
# GOOD: Research using docker browser
browser(action="open", targetUrl="https://arxiv.org/search/?query=ai+safety")
browser(action="snapshot", refs="aria")
# Extract information from snapshot
```

### Market Data
```python
# GOOD: Scrape using docker browser  
browser(action="open", targetUrl="https://coinmarketcap.com")
browser(action="snapshot", refs="aria")
```

### Social Media
```python
# GOOD: Check Moltbook using docker browser
browser(action="open", targetUrl="https://www.moltbook.com")
browser(action="snapshot", refs="aria")
```

---

## Verification

All sub-agents must verify browser availability:
```python
# Check browser health
browser(action="status")
```

If browser is unavailable, the agent should:
1. Log the failure
2. Request human assistance
3. **Never** fall back to Brave/web_search

---

## Enforcement

This policy is enforced through:
1. **Agent Prompts:** All sub-agent prompts include this policy
2. **Skill Restrictions:** web_search skill disabled in agent contexts
3. **Audit Logs:** All web access logged for compliance review

---

## Exceptions

**NO EXCEPTIONS** without explicit human approval.  
If you believe an exception is needed, request permission with justification.

---

## Related Infrastructure

- **Docker Compose:** `stacks/brain/docker-compose.yml`
- **Service:** `aria-browser`
- **Health Check:** `http://aria-browser:3000/health`
- **Documentation:** `aria_memories/knowledge/web_access_policy.md`

---

*Policy established: 2026-02-11*  
*Enforced by: Aria Blue ⚡️*
