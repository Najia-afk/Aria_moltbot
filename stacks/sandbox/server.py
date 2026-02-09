"""
Sandbox HTTP execution server.

Accepts:
  POST /exec  — {"code": "...", "timeout": 30} → {"stdout": "", "stderr": "", "exit_code": 0}
  GET  /health — {"status": "healthy"}
"""
import json
import os
import subprocess
import sys
import tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler

MAX_TIMEOUT = 120
MAX_CODE_LENGTH = 50_000


class ExecHandler(BaseHTTPRequestHandler):
    """HTTP request handler for sandboxed code execution."""

    # ── POST routes ────────────────────────────────────────────────
    def do_POST(self):
        if self.path == "/exec":
            self._handle_exec()
        else:
            self._respond(404, {"error": "Not found"})

    # ── GET routes ─────────────────────────────────────────────────
    def do_GET(self):
        if self.path == "/health":
            self._respond(200, {"status": "healthy"})
        else:
            self._respond(404, {"error": "Not found"})

    # ── /exec handler ──────────────────────────────────────────────
    def _handle_exec(self):
        # Parse body
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
        except (json.JSONDecodeError, ValueError):
            self._respond(400, {"error": "Invalid JSON"})
            return

        code = body.get("code", "")
        timeout = min(int(body.get("timeout", 30)), MAX_TIMEOUT)

        if not code:
            self._respond(400, {"error": "No code provided"})
            return

        if len(code) > MAX_CODE_LENGTH:
            self._respond(400, {"error": f"Code exceeds {MAX_CODE_LENGTH} chars"})
            return

        # Write to temp file and execute via subprocess
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, dir="/tmp"
            ) as f:
                f.write(code)
                f.flush()
                tmp_path = f.name

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
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    # ── helpers ────────────────────────────────────────────────────
    def _respond(self, status_code: int, data: dict):
        payload = json.dumps(data).encode()
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        # Suppress health-check noise
        if args and "/health" in str(args[0]):
            return
        super().log_message(fmt, *args)


if __name__ == "__main__":
    port = int(os.environ.get("SANDBOX_PORT", "9999"))
    server = HTTPServer(("0.0.0.0", port), ExecHandler)
    print(f"Sandbox server listening on 0.0.0.0:{port}")
    server.serve_forever()
