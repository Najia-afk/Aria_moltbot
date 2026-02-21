# S6-06: Remove OpenClaw Proxy Routes from Flask Web App
**Epic:** E5 — Web Dashboard Evolution | **Priority:** P0 | **Points:** 2 | **Phase:** 6

## Problem
The Flask web app (`src/web/app.py`) contains a `/clawdbot/` reverse proxy route that forwards requests to the OpenClaw container. With OpenClaw being removed (E6), this proxy must be deleted. Navigation references to OpenClaw should be updated to point to the new engine routes (`/chat/`, `/operations/`).

## Root Cause
The `/clawdbot/` proxy was added in `src/web/app.py` (lines 82-99) to allow the dashboard to proxy requests to OpenClaw's gateway at `http://clawdbot:18789`. Several environment variables (`CLAWDBOT_PUBLIC_URL`, `CLAWDBOT_TOKEN`, `CLAWDBOT_URL`) support this proxy. With OpenClaw removal, all of this dead code must go.

## Fix

### `src/web/app.py` — Updated version

```python
# =============================================================================
# Aria Blue - Dashboard Portal
# Flask app with GraphQL, Grid, Search for Aria activities and records
# =============================================================================

from flask import Flask, render_template, make_response, request, Response, send_from_directory
import os
import requests as http_requests

def create_app():
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')
    
    app.config['SECRET_KEY'] = os.environ['SECRET_KEY']

    service_host = os.environ['SERVICE_HOST']
    api_base_url = os.environ['API_BASE_URL']
    # REMOVED: clawdbot_public_url, clawdbot_token — OpenClaw removed

    # Internal API service URL (Docker network or localhost fallback)
    _api_internal_url = os.environ.get('API_INTERNAL_URL', 'http://aria-api:8000')

    @app.context_processor
    def inject_config():
        return {
            'service_host': service_host,
            'api_base_url': api_base_url,
            # REMOVED: clawdbot_public_url, clawdbot_token
        }
    
    @app.after_request
    def add_header(response):
        # Disable Chrome's speculative loading that causes prefetch storms
        response.headers['Supports-Loading-Mode'] = 'fenced-frame'

        # Force fresh dashboard HTML to avoid stale templates/scripts after deploys
        if response.content_type and response.content_type.startswith('text/html'):
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response

    @app.route('/favicon.ico')
    def favicon_ico():
        return send_from_directory(app.static_folder, 'favicon.svg', mimetype='image/svg+xml')
    
    # =========================================================================
    # API Reverse Proxy - forwards /api/* to aria-api backend
    # Enables dashboard to work when accessed directly (port 5000)
    # without requiring Traefik (port 80)
    # =========================================================================
    @app.route('/api/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'])
    @app.route('/api/<path:path>', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'])
    def api_proxy(path):
        url = f"{_api_internal_url}/{path}"
        resp = http_requests.request(
            method=request.method,
            url=url,
            params=request.args,
            headers={k: v for k, v in request.headers if k.lower() not in ('host', 'transfer-encoding')},
            data=request.get_data(),
            timeout=30,
        )
        # Build Flask response from upstream
        excluded_headers = {'content-encoding', 'transfer-encoding', 'connection', 'content-length'}
        headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded_headers}
        return Response(resp.content, status=resp.status_code, headers=headers)

    # REMOVED: /clawdbot/ proxy route — OpenClaw removed (Operation Independence)
    # Previously: forwarded to http://clawdbot:18789 with Bearer token injection
    # Replaced by: native /chat/ route (S6-01) connecting to engine WebSocket

    # =========================================================================
    # Routes - Pages
    # =========================================================================
    
    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.route('/dashboard')
    def dashboard():
        from flask import redirect
        return redirect('/', code=301)
    
    @app.route('/activities')
    def activities():
        return render_template('activities.html')

    @app.route('/activity-visualization')
    @app.route('/creative-pulse')
    def creative_pulse():
        return render_template('creative_pulse.html')
    
    @app.route('/thoughts')
    def thoughts():
        return render_template('thoughts.html')
    
    @app.route('/memories')
    def memories():
        return render_template('memories.html')

    @app.route('/sentiment')
    def sentiment():
        return render_template('sentiment.html')

    @app.route('/patterns')
    def patterns():
        return render_template('patterns.html')

    @app.route('/records')
    def records():
        return render_template('records.html')
    
    @app.route('/search')
    def search():
        return render_template('search.html')
    
    @app.route('/services')
    def services():
        return render_template('services.html')
    
    @app.route('/litellm')
    def litellm():
        # Merged into /models — redirect for bookmarks
        from flask import redirect
        return redirect('/models', code=301)

    @app.route('/models')
    def models():
        return render_template('models.html')

    @app.route('/wallets')
    def wallets():
        from flask import redirect
        return redirect('/models', code=301)

    @app.route('/sprint-board')
    def sprint_board():
        return render_template('sprint_board.html')

    @app.route('/heartbeat')
    def heartbeat():
        return render_template('heartbeat.html')

    @app.route('/knowledge')
    def knowledge():
        return render_template('knowledge.html')

    @app.route('/skill-graph')
    def skill_graph():
        return render_template('skill_graph.html')

    @app.route('/social')
    def social():
        return render_template('social.html')

    @app.route('/performance')
    def performance():
        return render_template('performance.html')

    @app.route('/security')
    def security():
        return render_template('security.html')

    # ============================================
    # Aria Operations Routes
    # ============================================
    @app.route('/sessions')
    def sessions():
        return render_template('sessions.html')

    @app.route('/working-memory')
    def working_memory():
        return render_template('working_memory.html')

    @app.route('/skills')
    def skills():
        return render_template('skills.html')

    @app.route('/proposals')
    def proposals():
        return render_template('proposals.html')

    @app.route('/skill-stats')
    def skill_stats():
        return render_template('skill_stats.html')

    @app.route('/skill-health')
    def skill_health():
        return render_template('skill_health.html')

    @app.route('/soul')
    def soul():
        return render_template('soul.html')

    @app.route('/model-usage')
    def model_usage():
        return render_template('model_usage.html')

    @app.route('/rate-limits')
    def rate_limits():
        return render_template('rate_limits.html')

    @app.route('/api-key-rotations')
    def api_key_rotations():
        return render_template('api_key_rotations.html')

    # ============================================
    # Engine Routes (New — replaces OpenClaw UI)
    # ============================================
    @app.route('/chat/')
    @app.route('/chat/<session_id>')
    def chat(session_id=None):
        return render_template('engine_chat.html', session_id=session_id)

    @app.route('/operations/cron/')
    def operations_cron():
        return render_template('engine_operations.html')

    @app.route('/operations/agents/')
    def operations_agents():
        return render_template('engine_agents_mgmt.html')

    @app.route('/operations/agents/<agent_id>/prompt')
    def operations_agent_prompt(agent_id):
        return render_template('engine_prompt_editor.html', agent_id=agent_id)

    @app.route('/operations/health/')
    def operations_health():
        return render_template('engine_health.html')

    # Legacy redirect: anyone bookmarking /clawdbot/ gets redirected to /chat/
    @app.route('/clawdbot/')
    @app.route('/clawdbot/<path:path>')
    def clawdbot_redirect(path=''):
        from flask import redirect
        return redirect('/chat/', code=301)

    # Flask remains UI-only. All data access goes through the FastAPI service.

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.environ.get('WEB_PORT', '5000')), debug=True)
```

### Changes Summary
1. **Removed** `clawdbot_public_url` and `clawdbot_token` env var reads
2. **Removed** `clawdbot_public_url` and `clawdbot_token` from context processor
3. **Removed** `_clawdbot_internal_url` variable
4. **Removed** entire `/clawdbot/` proxy route function (17 lines)
5. **Added** `/clawdbot/` → `/chat/` 301 redirect for backward compatibility
6. **Added** engine routes: `/chat/`, `/operations/cron/`, `/operations/agents/`, `/operations/health/`

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Flask stays UI-only, proxies to API |
| 2 | .env for secrets (zero in code) | ✅ | CLAWDBOT env vars removed |
| 3 | models.yaml single source of truth | ❌ | No model access |
| 4 | Docker-first testing | ✅ | Flask container startup must work |
| 5 | aria_memories only writable path | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S6-01 (Chat UI template must exist before `/chat/` route is added)
- S7-01 (Cron page template for `/operations/cron/`)
- S7-02 (Agent page template for `/operations/agents/`)

## Verification
```bash
# 1. /clawdbot/ redirects to /chat/:
curl -s -o /dev/null -w "%{http_code}" http://aria-web:5000/clawdbot/
# EXPECTED: 301

# 2. /chat/ is accessible:
curl -s -o /dev/null -w "%{http_code}" http://aria-web:5000/chat/
# EXPECTED: 200

# 3. No clawdbot proxy code remains:
grep -c "clawdbot_proxy" src/web/app.py
# EXPECTED: 0

# 4. No CLAWDBOT env reads (except redirect route name):
grep -c "CLAWDBOT_PUBLIC_URL\|CLAWDBOT_TOKEN\|CLAWDBOT_URL" src/web/app.py
# EXPECTED: 0

# 5. API proxy still works:
curl -s -o /dev/null -w "%{http_code}" http://aria-web:5000/api/health
# EXPECTED: 200
```

## Prompt for Agent
```
Remove the OpenClaw /clawdbot/ proxy from the Flask web app and add engine routes.

FILES TO READ FIRST:
- src/web/app.py (full file — find /clawdbot/ proxy route to remove)
- src/web/templates/base.html (lines 80-200 — navigation, check for clawdbot references)
- src/web/templates/services.html (if exists — any clawdbot health checks)
- src/web/templates/operations.html (if exists — any clawdbot references)

STEPS:
1. Read src/web/app.py fully
2. Remove clawdbot_public_url, clawdbot_token env var reads (lines 20-21)
3. Remove clawdbot from context_processor inject_config() (lines 33-34)
4. Remove _clawdbot_internal_url (line 82)
5. Remove clawdbot_proxy() function (lines 84-99)
6. Add 301 redirect: /clawdbot/* → /chat/
7. Add engine routes: /chat/, /operations/cron/, /operations/agents/, /operations/health/
8. Check templates for clawdbot_public_url references, update to new routes
9. Run verification

CONSTRAINTS:
- Keep /api/ proxy intact (needed for dashboard → aria-api communication)
- Add 301 redirect for backward compatibility (bookmarks)
- New engine routes must reference templates from other Sprint 6/7 tickets
```
