# =============================================================================
# Aria Blue - Dashboard Portal
# Flask app with GraphQL, Grid, Search for Aria activities and records
# =============================================================================

from flask import Flask, render_template
import os

def create_app():
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')
    
    app.config['SECRET_KEY'] = os.environ['SECRET_KEY']

    service_host = os.environ['SERVICE_HOST']
    api_base_url = os.environ['API_BASE_URL']
    clawdbot_public_url = os.environ['CLAWDBOT_PUBLIC_URL']

    @app.context_processor
    def inject_config():
        return {
            'service_host': service_host,
            'api_base_url': api_base_url,
            'clawdbot_public_url': clawdbot_public_url,
        }
    
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
    
    @app.route('/records')
    def records():
        return render_template('records.html')
    
    @app.route('/search')
    def search():
        return render_template('search.html')
    
    @app.route('/services')
    def services():
        return render_template('services.html')
    
    # Flask remains UI-only. All data access goes through the FastAPI service.
    
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
