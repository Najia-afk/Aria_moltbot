#!/usr/bin/env python
"""Verify skill-related endpoints after cleanup and backfill."""
import urllib.request, json

def get(path):
    r = urllib.request.urlopen(f"http://localhost:8000{path}", timeout=10)
    return json.loads(r.read().decode())

# 1. Skill stats
data = get("/skills/stats?hours=720")
print("=== /skills/stats ===")
print(f"Skills: {len(data['stats'])}")
for s in data["stats"]:
    print(f"  {s['skill_name']:20} calls={s['total']:3d}  err={s['error_rate']:.1%}  avg={s['avg_duration_ms']}ms  tokens={s['total_tokens']}")

# 2. Skill insights
print()
data = get("/skills/insights?hours=720&limit=100")
s = data["summary"]
print("=== /skills/insights ===")
print(f"Total: {s['total_invocations']}  Success: {s['success_rate']}%  Avg: {s['avg_duration_ms']}ms  Skills: {s['unique_skills']}  Tools: {s['unique_tools']}")
for sk in data["by_skill"][:5]:
    print(f"  {sk['skill_name']:20} inv={sk['invocations']}  err_rate={sk['error_rate']}%")

# 3. Model-usage stats
print()
data = get("/model-usage/stats?hours=720")
src = data.get("sources", {})
print("=== /model-usage/stats ===")
print(f"Total: {data['total_requests']}  Skills: {src.get('skills',{}).get('requests',0)}  LiteLLM: {src.get('litellm',{}).get('requests',0)}")
by_model = data.get("by_model", [])
skill_models = [m for m in by_model if m.get("source") == "skills"]
llm_models = [m for m in by_model if m.get("source") != "skills"]
print(f"  LLM models: {len(llm_models)}  Skill models: {len(skill_models)}")

# 4. Skill health dashboard
print()
data = get("/skills/health/dashboard?hours=720")
o = data["overall"]
print("=== /skills/health/dashboard ===")
print(f"Score: {o['health_score']}  Status: {o['status']}  Skills: {o['skills_monitored']}  Calls: {o['total_invocations']}")
for sk in data["skills"][:5]:
    print(f"  {sk['skill_name']:20} score={sk['health_score']}  status={sk['status']}  calls={sk['total_calls']}  err={sk['error_rate']}%")

print("\n=== DONE ===")
