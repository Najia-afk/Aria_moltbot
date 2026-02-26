import json
import os
import urllib.request

BASE = os.getenv("ARIA_API_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("ARIA_API_KEY", "")


def get_json(path: str):
    headers = {"X-API-Key": API_KEY} if API_KEY else {}
    req = urllib.request.Request(BASE + path, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


lst = get_json("/api/engine/roundtable?page=1&page_size=100")
items = lst.get("items", [])
ids = {
    "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa01": "roundtable",
    "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa02": "swarm",
}
found = [
    {
        "session_id": item.get("session_id"),
        "session_type": item.get("session_type"),
        "title": item.get("title"),
    }
    for item in items
    if item.get("session_id") in ids
]

rt = get_json("/api/engine/roundtable/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa01")
sw = get_json("/api/engine/roundtable/swarm/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa02")

print(json.dumps({
    "history_found": found,
    "roundtable_detail": {
        "session_id": rt.get("session_id"),
        "turn_count": rt.get("turn_count"),
        "topic": rt.get("topic"),
    },
    "swarm_detail": {
        "session_id": sw.get("session_id"),
        "vote_count": sw.get("vote_count"),
        "topic": sw.get("topic"),
    },
}, indent=2))
