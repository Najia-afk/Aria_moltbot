"""Quick check of recent skill failures."""
import urllib.request
import json
import os

BASE = os.getenv("ARIA_API_URL", "http://localhost:8080/api")
API_KEY = os.getenv("ARIA_API_KEY", "")


def _open(url: str):
    headers = {"X-API-Key": API_KEY} if API_KEY else {}
    req = urllib.request.Request(url, headers=headers)
    return urllib.request.urlopen(req)

def check_stats(skill_name):
    url = f"{BASE}/skills/stats/{skill_name}"
    try:
        r = _open(url)
        data = json.loads(r.read())
        invocations = data.get("invocations", [])
        failures = [x for x in invocations if not x.get("success", True)]
        print(f"\n=== {skill_name}: {len(failures)} failures of {data.get('total',0)} ===")
        for x in failures[:3]:
            # Print all keys to see what data is available
            print(f"  KEYS: {list(x.keys())}")
            print(f"  FULL: {json.dumps(x, default=str)[:300]}")
    except Exception as e:
        print(f"\n=== {skill_name}: {e} ===")

def check_api_client_methods():
    """Check what methods api_client has as tools."""
    url = f"{BASE}/skills/coherence"
    try:
        r = _open(url)
        data = json.loads(r.read())
        for s in data.get("skills", []):
            name = s.get("skill", "")
            if name == "api_client":
                print("\n=== api_client ===")
                for t in s.get("tools", []):
                    print(f"  {t}")
                return
        print("\napi_client not found")
    except Exception as e:
        print(f"coherence error: {e}")

check_api_client_methods()
for s in ["data_pipeline", "unified_search", "llm", "sandbox"]:
    check_stats(s)
