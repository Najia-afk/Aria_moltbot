# =============================================================================
# Aria Blue - Dashboard Portal
# Flask app with GraphQL, Grid, Search for Aria activities and records
# =============================================================================

from flask import Flask, render_template, make_response
import os

def create_app():
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')
    
    app.config['SECRET_KEY'] = os.environ['SECRET_KEY']

    service_host = os.environ['SERVICE_HOST']
    api_base_url = os.environ['API_BASE_URL']
    clawdbot_public_url = os.environ['CLAWDBOT_PUBLIC_URL']
    # Extract token from clawdbot URL for dynamic URL generation
    clawdbot_token = os.environ.get('CLAWDBOT_TOKEN', '')

    @app.context_processor
    def inject_config():
        return {
            'service_host': service_host,
            'api_base_url': api_base_url,
            'clawdbot_public_url': clawdbot_public_url,
            'clawdbot_token': clawdbot_token,
        }
    
    @app.after_request
    def add_header(response):
        # Disable Chrome's speculative loading that causes prefetch storms
        response.headers['Supports-Loading-Mode'] = 'fenced-frame'
        return response
    
    # =========================================================================
    # Routes - Pages
    # =========================================================================
    
    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.route('/dashboard')
    def dashboard():
        return render_template('dashboard.html')
    
    @app.route('/activities')
    def activities():
        return render_template('activities.html')
    
    @app.route('/thoughts')
    def thoughts():
        return render_template('thoughts.html')
    
    @app.route('/memories')
    def memories():
        return render_template('memories.html')
    
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
        return render_template('wallets.html')

    @app.route('/goals')
    def goals():
        return render_template('goals.html')

    @app.route('/heartbeat')
    def heartbeat():
        return render_template('heartbeat.html')

    @app.route('/knowledge')
    def knowledge():
        return render_template('knowledge.html')

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
    @app.route('/operations')
    def operations():
        return render_template('operations.html')

    @app.route('/sessions')
    def sessions():
        return render_template('sessions.html')

    @app.route('/working-memory')
    def working_memory():
        return render_template('working_memory.html')

    @app.route('/skills')
    def skills():
        return render_template('skills.html')

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

    # Flask remains UI-only. All data access goes through the FastAPI service.

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
