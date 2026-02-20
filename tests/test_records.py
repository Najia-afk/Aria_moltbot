"""Records, Export, and Search endpoint tests."""
import pytest


class TestRecords:
    def test_list_records(self, api):
        r = api.get("/records")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (dict, list))

    def test_export(self, api):
        r = api.get("/export")
        assert r.status_code == 200

    def test_search(self, api):
        r = api.get("/search", params={"q": "test"})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (dict, list))

    def test_search_empty_query(self, api):
        r = api.get("/search", params={"q": ""})
        assert r.status_code in (200, 422)
