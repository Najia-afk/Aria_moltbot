"""Quick check which OpenRouter free models are available."""
import httpx

r = httpx.get("https://openrouter.ai/api/v1/models", timeout=30)
models = r.json()["data"]
free = [m for m in models if ":free" in m.get("id", "")]
for m in sorted(free, key=lambda x: x["id"]):
    mid = m["id"]
    ctx = m.get("context_length", "?")
    print(f"{mid:65s} ctx={ctx}")
print(f"\nTotal free models: {len(free)}")
