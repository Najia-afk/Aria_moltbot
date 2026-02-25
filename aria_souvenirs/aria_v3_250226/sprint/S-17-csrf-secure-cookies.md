# S-17: CSRF Protection & Secure Cookie Flags
**Epic:** E10 — Security Hardening | **Priority:** P0 | **Points:** 3 | **Phase:** 1

## Problem
1. **No CSRF protection** — `src/web/app.py` L16 sets `SECRET_KEY` but never initializes `flask_wtf.CSRFProtect`. The web app's API proxy makes state-changing requests (DELETE sessions, trigger cron jobs, manage models) on behalf of the user. Without CSRF tokens, a malicious site can forge these requests.

2. **No secure cookie flags** — `src/web/app.py` L16: `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY`, and `SESSION_COOKIE_SAMESITE` are not configured. Session cookies can be stolen via XSS or sent in cross-site requests.

## Root Cause
Flask defaults are permissive. Security hardening was not applied after initial scaffolding.

## Fix

### Fix 1: Enable CSRF protection
**File:** `src/web/app.py`
```python
from flask_wtf.csrf import CSRFProtect

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret')
csrf = CSRFProtect(app)

# Exempt the API proxy route (it's a pass-through, not a form submission)
@csrf.exempt
@app.route('/api/proxy/<path:path>', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
def api_proxy(path):
    ...
```

### Fix 2: Add CSRF meta tag to base.html
**File:** `src/web/templates/base.html`
Add to `<head>`:
```html
<meta name="csrf-token" content="{{ csrf_token() }}">
```

### Fix 3: Add CSRF header to frontend fetch calls
**File:** `src/web/static/js/aria-common.js`
```javascript
// Global fetch wrapper with CSRF
function ariaFetch(url, options = {}) {
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
    options.headers = {
        ...options.headers,
        'X-CSRFToken': csrfToken,
    };
    return fetch(url, options);
}
```

### Fix 4: Set secure cookie flags
**File:** `src/web/app.py`
```python
app.config.update(
    SESSION_COOKIE_SECURE=os.environ.get('FLASK_ENV') == 'production',
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)
```

### Fix 5: Add flask-wtf to dependencies
**File:** `pyproject.toml` or `requirements.txt` — add `flask-wtf>=1.2.0`

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ❌ | Frontend security |
| 2 | .env for secrets | ✅ | SECRET_KEY via env |
| 3 | models.yaml truth | ❌ | |
| 4 | Docker-first testing | ✅ | |
| 5 | aria_memories writable | ❌ | |
| 6 | No soul modification | ❌ | |

## Dependencies
- None — standalone P0 security fix.

## Verification
```bash
# 1. CSRF token in pages:
curl -s http://localhost:5050/dashboard | grep 'csrf-token'
# EXPECTED: <meta name="csrf-token" content="...">

# 2. POST without CSRF fails:
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:5050/some-form-endpoint
# EXPECTED: 400 (CSRF validation failed)

# 3. Secure cookie flags:
curl -sI http://localhost:5050/ | grep -i 'set-cookie'
# EXPECTED: HttpOnly; SameSite=Lax (Secure only in production with HTTPS)

# 4. API proxy still works (CSRF exempt):
curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/api/proxy/health
# EXPECTED: 200
```

## Prompt for Agent
```
Read these files FIRST:
- src/web/app.py (full)
- src/web/templates/base.html (L1-L50 — <head> section)
- src/web/static/js/aria-common.js (full)
- pyproject.toml (dependencies section)

CONSTRAINTS: #2 (.env for SECRET_KEY).

STEPS:
1. Add flask-wtf to project dependencies
2. Initialize CSRFProtect(app) in app.py
3. Exempt the API proxy route from CSRF
4. Add <meta name="csrf-token"> to base.html <head>
5. Create ariaFetch() wrapper in aria-common.js with CSRF header
6. Set SESSION_COOKIE_HTTPONLY, SESSION_COOKIE_SAMESITE in app.py
7. Conditionally set SESSION_COOKIE_SECURE for production
8. Grep for all direct fetch() calls in templates — consider migrating to ariaFetch()
9. Run verification commands
10. IMPORTANT: Don't break the API proxy or WebSocket connections
```
