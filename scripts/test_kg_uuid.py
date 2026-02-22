#!/usr/bin/env python3
"""Quick UUID backward-compat test for KG relation fix."""
import httpx
import json

API = "http://localhost:8000/api"
c = httpx.Client(base_url=API, timeout=30)

# Create entities with non-test names
print("Creating entities...")
r1 = c.post("/knowledge-graph/entities", json={"name": "Thorin Ashveil", "type": "character", "properties": {"class": "fighter", "level": 1}})
print(f"  Entity A: {r1.status_code} -> {r1.json()}")
a_id = r1.json().get("id")

r2 = c.post("/knowledge-graph/entities", json={"name": "Seraphina Dawnblade", "type": "character", "properties": {"class": "paladin", "level": 1}})
print(f"  Entity B: {r2.status_code} -> {r2.json()}")
b_id = r2.json().get("id")

if a_id and b_id:
    # Test UUID-based relation (backward compat)
    print(f"\nCreating relation by UUID: {a_id} -> {b_id}")
    r3 = c.post("/knowledge-graph/relations", json={
        "from_entity": a_id,
        "to_entity": b_id,
        "relation_type": "allies_with",
    })
    print(f"  Relation by UUID: {r3.status_code} -> {r3.json()}")
    assert r3.status_code == 200 and r3.json().get("created"), "UUID relation failed"

    # Test name-based relation
    print(f"\nCreating relation by name: Thorin Ashveil -> Seraphina Dawnblade")
    r4 = c.post("/knowledge-graph/relations", json={
        "from_entity": "Thorin Ashveil",
        "to_entity": "Seraphina Dawnblade",
        "relation_type": "party_member",
    })
    print(f"  Relation by name: {r4.status_code} -> {r4.json()}")
    assert r4.status_code == 200 and r4.json().get("created"), "Name relation failed"

    print("\nAll backward compat tests PASSED")
else:
    print("Entities may already exist, trying name-based relation only...")
    r5 = c.post("/knowledge-graph/relations", json={
        "from_entity": "Thorin Ashveil",
        "to_entity": "Seraphina Dawnblade",
        "relation_type": "party_member",
    })
    print(f"  Relation by name: {r5.status_code} -> {r5.json()}")
