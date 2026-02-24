"""
Tests for the market_data skill (Layer 3 — domain).

Covers:
- Price fetching with mocked httpx
- Market overview
- Coin details
- Coin search
- Caching behavior
- Initialization without httpx
- Error handling
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from aria_skills.base import SkillConfig, SkillResult, SkillStatus
from aria_skills.market_data import MarketDataSkill


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_skill() -> MarketDataSkill:
    return MarketDataSkill(SkillConfig(name="market_data", config={
        "api_url": "https://api.coingecko.com/api/v3",
        "cache_ttl": 60,
    }))


def _mock_response(data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return resp


# ---------------------------------------------------------------------------
# Tests — Lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize():
    skill = _make_skill()
    ok = await skill.initialize()
    assert ok is True
    assert await skill.health_check() != SkillStatus.UNAVAILABLE
    await skill.close()


@pytest.mark.asyncio
async def test_initialize_no_httpx():
    skill = _make_skill()
    with patch("aria_skills.market_data.HAS_HTTPX", False):
        ok = await skill.initialize()
    assert ok is False
    assert skill._status == SkillStatus.UNAVAILABLE


# ---------------------------------------------------------------------------
# Tests — Price Fetching
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_price():
    skill = _make_skill()
    await skill.initialize()
    skill._client = AsyncMock()
    skill._client.get = AsyncMock(return_value=_mock_response({
        "bitcoin": {
            "usd": 65000.0,
            "usd_24h_change": 2.5,
            "usd_market_cap": 1300000000000.0,
        }
    }))

    result = await skill.get_price(coin_id="bitcoin", vs_currencies="usd")
    assert result.success
    assert result.data["price"] == 65000.0
    assert result.data["coin"] == "bitcoin"
    assert result.data["change_24h"] == 2.5
    await skill.close()


@pytest.mark.asyncio
async def test_get_price_cached():
    skill = _make_skill()
    await skill.initialize()
    skill._client = AsyncMock()
    skill._client.get = AsyncMock(return_value=_mock_response({
        "bitcoin": {"usd": 65000.0, "usd_24h_change": 2.5, "usd_market_cap": 1e12}
    }))

    # First call — cache miss
    await skill.get_price(coin_id="bitcoin")
    # Second call — cache hit
    result = await skill.get_price(coin_id="bitcoin")
    assert result.success
    # Only one HTTP call should have been made
    assert skill._client.get.await_count == 1
    await skill.close()


@pytest.mark.asyncio
async def test_get_price_api_error():
    skill = _make_skill()
    await skill.initialize()
    skill._client = AsyncMock()
    skill._client.get = AsyncMock(side_effect=Exception("Network error"))

    result = await skill.get_price(coin_id="bitcoin")
    assert not result.success
    assert "Network error" in (result.error or "")
    await skill.close()


# ---------------------------------------------------------------------------
# Tests — Market Overview
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_market_overview():
    skill = _make_skill()
    await skill.initialize()
    skill._client = AsyncMock()
    skill._client.get = AsyncMock(return_value=_mock_response([
        {
            "id": "bitcoin", "symbol": "btc", "name": "Bitcoin",
            "current_price": 65000, "market_cap": 1300000000000,
            "market_cap_rank": 1, "price_change_percentage_24h": 1.5,
            "total_volume": 50000000000,
        },
        {
            "id": "ethereum", "symbol": "eth", "name": "Ethereum",
            "current_price": 3500, "market_cap": 420000000000,
            "market_cap_rank": 2, "price_change_percentage_24h": -0.5,
            "total_volume": 20000000000,
        },
    ]))

    result = await skill.get_market_overview(vs_currency="usd", limit=2)
    assert result.success
    assert len(result.data["coins"]) == 2
    assert result.data["coins"][0]["symbol"] == "BTC"
    assert result.data["total_market_cap"] > 0
    await skill.close()


# ---------------------------------------------------------------------------
# Tests — Coin Details
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_coin_details():
    skill = _make_skill()
    await skill.initialize()
    skill._client = AsyncMock()
    skill._client.get = AsyncMock(return_value=_mock_response({
        "id": "bitcoin", "symbol": "btc", "name": "Bitcoin",
        "description": {"en": "A peer-to-peer electronic cash system."},
        "links": {"homepage": ["https://bitcoin.org"], "repos_url": {"github": ["https://github.com/bitcoin"]}},
        "market_data": {
            "current_price": {"usd": 65000},
            "market_cap": {"usd": 1300000000000},
            "total_volume": {"usd": 50000000000},
            "high_24h": {"usd": 66000},
            "low_24h": {"usd": 64000},
            "price_change_24h": 500,
            "price_change_percentage_24h": 0.77,
            "circulating_supply": 19600000,
            "total_supply": 21000000,
        },
    }))

    result = await skill.get_coin_details(coin_id="bitcoin")
    assert result.success
    assert result.data["symbol"] == "BTC"
    assert result.data["market_data"]["current_price_usd"] == 65000
    await skill.close()


# ---------------------------------------------------------------------------
# Tests — Search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_coins():
    skill = _make_skill()
    await skill.initialize()
    skill._client = AsyncMock()
    skill._client.get = AsyncMock(return_value=_mock_response({
        "coins": [
            {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin", "market_cap_rank": 1},
            {"id": "bitcoin-cash", "symbol": "bch", "name": "Bitcoin Cash", "market_cap_rank": 20},
        ]
    }))

    result = await skill.search_coins(query="bitcoin")
    assert result.success
    assert result.data["count"] == 2
    assert result.data["results"][0]["symbol"] == "BTC"
    await skill.close()


# ---------------------------------------------------------------------------
# Tests — Close
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_close():
    skill = _make_skill()
    await skill.initialize()
    await skill.close()
    assert skill._client is None
