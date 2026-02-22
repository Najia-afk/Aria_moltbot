#!/usr/bin/env python3
"""Full duplicate audit of aria_souvenirs/"""
import os
import hashlib
from collections import defaultdict

ROOT = "/Users/najia/aria/aria_souvenirs"

# 1. Collect all files with their hashes and sizes
files = {}
for dirpath, dirnames, filenames in os.walk(ROOT):
    for fn in filenames:
        if fn.startswith('.'):
            continue
        fp = os.path.join(dirpath, fn)
        rel = os.path.relpath(fp, ROOT)
        sz = os.path.getsize(fp)
        with open(fp, 'rb') as f:
            h = hashlib.md5(f.read()).hexdigest()
        files[rel] = {"size": sz, "hash": h, "abs": fp}

print(f"Total files in aria_souvenirs: {len(files)}")
print()

# 2. Find exact content duplicates (same hash)
by_hash = defaultdict(list)
for rel, info in files.items():
    by_hash[info["hash"]].append(rel)

dupes = {h: paths for h, paths in by_hash.items() if len(paths) > 1}
if dupes:
    print(f"=== EXACT DUPLICATES (same content hash) === ({len(dupes)} groups)")
    print()
    for h, paths in sorted(dupes.items(), key=lambda x: -len(x[1])):
        sz = files[paths[0]]["size"]
        print(f"  Hash: {h}  Size: {sz:,} bytes  Copies: {len(paths)}")
        for p in sorted(paths):
            print(f"    - {p}")
        print()
else:
    print("=== NO EXACT DUPLICATES FOUND ===")
    print()

# 3. Find filename duplicates (same name, different paths)
by_name = defaultdict(list)
for rel in files:
    fn = os.path.basename(rel)
    by_name[fn].append(rel)

name_dupes = {fn: paths for fn, paths in by_name.items() if len(paths) > 1}
if name_dupes:
    print(f"=== FILENAME DUPLICATES (same name, possibly different content) === ({len(name_dupes)} groups)")
    print()
    for fn, paths in sorted(name_dupes.items()):
        same_content = len(set(files[p]["hash"] for p in paths)) == 1
        tag = "IDENTICAL" if same_content else "DIFFERENT CONTENT"
        print(f"  {fn}  [{tag}]")
        for p in sorted(paths):
            print(f"    - {p}  ({files[p]['size']:,} bytes)")
        print()
else:
    print("=== NO FILENAME DUPLICATES FOUND ===")
    print()

# 4. Look for cross-folder overlaps between versioned souvenirs
versions = [d for d in os.listdir(ROOT) if os.path.isdir(os.path.join(ROOT, d)) and d.startswith("aria_v")]
print(f"=== VERSION FOLDERS === ({len(versions)})")
for v in sorted(versions):
    vpath = os.path.join(ROOT, v)
    count = sum(1 for _, _, fs in os.walk(vpath) for f in fs if not f.startswith('.'))
    total_sz = sum(
        os.path.getsize(os.path.join(dp, fn))
        for dp, _, fns in os.walk(vpath) for fn in fns if not fn.startswith('.')
    )
    print(f"  {v}: {count} files, {total_sz:,} bytes")

# 5. Check for large files that might be wasteful
print()
print("=== LARGEST FILES (>50KB) ===")
large = [(rel, info) for rel, info in files.items() if info["size"] > 50000]
for rel, info in sorted(large, key=lambda x: -x[1]["size"]):
    print(f"  {info['size']:>10,} bytes  {rel}")

# 6. Summary
total_dup_bytes = sum(
    files[paths[0]]["size"] * (len(paths) - 1)
    for paths in dupes.values()
)
print()
print(f"=== SUMMARY ===")
print(f"Total files: {len(files)}")
print(f"Exact duplicate groups: {len(dupes)}")
print(f"Wasted bytes from duplicates: {total_dup_bytes:,}")
print(f"Filename collisions: {len(name_dupes)}")
