"""Sandbox HTTP execution server — accepts POST /exec with {"code": "...", "timeout": 30}."""
import json
import subprocess
import sys
import tempfile
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

MAX_TIMEOUT = 120
MAX_CODE_LENGTH = 50_000


class ExecHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/exec":
            self._handle_exec()
        elif self.path == "/health":
            self._respond(200, {"status": "healthy"})
        else:
            self._respond(404, {"error": "Not found"})

    def do_GET(self):
        if self.path == "/health":
            self._respond(200, {"status": "healthy"})
        else:
            self._respond(404, {"error": "Not found"})

    def _handle_exec(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
        except (json.JSONDecodeError, ValueError):
            self._respond(400, {"error": "Invalid JSON"})
            return

        code = body.get("code", "")
        timeout = min(body.get("timeout", 30), MAX_TIMEOUT)

        if not code:
            self._respond(400, {"error": "No code provided"})
            return

        if len(code) > MAX_CODE_LENGTH:
            self._respond(400, {"error": f"Code exceeds {MAX_CODE_LENGTH} chars"})
            return

        # Write code to temp file and execute
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir="/tmp") as f:
            f.write(code)
            f.flush()
            tmp_path = f.name

        try:
            result = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd="/sandbox",
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            self._respond(200, {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
            })
        except subprocess.TimeoutExpired:
            self._respond(200, {
                "stdout": "",
                "stderr": f"Execution timed out after {timeout}s",
                "exit_code": -1,
            })
        except Exception as e:
            self._respond(500, {"error": str(e)})
        finally:
            os.unlink(tmp_path)

    def _respond(self, status_code, data):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        # Only log non-health requests
        if "/health" not in (args[0] if args else ""):
            super().log_message(format, *args)


if __name__ == "__main__":
    port = int(os.environ.get("SANDBOX_PORT", 9999))
    server = HTTPServer(("0.0.0.0", port), ExecHandler)
    print(f"Sandbox server listening on :{port}")
    server.serve_forever()
