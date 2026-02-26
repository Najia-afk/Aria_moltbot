#!/usr/bin/env python3
"""Test app_managed sync protection for models and agents."""
import json, os, urllib.request, urllib.error

API = "http://localhost:45669"
KEY = os.getenv("ARIA_API_KEY", "")

def req(method, path, data=None):
    url = API + path
    headers = {"Content-Type": "application/json"}
    if KEY:
        headers["X-API-Key"] = KEY
    body = json.dumps(data).encode() if data else None
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode()) if e.fp else {}

print("=" * 60)
print("  TEST: app_managed sync protection")
print("=" * 60)

# ── RESET: Force sync first to clear any leftover state ─────
print("\n── RESET ──")
s, d = req("POST", "/models/db/sync?force=true")
print(f"  Force-synced models: updated={d['updated']}")
s, d = req("POST", "/agents/db/sync?force=true")
print(f"  Force-synced agents: updated={d['updated']}")

# ── MODELS TEST ─────────────────────────────────────────────

print("\n── MODELS ──")

# 1. Check kimi before edit
s, d = req("GET", "/models/db/kimi")
print(f"1. Before edit:     name='{d['name']}', enabled={d['enabled']}, app_managed={d['app_managed']}")
assert d['app_managed'] == False, "Should start as False"

# 2. Edit via API
s, d = req("PUT", "/models/db/kimi", {"name": "Kimi CUSTOM", "enabled": False})
print(f"2. After API edit:  name='{d['name']}', enabled={d['enabled']}, app_managed={d['app_managed']}")
assert d['app_managed'] == True, "Should be True after API edit"
assert d['name'] == "Kimi CUSTOM", "Name should be changed"
assert d['enabled'] == False, "Should be disabled"

# 3. Sync from config (should skip kimi)
s, d = req("POST", "/models/db/sync")
print(f"3. Normal sync:     skipped={d.get('skipped', 0)}, updated={d['updated']}")
assert d.get('skipped', 0) >= 1, "Should skip at least 1 app_managed model"

# 4. Verify kimi was NOT overwritten
s, d = req("GET", "/models/db/kimi")
print(f"4. After sync:      name='{d['name']}', enabled={d['enabled']}, app_managed={d['app_managed']}")
assert d['name'] == "Kimi CUSTOM", "Name should still be custom"
assert d['enabled'] == False, "Should still be disabled"

# 5. Force sync (should overwrite)
s, d = req("POST", "/models/db/sync?force=true")
print(f"5. Force sync:      skipped={d.get('skipped', 0)}, updated={d['updated']}")
assert d.get('skipped', 0) == 0, "Force should skip nothing"

# 6. Verify kimi WAS overwritten
s, d = req("GET", "/models/db/kimi")
print(f"6. After force:     name='{d['name']}', enabled={d['enabled']}, app_managed={d['app_managed']}")
assert d['name'] != "Kimi CUSTOM", "Name should be back from config"
assert d['enabled'] == True, "Should be re-enabled from config"

print("\n  ✓ MODELS: All assertions passed!")

# ── AGENTS TEST ─────────────────────────────────────────────

print("\n── AGENTS ──")

# 1. Check analyst before edit
s, d = req("GET", "/agents/db/analyst")
print(f"1. Before edit:     model='{d['model']}', app_managed={d['app_managed']}")
original_model = d['model']
assert d['app_managed'] == False, "Should start as False"

# 2. Edit via API
s, d = req("PUT", "/agents/db/analyst", {"model": "custom-model-xyz"})
print(f"2. After API edit:  model='{d['model']}', app_managed={d['app_managed']}")
assert d['app_managed'] == True, "Should be True after API edit"
assert d['model'] == "custom-model-xyz", "Model should be changed"

# 3. Sync from config (should skip analyst)
s, d = req("POST", "/agents/db/sync")
print(f"3. Normal sync:     skipped={d.get('skipped', 0)}, updated={d['updated']}")
assert d.get('skipped', 0) >= 1, "Should skip at least 1 app_managed agent"

# 4. Verify analyst was NOT overwritten
s, d = req("GET", "/agents/db/analyst")
print(f"4. After sync:      model='{d['model']}', app_managed={d['app_managed']}")
assert d['model'] == "custom-model-xyz", "Model should still be custom"

# 5. Force sync (should overwrite)
s, d = req("POST", "/agents/db/sync?force=true")
print(f"5. Force sync:      skipped={d.get('skipped', 0)}, updated={d['updated']}")
assert d.get('skipped', 0) == 0, "Force should skip nothing"

# 6. Verify analyst WAS overwritten
s, d = req("GET", "/agents/db/analyst")
print(f"6. After force:     model='{d['model']}', app_managed={d['app_managed']}")
assert d['model'] == original_model, f"Model should be back to '{original_model}'"

print("\n  ✓ AGENTS: All assertions passed!")

print("\n" + "=" * 60)
print("  ALL TESTS PASSED")
print("=" * 60)
