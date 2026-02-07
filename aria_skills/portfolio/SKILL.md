```skill
---
name: aria-portfolio
description: "💼 Portfolio and position management for Crypto Trader"
metadata: {"openclaw": {"emoji": "💼"}}
---
```

# aria-portfolio

Portfolio and position management. Open/close positions, track unrealized P&L, view trade history, calculate performance metrics, and check risk limits.

## Usage

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py portfolio <function> '<json_args>'
```

## Functions

### open_position
Open a new trading position.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py portfolio open_position '{"symbol": "BTC/USDT", "side": "long", "amount": 0.1}'
```

### close_position
Close an existing position.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py portfolio close_position '{"position_id": "abc", "reason": "take profit"}'
```

### get_positions
Get all open positions with unrealized P&L.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py portfolio get_positions '{}'
```

### get_trade_history
Get trade history.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py portfolio get_trade_history '{}'
```

### get_performance_metrics
Calculate portfolio performance metrics.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py portfolio get_performance_metrics '{}'
```

### check_risk_limits
Check if portfolio respects risk limits.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py portfolio check_risk_limits '{}'
```
