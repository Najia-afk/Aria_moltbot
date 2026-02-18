# aria_skills/portfolio.py
"""
Portfolio management skill.

Tracks and manages cryptocurrency portfolios.
"""
from datetime import datetime, timezone
from typing import Any

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry


@SkillRegistry.register
class PortfolioSkill(BaseSkill):
    """
    Portfolio tracking and management.
    
    Manages positions, tracks P&L, and provides portfolio analytics.
    """
    
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._positions: dict[str, Dict] = {}
        self._transactions: list[Dict] = []
    
    @property
    def name(self) -> str:
        return "portfolio"
    
    async def initialize(self) -> bool:
        """Initialize portfolio skill."""
        # TODO: TICKET-12 - stub requires API endpoint for portfolio persistence.
        # Currently in-memory only. Needs POST/GET /api/portfolio endpoints.
        self.logger.warning("portfolio skill is in-memory only — API endpoint not yet available")
        self._status = SkillStatus.AVAILABLE
        self.logger.info("Portfolio skill initialized")
        return True
    
    async def health_check(self) -> SkillStatus:
        """Check availability."""
        return self._status
    
    async def add_position(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
        notes: str | None = None,
    ) -> SkillResult:
        """
        Add or update a position.
        
        Args:
            symbol: Asset symbol (e.g., "BTC")
            quantity: Amount held
            entry_price: Average entry price
            notes: Optional notes
            
        Returns:
            SkillResult with position data
        """
        symbol = symbol.upper()
        
        if symbol in self._positions:
            # Update existing position (average in)
            existing = self._positions[symbol]
            total_quantity = existing["quantity"] + quantity
            total_cost = (existing["quantity"] * existing["entry_price"]) + (quantity * entry_price)
            avg_price = total_cost / total_quantity
            
            existing["quantity"] = total_quantity
            existing["entry_price"] = avg_price
            existing["updated_at"] = datetime.now(timezone.utc).isoformat()
        else:
            # Create new position
            self._positions[symbol] = {
                "symbol": symbol,
                "quantity": quantity,
                "entry_price": entry_price,
                "notes": notes,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        
        # Log transaction
        self._transactions.append({
            "type": "buy",
            "symbol": symbol,
            "quantity": quantity,
            "price": entry_price,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
        return SkillResult.ok(self._positions[symbol])
    
    async def remove_position(
        self,
        symbol: str,
        quantity: float | None = None,
        exit_price: float | None = None,
    ) -> SkillResult:
        """
        Remove or reduce a position.
        
        Args:
            symbol: Asset symbol
            quantity: Amount to remove (None = all)
            exit_price: Sale price for P&L calculation
            
        Returns:
            SkillResult with P&L if price provided
        """
        symbol = symbol.upper()
        
        if symbol not in self._positions:
            return SkillResult.fail(f"No position in {symbol}")
        
        position = self._positions[symbol]
        remove_qty = quantity or position["quantity"]
        
        if remove_qty > position["quantity"]:
            return SkillResult.fail(f"Cannot remove {remove_qty}, only have {position['quantity']}")
        
        # Calculate P&L if exit price provided
        pnl = None
        pnl_percent = None
        if exit_price:
            pnl = (exit_price - position["entry_price"]) * remove_qty
            pnl_percent = ((exit_price / position["entry_price"]) - 1) * 100
        
        # Log transaction
        self._transactions.append({
            "type": "sell",
            "symbol": symbol,
            "quantity": remove_qty,
            "price": exit_price,
            "pnl": pnl,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
        # Update or remove position
        if remove_qty >= position["quantity"]:
            del self._positions[symbol]
            remaining = 0
        else:
            position["quantity"] -= remove_qty
            position["updated_at"] = datetime.now(timezone.utc).isoformat()
            remaining = position["quantity"]
        
        return SkillResult.ok({
            "symbol": symbol,
            "removed_quantity": remove_qty,
            "remaining_quantity": remaining,
            "exit_price": exit_price,
            "pnl": round(pnl, 2) if pnl else None,
            "pnl_percent": round(pnl_percent, 2) if pnl_percent else None,
        })
    
    async def get_position(self, symbol: str) -> SkillResult:
        """Get a specific position."""
        symbol = symbol.upper()
        
        if symbol not in self._positions:
            return SkillResult.fail(f"No position in {symbol}")
        
        return SkillResult.ok(self._positions[symbol])
    
    async def get_portfolio(self, current_prices: dict[str, float] | None = None) -> SkillResult:
        """
        Get full portfolio with optional current valuations.
        
        Args:
            current_prices: Dict of symbol: current_price for valuation
            
        Returns:
            SkillResult with portfolio summary
        """
        positions = []
        total_value = 0
        total_cost = 0
        
        for symbol, pos in self._positions.items():
            cost = pos["quantity"] * pos["entry_price"]
            total_cost += cost
            
            position_data = {
                "symbol": symbol,
                "quantity": pos["quantity"],
                "entry_price": pos["entry_price"],
                "cost_basis": round(cost, 2),
            }
            
            if current_prices and symbol in current_prices:
                current = current_prices[symbol]
                value = pos["quantity"] * current
                pnl = value - cost
                pnl_percent = ((current / pos["entry_price"]) - 1) * 100
                
                position_data.update({
                    "current_price": current,
                    "current_value": round(value, 2),
                    "pnl": round(pnl, 2),
                    "pnl_percent": round(pnl_percent, 2),
                })
                total_value += value
            
            positions.append(position_data)
        
        result = {
            "positions": positions,
            "position_count": len(positions),
            "total_cost_basis": round(total_cost, 2),
        }
        
        if current_prices:
            total_pnl = total_value - total_cost
            result.update({
                "total_value": round(total_value, 2),
                "total_pnl": round(total_pnl, 2),
                "total_pnl_percent": round((total_pnl / total_cost) * 100, 2) if total_cost > 0 else 0,
            })
        
        return SkillResult.ok(result)
    
    async def get_transactions(self, limit: int = 20, symbol: str | None = None) -> SkillResult:
        """
        Get transaction history.
        
        Args:
            limit: Maximum transactions to return
            symbol: Filter by symbol
            
        Returns:
            SkillResult with transactions
        """
        transactions = self._transactions
        
        if symbol:
            symbol = symbol.upper()
            transactions = [t for t in transactions if t["symbol"] == symbol]
        
        return SkillResult.ok({
            "transactions": transactions[-limit:],
            "total": len(transactions),
        })
    
    async def get_summary(self) -> SkillResult:
        """Get portfolio summary statistics."""
        total_buys = sum(1 for t in self._transactions if t["type"] == "buy")
        total_sells = sum(1 for t in self._transactions if t["type"] == "sell")
        
        realized_pnl = sum(t.get("pnl", 0) or 0 for t in self._transactions if t["type"] == "sell")
        
        return SkillResult.ok({
            "active_positions": len(self._positions),
            "total_transactions": len(self._transactions),
            "buys": total_buys,
            "sells": total_sells,
            "realized_pnl": round(realized_pnl, 2),
            "symbols_held": list(self._positions.keys()),
        })
