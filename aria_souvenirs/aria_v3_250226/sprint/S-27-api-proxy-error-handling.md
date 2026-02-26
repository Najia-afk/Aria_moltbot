# S-27: API Proxy Error Handling & Error Display Standardization
**Epic:** E14 — Frontend Quality | **Priority:** P1 | **Points:** 3 | **Phase:** 2

## Problem
### Problem A: API proxy crashes on connection failure
`src/web/app.py` L63-77: The `api_proxy()` function has no `try/except`. If `_api_internal_url` is unreachable (API container down, network partition), `requests.request()` raises `ConnectionError`/`Timeout` → Flask returns a raw 500 with a Python stack trace to the browser.

### Problem B: Inconsistent API base URL in templates
Templates use 3 different patterns:
- `API_BASE_URL` from base.html context (correct pattern)
- Hardcoded `/api/` relative paths: `engine_agent_dashboard.html` L57, `proposals.html` L67, `sessions.html` L590
- `window.location.origin + '/api'`: `rpg.html` L216

### Problem C: Inconsistent error display
A shared `showErrorState(container, message, retryFn)` exists in `aria-common.js` L96-113 but most pages roll their own error HTML. Example: `engine_agent_dashboard.html` L84-87 shows only "Failed to load metrics" regardless of error type.

## Fix

### Fix 1: Wrap api_proxy in try/except
**File:** `src/web/app.py` L63-77
```python
@app.route('/api/proxy/<path:path>', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
def api_proxy(path):
    try:
        resp = requests.request(
            method=request.method,
            url=f"{_api_internal_url}/{path}",
            headers={k: v for k, v in request.headers if k.lower() != 'host'},
            data=request.get_data(),
            params=request.args,
            timeout=30,
        )
        return Response(resp.content, status=resp.status_code, headers=dict(resp.headers))
    except requests.ConnectionError:
        return jsonify({"error": "API service unavailable", "detail": "Cannot connect to aria-api"}), 502
    except requests.Timeout:
        return jsonify({"error": "API timeout", "detail": "aria-api did not respond in 30s"}), 504
    except Exception as e:
        logger.error(f"API proxy error: {e}", exc_info=True)
        return jsonify({"error": "Proxy error", "detail": str(e)}), 500
```

### Fix 2: Standardize API_BASE_URL
**File:** `src/web/templates/base.html` — in `{% block scripts %}`:
```html
<script>
    const API_BASE = '{{ api_base_url }}';
</script>
```

Then migrate all templates to use `API_BASE`:
- `engine_agent_dashboard.html` L57: replace `/api/` → `API_BASE`
- `proposals.html` L67: replace `/api/` → `API_BASE`
- `sessions.html` L590: replace `/api/` → `API_BASE`
- `rpg.html` L216: replace `window.location.origin + '/api'` → `API_BASE`

### Fix 3: Standardize error display with showErrorState
**File:** `src/web/static/js/aria-common.js`
Enhance `showErrorState()`:
```javascript
function showErrorState(container, message, retryFn) {
    if (typeof container === 'string') container = document.getElementById(container);
    container.setAttribute('role', 'alert');
    container.innerHTML = `
        <div class="error-state">
            <span class="error-icon">⚠️</span>
            <p class="error-message">${escapeHtml(message)}</p>
            ${retryFn ? '<button class="btn btn-sm btn-retry" onclick="(' + retryFn.toString() + ')()">Retry</button>' : ''}
        </div>
    `;
}
```

Then grep all templates and replace custom error HTML with `showErrorState()`.

### Fix 4: Add loading states
Create a standard loading pattern:
```javascript
function showLoadingState(container) {
    if (typeof container === 'string') container = document.getElementById(container);
    container.innerHTML = '<div class="loading-state"><div class="spinner"></div><p>Loading...</p></div>';
}
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ❌ | Frontend/proxy only |
| 2 | .env for secrets | ❌ | |
| 3 | models.yaml truth | ❌ | |
| 4 | Docker-first testing | ✅ | |
| 5 | aria_memories writable | ❌ | |
| 6 | No soul modification | ❌ | |

## Dependencies
- None — standalone.

## Verification
```bash
# 1. Proxy returns 502 when API is down:
docker compose stop aria-api
curl -s http://localhost:5050/api/proxy/health | python -m json.tool
# EXPECTED: {"error": "API service unavailable"}
docker compose start aria-api

# 2. No hardcoded /api/ in templates:
grep -rn "'/api/" src/web/templates/ --include='*.html' | grep -v 'API_BASE'
# EXPECTED: 0 matches

# 3. showErrorState used consistently:
grep -rn 'showErrorState' src/web/templates/ --include='*.html' | wc -l
# EXPECTED: ≥ 10 (used in most data-fetching pages)

# 4. No raw innerHTML error display:
grep -rn "innerHTML.*Error\|innerHTML.*failed\|innerHTML.*error" src/web/templates/ | grep -v 'showErrorState' | grep -v 'escapeHtml'
# EXPECTED: Minimal matches
```

## Prompt for Agent
```
Read these files FIRST:
- src/web/app.py (L55-L85 — api_proxy function)
- src/web/templates/base.html (find API_BASE_URL setup)
- src/web/static/js/aria-common.js (L90-L120 — showErrorState)
- src/web/templates/engine_agent_dashboard.html (L50-L90 — error handling example)

STEPS:
1. Wrap api_proxy() in try/except with proper HTTP status codes (502, 504, 500)
2. Add timeout=30 to requests.request()
3. Add logging for proxy errors
4. Standardize API_BASE in base.html <script> block
5. Grep all templates for hardcoded '/api/' → replace with API_BASE
6. Enhance showErrorState() with escaping and role="alert"
7. Add showLoadingState() to aria-common.js
8. Grep all templates for custom error HTML → replace with showErrorState()
9. Test proxy with API down → verify 502 JSON response
10. Test proxy with API slow → verify 504 after timeout
```
