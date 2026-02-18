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
    # REMOVED: legacy bot proxy config (Operation Independence)

    # Internal API service URL (Docker network or localhost fallback)
    _api_internal_url = os.environ.get('API_INTERNAL_URL', 'http://aria-api:8000')

    @app.context_processor
    def inject_config():
        return {
            'service_host': service_host,
            'api_base_url': api_base_url,
            # REMOVED: legacy bot proxy config
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

    # REMOVED: legacy bot proxy route (Operation Independence)
    # Previously: forwarded to legacy bot service with Bearer token injection
    # Replaced by: native /chat/ route (S6-01) connecting to engine WebSocket

    # Legacy redirect: anyone bookmarking /clawdbot/ gets redirected to /chat/
    @app.route('/clawdbot/')
    @app.route('/clawdbot/<path:path>')
    def legacy_bot_redirect(path=''):
        from flask import redirect
        return redirect('/chat/', code=301)

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

    @app.route('/cron')
    @app.route('/cron/')
    def cron_page():
        """Cron job management page."""
        return render_template('engine_cron.html')

    @app.route('/agents')
    @app.route('/agents/')
    def agents_page():
        """Agent management page."""
        return render_template('engine_agents.html')

    @app.route('/agent-dashboard')
    @app.route('/agent-dashboard/')
    def agent_dashboard_page():
        """Agent performance dashboard."""
        return render_template('engine_agent_dashboard.html')

    @app.route('/rate-limits')
    def rate_limits():
        return render_template('rate_limits.html')

    @app.route('/api-key-rotations')
    def api_key_rotations():
        return render_template('api_key_rotations.html')

    # ============================================
    # Operations Hub Routes (Sprint 7)
    # ============================================
    @app.route('/operations')
    @app.route('/operations/')
    def operations():
        return render_template('operations.html')

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

    # ============================================
    # Engine Routes (native chat UI)
    # ============================================
    @app.route('/chat/')
    @app.route('/chat/<session_id>')
    def chat(session_id=None):
        return render_template('engine_chat.html', session_id=session_id)

    # Flask remains UI-only. All data access goes through the FastAPI service.

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.environ.get('WEB_PORT', '5000')), debug=True)
