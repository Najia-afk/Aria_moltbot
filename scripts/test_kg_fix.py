#!/usr/bin/env python3
"""Test script for the KG relationship creation fix."""
import httpx
import json
import sys

API = "http://localhost:8000/api"
c = httpx.Client(base_url=API, timeout=30)
passed = 0
failed = 0


def test(name, func):
    global passed, failed
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    try:
        func()
        passed += 1
        print(f"  PASSED")
    except Exception as e:
        failed += 1
        print(f"  FAILED: {e}")


def test_create_entity_a():
    r = c.post("/knowledge-graph/entities", json={
        "name": "KG_Test_Najia",
        "type": "person",
        "properties": {"role": "creator"},
    })
    assert r.status_code == 200, f"Status {r.status_code}: {r.text}"
    data = r.json()
    print(f"  Response: {json.dumps(data, indent=2)}")
    assert data.get("id") or data.get("created"), f"No ID: {data}"
    global entity_a_id
    entity_a_id = data.get("id")


def test_create_entity_b():
    r = c.post("/knowledge-graph/entities", json={
        "name": "KG_Test_Aria",
        "type": "ai_agent",
        "properties": {"version": "2.0"},
    })
    assert r.status_code == 200, f"Status {r.status_code}: {r.text}"
    data = r.json()
    print(f"  Response: {json.dumps(data, indent=2)}")
    assert data.get("id") or data.get("created"), f"No ID: {data}"
    global entity_b_id
    entity_b_id = data.get("id")


def test_relation_by_name():
    """THE BIG FIX: create relation using entity names, not UUIDs."""
    r = c.post("/knowledge-graph/relations", json={
        "from_entity": "KG_Test_Najia",
        "to_entity": "KG_Test_Aria",
        "relation_type": "created",
    })
    print(f"  Status: {r.status_code}")
    print(f"  Response: {json.dumps(r.json(), indent=2)}")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    assert r.json().get("created") is True, f"Not created: {r.json()}"


def test_relation_by_uuid():
    """Backward compat: UUIDs still work."""
    if not entity_a_id or not entity_b_id:
        print("  Skipped: no entity IDs")
        return
    r = c.post("/knowledge-graph/relations", json={
        "from_entity": entity_a_id,
        "to_entity": entity_b_id,
        "relation_type": "maintains",
    })
    print(f"  Status: {r.status_code}")
    print(f"  Response: {json.dumps(r.json(), indent=2)}")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    assert r.json().get("created") is True, f"Not created: {r.json()}"


def test_relation_auto_create():
    """Auto-create: entity that doesnt exist yet gets created on the fly."""
    r = c.post("/knowledge-graph/relations", json={
        "from_entity": "KG_Test_Najia",
        "to_entity": "KG_Test_NewConcept",
        "relation_type": "discovered",
    })
    print(f"  Status: {r.status_code}")
    print(f"  Response: {json.dumps(r.json(), indent=2)}")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    assert r.json().get("created") is True, f"Not created: {r.json()}"


def test_relation_case_insensitive():
    """Case-insensitive name matching."""
    r = c.post("/knowledge-graph/relations", json={
        "from_entity": "kg_test_aria",
        "to_entity": "kg_test_najia",
        "relation_type": "serves",
    })
    print(f"  Status: {r.status_code}")
    print(f"  Response: {json.dumps(r.json(), indent=2)}")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    assert r.json().get("created") is True, f"Not created: {r.json()}"


def test_verify_relations():
    """Verify all test relations exist in the graph."""
    r = c.get("/knowledge-graph/relations")
    assert r.status_code == 200
    rels = r.json().get("relations", [])
    test_rels = [
        rel for rel in rels
        if "KG_Test" in rel.get("from_name", "") or "KG_Test" in rel.get("to_name", "")
    ]
    for rel in test_rels:
        print(f"  {rel.get('from_name')} --[{rel.get('relation_type')}]--> {rel.get('to_name')}")
    print(f"  Total test relations: {len(test_rels)}")
    assert len(test_rels) >= 4, f"Expected >= 4 relations, got {len(test_rels)}"


entity_a_id = None
entity_b_id = None

test("Create entity A", test_create_entity_a)
test("Create entity B", test_create_entity_b)
test("Relation by NAME (the fix)", test_relation_by_name)
test("Relation by UUID (backward compat)", test_relation_by_uuid)
test("Relation auto-create entity", test_relation_auto_create)
test("Relation case-insensitive", test_relation_case_insensitive)
test("Verify all relations", test_verify_relations)

print(f"\n{'='*60}")
print(f"RESULTS: {passed} passed, {failed} failed")
print(f"{'='*60}")
sys.exit(1 if failed else 0)
