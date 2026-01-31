#!/bin/sh
# Aria Bot Entrypoint

echo "⚡️ Starting Aria Bot..."

# Load soul files
if [ -d "/app/soul" ]; then
    echo "Loading soul files..."
    ls -la /app/soul/
fi

# Check for OpenClaw
if [ -f "/app/openclaw/index.js" ]; then
    echo "OpenClaw found, starting..."
    cd /app/openclaw
    exec "$@"
else
    echo "OpenClaw not found, running in standalone mode..."
    # Fallback: run a simple health server
    exec node -e "
const http = require('http');
const server = http.createServer((req, res) => {
    if (req.url === '/health') {
        res.writeHead(200, {'Content-Type': 'application/json'});
        res.end(JSON.stringify({status: 'ok', mode: 'standalone', timestamp: new Date().toISOString()}));
    } else {
        res.writeHead(200, {'Content-Type': 'text/html'});
        res.end('<html><body><h1>⚡️ Aria Bot</h1><p>Standalone mode - OpenClaw not configured</p></body></html>');
    }
});
server.listen(18789, () => console.log('Aria Bot listening on :18789'));
"
fi
