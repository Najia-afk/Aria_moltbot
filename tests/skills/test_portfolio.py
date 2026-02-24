"""
Tests for the portfolio skill (Layer 3 — domain).

Covers:
- Initialization
- Add position (new and update existing)
- Remove position (full and partial, with P&L)
- Get position / portfolio / transactions / summary
"""
from __future__ import annotations

import pytest

from aria_skills.base import SkillConfig, SkillResult, SkillStatus
from aria_skills.portfolio import PortfolioSkill


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_skill() -> PortfolioSkill:
    return PortfolioSkill(SkillConfig(name="portfolio"))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize():
    skill = _make_skill()
    ok = await skill.initialize()
    assert ok is True
    assert await skill.health_check() == SkillStatus.AVAILABLE


@pytest.mark.asyncio
async def test_add_position():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.add_position(symbol="BTC", quantity=1.5, entry_price=40000)
    assert result.success
    assert result.data["symbol"] == "BTC"
    assert result.data["quantity"] == 1.5
    assert result.data["entry_price"] == 40000


@pytest.mark.asyncio
async def test_add_position_updates_existing():
    skill = _make_skill()
    await skill.initialize()
    await skill.add_position(symbol="ETH", quantity=10, entry_price=2000)
    result = await skill.add_position(symbol="ETH", quantity=10, entry_price=3000)
    assert result.success
    assert result.data["quantity"] == 20
    assert result.data["entry_price"] == 2500  # Average of 2000 and 3000


@pytest.mark.asyncio
async def test_remove_position_full():
    skill = _make_skill()
    await skill.initialize()
    await skill.add_position(symbol="BTC", quantity=2, entry_price=30000)
    result = await skill.remove_position(symbol="BTC", exit_price=40000)
    assert result.success
    assert result.data["remaining_quantity"] == 0
    assert result.data["pnl"] == 20000  # (40000 - 30000) * 2


@pytest.mark.asyncio
async def test_remove_position_partial():
    skill = _make_skill()
    await skill.initialize()
    await skill.add_position(symbol="SOL", quantity=100, entry_price=50)
    result = await skill.remove_position(symbol="SOL", quantity=50, exit_price=100)
    assert result.success
    assert result.data["remaining_quantity"] == 50
    assert result.data["pnl"] == 2500  # (100 - 50) * 50


@pytest.mark.asyncio
async def test_remove_position_not_found():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.remove_position(symbol="DOGE")
    assert not result.success


@pytest.mark.asyncio
async def test_remove_position_exceeds_quantity():
    skill = _make_skill()
    await skill.initialize()
    await skill.add_position(symbol="ADA", quantity=10, entry_price=1)
    result = await skill.remove_position(symbol="ADA", quantity=20)
    assert not result.success


@pytest.mark.asyncio
async def test_get_position():
    skill = _make_skill()
    await skill.initialize()
    await skill.add_position(symbol="BTC", quantity=1, entry_price=50000)
    result = await skill.get_position(symbol="btc")  # lowercase should work
    assert result.success
    assert result.data["symbol"] == "BTC"


@pytest.mark.asyncio
async def test_get_position_not_found():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.get_position(symbol="XRP")
    assert not result.success


@pytest.mark.asyncio
async def test_get_portfolio():
    skill = _make_skill()
    await skill.initialize()
    await skill.add_position(symbol="BTC", quantity=1, entry_price=50000)
    await skill.add_position(symbol="ETH", quantity=10, entry_price=3000)

    result = await skill.get_portfolio(current_prices={"BTC": 60000, "ETH": 4000})
    assert result.success
    assert result.data["position_count"] == 2
    assert result.data["total_value"] == 100000  # 60000 + 40000
    assert result.data["total_pnl"] == 20000  # (60000-50000) + (40000-30000)


@pytest.mark.asyncio
async def test_get_transactions():
    skill = _make_skill()
    await skill.initialize()
    await skill.add_position(symbol="BTC", quantity=1, entry_price=50000)
    await skill.remove_position(symbol="BTC", exit_price=55000)

    result = await skill.get_transactions()
    assert result.success
    assert result.data["total"] == 2  # One buy + one sell


@pytest.mark.asyncio
async def test_get_summary():
    skill = _make_skill()
    await skill.initialize()
    await skill.add_position(symbol="BTC", quantity=1, entry_price=50000)
    await skill.add_position(symbol="ETH", quantity=5, entry_price=2000)
    await skill.remove_position(symbol="BTC", exit_price=55000)

    result = await skill.get_summary()
    assert result.success
    assert result.data["buys"] == 2
    assert result.data["sells"] == 1
    assert result.data["realized_pnl"] == 5000  # (55000-50000)*1
    assert "ETH" in result.data["symbols_held"]
