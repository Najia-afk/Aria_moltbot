"""Providers endpoint tests."""
import pytest


class TestProviders:
    def test_balances(self, api):
        r = api.get("/providers/balances")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (dict, list))
