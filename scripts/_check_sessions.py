import urllib.request, json

# Exactly what browser fetches when checkbox IS ticked
url_with = "http://localhost:8000/engine/sessions?limit=200&sort=updated_at&order=desc"
# Exactly what browser fetches when checkbox NOT ticked
url_without = "http://localhost:8000/engine/sessions?limit=200&sort=updated_at&order=desc&exclude_agent_sessions=true"

with urllib.request.urlopen(url_with) as r:
    d_with = json.load(r)
with urllib.request.urlopen(url_without) as r:
    d_without = json.load(r)

s_with = d_with.get("sessions", [])
s_without = d_without.get("sessions", [])

types_with = {}
for s in s_with:
    t = s.get("session_type") or "interactive"
    types_with[t] = types_with.get(t, 0) + 1

print(f"Checkbox TICKED   → API returns {len(s_with)} sessions (total_in_db={d_with.get('total')}): {types_with}")
print(f"Checkbox UNTICKED → API returns {len(s_without)} sessions (total_in_db={d_without.get('total')})")
print()
print("Last 5 in checkbox-ticked result (should be cron at bottom):")
for s in s_with[-5:]:
    print(f"  [{s.get('session_type'):12}] {s.get('updated_at','')[:16]}  {(s.get('title') or 'Untitled')[:50]}")
