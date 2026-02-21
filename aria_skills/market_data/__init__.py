# aria_skills/market_data.py
"""
Crypto market data skill.

Fetches and analyzes cryptocurrency market data.
"""
import os
from datetime import datetime, timezone
from typing import Any

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


@SkillRegistry.register
class MarketDataSkill(BaseSkill):
    """
    Cryptocurrency market data.
    
    Config:
        api_url: CoinGecko API URL (default: https://api.coingecko.com/api/v3)
        cache_ttl: Cache duration in seconds
    """
    
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._client: "httpx.AsyncClient" | None = None
        self._cache: dict[str, Any] = {}
        self._cache_time: dict[str, datetime] = {}
    
    @property
    def name(self) -> str:
        return "market_data"
    
    async def initialize(self) -> bool:
        """Initialize market data client."""
        if not HAS_HTTPX:
            self.logger.error("httpx not installed")
            self._status = SkillStatus.UNAVAILABLE
            return False
        
        api_url = self.config.config.get(
            "api_url",
            "https://api.coingecko.com/api/v3"
        ).rstrip("/")
        
        self._cache_ttl = self.config.config.get("cache_ttl", 60)
        
        self._client = httpx.AsyncClient(
            base_url=api_url,
            timeout=30,
            headers={"Accept": "application/json"},
        )
        
        self._status = SkillStatus.AVAILABLE
        self.logger.info("Market data skill initialized")
        return True
    
    async def health_check(self) -> SkillStatus:
        """Check API connectivity."""
        if not self._client:
            self._status = SkillStatus.UNAVAILABLE
            return self._status
        
        try:
            resp = await self._client.get("/ping")
            self._status = SkillStatus.AVAILABLE if resp.status_code == 200 else SkillStatus.ERROR
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            self._status = SkillStatus.ERROR
        
        return self._status
    
    def _cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid."""
        if key not in self._cache_time:
            return False
        age = (datetime.now(timezone.utc) - self._cache_time[key]).total_seconds()
        return age < self._cache_ttl
    
    async def get_price(
        self,
        coin_id: str,
        vs_currencies: str = "usd",
    ) -> SkillResult:
        """
        Get current price for a coin.
        
        Args:
            coin_id: CoinGecko coin ID (e.g., "bitcoin")
            vs_currencies: Target currency (default: "usd")
            
        Returns:
            SkillResult with price data
        """
        cache_key = f"price_{coin_id}_{vs_currencies}"
        
        if self._cache_valid(cache_key):
            return SkillResult.ok(self._cache[cache_key])
        
        try:
            resp = await self._client.get(
                "/simple/price",
                params={
                    "ids": coin_id,
                    "vs_currencies": vs_currencies,
                    "include_24hr_change": "true",
                    "include_market_cap": "true",
                },
            )
            resp.raise_for_status()
            
            data = resp.json()
            result = {
                "coin": coin_id,
                "currency": vs_currencies,
                "price": data[coin_id][vs_currencies],
                "change_24h": data[coin_id].get(f"{vs_currencies}_24h_change"),
                "market_cap": data[coin_id].get(f"{vs_currencies}_market_cap"),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            
            self._cache[cache_key] = result
            self._cache_time[cache_key] = datetime.now(timezone.utc)
            
            return SkillResult.ok(result)
            
        except Exception as e:
            return SkillResult.fail(f"Failed to get price: {e}")
    
    async def get_market_overview(
        self,
        vs_currency: str = "usd",
        limit: int = 10,
    ) -> SkillResult:
        """
        Get top coins by market cap.
        
        Args:
            vs_currency: Target currency
            limit: Number of coins to return
            
        Returns:
            SkillResult with market overview
        """
        cache_key = f"overview_{vs_currency}_{limit}"
        
        if self._cache_valid(cache_key):
            return SkillResult.ok(self._cache[cache_key])
        
        try:
            resp = await self._client.get(
                "/coins/markets",
                params={
                    "vs_currency": vs_currency,
                    "order": "market_cap_desc",
                    "per_page": limit,
                    "page": 1,
                    "sparkline": "false",
                },
            )
            resp.raise_for_status()
            
            coins = []
            for coin in resp.json():
                coins.append({
                    "id": coin["id"],
                    "symbol": coin["symbol"].upper(),
                    "name": coin["name"],
                    "price": coin["current_price"],
                    "market_cap": coin["market_cap"],
                    "rank": coin["market_cap_rank"],
                    "change_24h": coin["price_change_percentage_24h"],
                    "volume_24h": coin["total_volume"],
                })
            
            result = {
                "currency": vs_currency,
                "coins": coins,
                "total_market_cap": sum(c["market_cap"] or 0 for c in coins),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            
            self._cache[cache_key] = result
            self._cache_time[cache_key] = datetime.now(timezone.utc)
            
            return SkillResult.ok(result)
            
        except Exception as e:
            return SkillResult.fail(f"Failed to get market overview: {e}")
    
    async def get_coin_details(self, coin_id: str) -> SkillResult:
        """
        Get detailed information about a coin.
        
        Args:
            coin_id: CoinGecko coin ID
            
        Returns:
            SkillResult with coin details
        """
        cache_key = f"details_{coin_id}"
        
        if self._cache_valid(cache_key):
            return SkillResult.ok(self._cache[cache_key])
        
        try:
            resp = await self._client.get(
                f"/coins/{coin_id}",
                params={
                    "localization": "false",
                    "tickers": "false",
                    "market_data": "true",
                    "community_data": "false",
                    "developer_data": "false",
                },
            )
            resp.raise_for_status()
            
            data = resp.json()
            market_data = data.get("market_data", {})
            
            result = {
                "id": data["id"],
                "symbol": data["symbol"].upper(),
                "name": data["name"],
                "description": data.get("description", {}).get("en", "")[:500],
                "links": {
                    "homepage": data.get("links", {}).get("homepage", [None])[0],
                    "github": data.get("links", {}).get("repos_url", {}).get("github", [None])[0],
                },
                "market_data": {
                    "current_price_usd": market_data.get("current_price", {}).get("usd"),
                    "market_cap_usd": market_data.get("market_cap", {}).get("usd"),
                    "total_volume_usd": market_data.get("total_volume", {}).get("usd"),
                    "high_24h_usd": market_data.get("high_24h", {}).get("usd"),
                    "low_24h_usd": market_data.get("low_24h", {}).get("usd"),
                    "price_change_24h": market_data.get("price_change_24h"),
                    "price_change_percentage_24h": market_data.get("price_change_percentage_24h"),
                    "circulating_supply": market_data.get("circulating_supply"),
                    "total_supply": market_data.get("total_supply"),
                },
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            
            self._cache[cache_key] = result
            self._cache_time[cache_key] = datetime.now(timezone.utc)
            
            return SkillResult.ok(result)
            
        except Exception as e:
            return SkillResult.fail(f"Failed to get coin details: {e}")
    
    async def search_coins(self, query: str) -> SkillResult:
        """
        Search for coins.
        
        Args:
            query: Search query
            
        Returns:
            SkillResult with search results
        """
        try:
            resp = await self._client.get("/search", params={"query": query})
            resp.raise_for_status()
            
            data = resp.json()
            coins = [
                {
                    "id": c["id"],
                    "symbol": c["symbol"].upper(),
                    "name": c["name"],
                    "market_cap_rank": c.get("market_cap_rank"),
                }
                for c in data.get("coins", [])[:10]
            ]
            
            return SkillResult.ok({
                "query": query,
                "results": coins,
                "count": len(coins),
            })
            
        except Exception as e:
            return SkillResult.fail(f"Search failed: {e}")
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
