"""Comprehensive audit of skills, web pages, and API endpoints."""
import os
import urllib.request, json

API = os.getenv("ARIA_API_URL", "http://localhost:8000")
WEB = os.getenv("ARIA_WEB_URL", "http://localhost:8080")
API_KEY = os.getenv("ARIA_API_KEY", "")


def _request(url: str, timeout: int = 10):
    headers = {"X-API-Key": API_KEY} if API_KEY else {}
    req = urllib.request.Request(url, headers=headers)
    return urllib.request.urlopen(req, timeout=timeout)

def get(url, timeout=10):
    r = _request(url, timeout=timeout)
    return json.loads(r.read().decode())

def get_raw(url, timeout=5):
    r = _request(url, timeout=timeout)
    return r.read().decode()

# 1. Skills health dashboard
print("=== SKILLS HEALTH DASHBOARD ===")
try:
    data = get(f"{API}/skills/health/dashboard")
    overall = data.get("overall", {})
    print(f"Score: {overall.get('health_score')}%  Status: {overall.get('status')}")
    print(f"Invocations: {overall.get('total_invocations')}  Failures: {overall.get('total_failures')}")
    print(f"Unhealthy: {overall.get('unhealthy_count')}  Degraded: {overall.get('degraded_count')}  Slow: {overall.get('slow_count')}")
    print()
    for s in data.get("skills", []):
        name = s.get("skill_name", "?")
        score = s.get("health_score", 0)
        status = s.get("status", "?")
        calls = s.get("total_calls", 0)
        fails = s.get("failures", 0)
        print(f"  {name:25} score={score:6.1f}  status={status:12}  calls={calls:4}  fails={fails}")
except Exception as e:
    print(f"  FAIL: {e}")

# 2. Tool registry - what skills were discovered vs removed
print()
print("=== TOOL REGISTRY (via container) ===")
# We'll check this separately

# 3. Web pages through Traefik
print()
print("=== WEB PAGES (via Traefik :8080) ===")
pages = [
    ("Home", "/"),
    ("Chat", "/chat"),
    ("Dashboard", "/dashboard"),
    ("Skills", "/skills"),
    ("Memory", "/memory"),
    ("Heartbeat", "/heartbeat"),
    ("Logs", "/logs"),
    ("Models", "/models"),
    ("Model Usage", "/model-usage"),
]
for name, path in pages:
    try:
        body = get_raw(f"{WEB}{path}")
        title = body.split("<title>")[1].split("</title>")[0] if "<title>" in body else "no title"
        size = len(body)
        print(f"  OK   {name:15} title=\"{title}\"  ({size} bytes)")
    except Exception as e:
        print(f"  FAIL {name:15} {e}")

# 4. Key API endpoints
print()
print("=== KEY API ENDPOINTS ===")
endpoints = [
    ("GET", "/health"),
    ("GET", "/skills"),
    ("GET", "/skills/health/dashboard"),
    ("GET", "/skills/stats/summary"),
    ("GET", "/skills/coherence"),
    ("GET", "/skills/insights"),
    ("GET", "/engine/agents"),
    ("GET", "/engine/chat/sessions?limit=3"),
    ("GET", "/engine/roundtable"),
    ("GET", "/engine/roundtable/agents/available"),
    ("GET", "/engine/cron"),
    ("GET", "/engine/cron/status"),
    ("GET", "/engine/sessions/stats"),
    ("GET", "/models/available"),
    ("GET", "/litellm/models"),
    ("GET", "/litellm/global-spend"),
    ("GET", "/providers/balances"),
    ("GET", "/models/pricing"),
]
for method, path in endpoints:
    try:
        r = _request(f"{API}{path}", timeout=10)
        body = r.read().decode()[:200]
        print(f"  OK   {method} {path:45} => {body[:100]}")
    except Exception as e:
        err_body = ""
        if hasattr(e, "read"):
            err_body = e.read().decode()[:150]
        print(f"  FAIL {method} {path:45} => {e} {err_body}")

# 5. Check what Aria flagged
print()
print("=== ARIA-FLAGGED ISSUES ===")
# Test the specific skills that were failing
print("Testing removed skills (brainstorm, community, database, experiment, fact_check, model_switcher)...")
for skill_name in ["brainstorm", "community", "database", "experiment", "fact_check", "model_switcher"]:
    # Check if skill dir exists with skill.json
    try:
        import os
        skill_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "aria_skills", skill_name)
        manifest = os.path.join(skill_dir, "skill.json")
        init_file = os.path.join(skill_dir, "__init__.py")
        has_manifest = os.path.exists(manifest)
        has_init = os.path.exists(init_file)
        print(f"  {skill_name:20} manifest={has_manifest}  init={has_init}")
    except Exception as ex:
        print(f"  {skill_name:20} error: {ex}")
