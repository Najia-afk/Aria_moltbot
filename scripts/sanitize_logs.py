import json
import os
import re

SRC = "aria_memories/logs"
DST = "aria_souvenirs/aria_v3_270226/logs"

files = sorted([
    f for f in os.listdir(SRC)
    if f.startswith("work_cycle_2026-02-2") and f.endswith(".json")
    and (f.startswith("work_cycle_2026-02-28") or
         any(x in f for x in ["2315", "2317", "2348", "2351", "2354"]))
])

SENSITIVE_KEYS = {"network", "ip", "host_ip", "public_ip"}

def sanitize(obj):
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items() if k not in SENSITIVE_KEYS}
    if isinstance(obj, list):
        return [sanitize(i) for i in obj]
    return obj

written = []
for fname in files:
    src_path = os.path.join(SRC, fname)
    dst_path = os.path.join(DST, fname)
    try:
        with open(src_path) as f:
            raw = f.read().strip()
        try:
            data = json.loads(raw)
            clean = sanitize(data)
            with open(dst_path, "w") as f:
                json.dump(clean, f, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            clean_raw = re.sub(r',?\s*"network"\s*:\s*"[^"]*"', '', raw)
            with open(dst_path, "w") as f:
                f.write(clean_raw)
        written.append(fname)
    except Exception as e:
        print(f"ERROR {fname}: {e}")

# test_write.json — the filesystem probe sentinel (safe)
with open(f"{DST}/test_write.json", "w") as f:
    json.dump({"test": True}, f)
written.append("test_write.json")

print(f"Written {len(written)} files:")
for w in written:
    print(f"  {w}")
