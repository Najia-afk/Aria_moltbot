#!/usr/bin/env python3
"""Comprehensive test of the KG relationship fix + traversal improvements."""
import httpx
import sys

API = "http://localhost:8000/api"
c = httpx.Client(base_url=API, timeout=30)
passed = 0
failed = 0


def test(name, func):
    global passed, failed
    print(f"\nTEST: {name}")
    try:
        func()
        passed += 1
        print("  PASSED")
    except Exception as e:
        failed += 1
        print(f"  FAILED: {e}")


def test_create_entities():
    """Create 3 entities (properties avoid noise filter)."""
    for name, etype in [
        ("Kaelen Stormfire", "character"),
        ("Mirael Sunweave", "character"),
        ("Obsidian Citadel", "location"),
    ]:
        r = c.post("/knowledge-graph/entities", json={
            "name": name, "type": etype,
            "properties": {"origin": "campaign_s2"},
        })
        assert r.status_code == 200, f"Create {name}: {r.status_code} {r.text}"
        data = r.json()
        eid = data.get("id")
        assert eid and data.get("created"), f"Failed for {name}: {data}"
        print(f"  {name} -> {eid}")


def test_relation_by_name():
    """Create relation using entity names (the original bug)."""
    r = c.post("/knowledge-graph/relations", json={
        "from_entity": "Kaelen Stormfire",
        "to_entity": "Mirael Sunweave",
        "relation_type": "rivals_with",
    })
    assert r.status_code == 200 and r.json().get("created"), f"Failed: {r.status_code} {r.text}"
    print(f"  Relation id: {r.json()['id']}")


def test_relation_by_uuid():
    """Create relation using UUIDs (backward compat)."""
    r1 = c.get("/knowledge-graph/kg-search", params={"q": "Kaelen Stormfire"})
    r2 = c.get("/knowledge-graph/kg-search", params={"q": "Obsidian Citadel"})
    uid1 = r1.json()["results"][0]["id"]
    uid2 = r2.json()["results"][0]["id"]
    print(f"  UUID1: {uid1}, UUID2: {uid2}")
    r = c.post("/knowledge-graph/relations", json={
        "from_entity": uid1,
        "to_entity": uid2,
        "relation_type": "sieged",
    })
    assert r.status_code == 200 and r.json().get("created"), f"Failed: {r.status_code} {r.text}"
    print(f"  Relation id: {r.json()['id']}")


def test_relation_auto_create():
    """Create relation referencing a new entity that doesn't exist yet."""
    r = c.post("/knowledge-graph/relations", json={
        "from_entity": "Mirael Sunweave",
        "to_entity": "Voidborn Ritual",
        "relation_type": "performed",
    })
    assert r.status_code == 200 and r.json().get("created"), f"Failed: {r.status_code} {r.text}"
    print(f"  Auto-created Voidborn Ritual + relation: {r.json()['id']}")


def test_relation_case_insensitive():
    """Case-insensitive entity name resolution."""
    r = c.post("/knowledge-graph/relations", json={
        "from_entity": "kaelen stormfire",
        "to_entity": "obsidian citadel",
        "relation_type": "discovered",
    })
    assert r.status_code == 200 and r.json().get("created"), f"Failed: {r.status_code} {r.text}"
    print(f"  Relation id: {r.json()['id']}")


def test_kg_traverse():
    """BFS traversal on organic KG."""
    r = c.get("/knowledge-graph/kg-traverse", params={
        "start": "Kaelen Stormfire", "max_depth": 2, "direction": "both",
    })
    assert r.status_code == 200, f"Failed: {r.status_code} {r.text}"
    data = r.json()
    assert "error" not in data, f"Traverse error: {data.get('error')}"
    print(f"  Nodes: {data['total_nodes']}, Edges: {data['total_edges']}")
    for n in data.get("nodes", []):
        print(f"    node: {n.get('name')} ({n.get('type')})")
    for e in data.get("edges", []):
        print(f"    edge: {e.get('from_name', '?')} --[{e.get('relation_type')}]--> {e.get('to_name', '?')}")
    assert data["total_nodes"] >= 3, f"Expected >= 3 nodes, got {data['total_nodes']}"
    assert data["total_edges"] >= 3, f"Expected >= 3 edges, got {data['total_edges']}"


def test_kg_search():
    """ILIKE search on organic KG."""
    r = c.get("/knowledge-graph/kg-search", params={"q": "Kaelen"})
    assert r.status_code == 200, f"Failed: {r.status_code} {r.text}"
    data = r.json()
    print(f"  Results: {data['count']}")
    assert data["count"] >= 1
    names = [e.get("name") for e in data.get("results", [])]
    print(f"  Names: {names}")
    assert any("Kaelen" in str(n) for n in names)


def test_kg_search_by_type():
    """Search with type filter."""
    r = c.get("/knowledge-graph/kg-search", params={
        "q": "Obsidian", "entity_type": "location",
    })
    assert r.status_code == 200, f"Failed: {r.status_code} {r.text}"
    data = r.json()
    print(f"  Results for location/Obsidian: {data['count']}")
    assert data["count"] >= 1, f"Expected results, got 0"


def test_verify_graph():
    """Verify the graph has our relations via traversal."""
    r = c.get("/knowledge-graph/kg-traverse", params={
        "start": "Kaelen Stormfire", "max_depth": 2, "direction": "both",
    })
    assert r.status_code == 200
    data = r.json()
    edge_types = [e["relation_type"] for e in data.get("edges", [])]
    print(f"  Edge types: {edge_types}")
    for expected in ["rivals_with", "sieged", "discovered"]:
        assert expected in edge_types, f"Missing relation: {expected}"


# ── Run tests ───
test("Create entities", test_create_entities)
test("Relation by NAME (original bug)", test_relation_by_name)
test("Relation by UUID (backward compat)", test_relation_by_uuid)
test("Relation auto-create entity", test_relation_auto_create)
test("Relation case-insensitive", test_relation_case_insensitive)
test("KG traverse (BFS)", test_kg_traverse)
test("KG search", test_kg_search)
test("KG search by type", test_kg_search_by_type)
test("Verify graph structure", test_verify_graph)

print(f"\nRESULTS: {passed} passed, {failed} failed out of {passed + failed}")
sys.exit(1 if failed else 0)
