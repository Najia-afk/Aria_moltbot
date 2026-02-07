---
name: aria-marketdata
description: "📈 Cryptocurrency market data and analysis for Crypto Trader"
metadata: {"openclaw": {"emoji": "📈"}}
---

# aria-marketdata

Cryptocurrency market data and analysis. Get prices, OHLCV data, technical indicators, sentiment analysis, price alerts, and market overviews.

## Usage

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py market_data <function> '<json_args>'
```

## Functions

### get_price
Get current price for a trading pair.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py market_data get_price '{"symbol": "BTC/USDT"}'
```

### get_ohlcv
Get OHLCV candlestick data.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py market_data get_ohlcv '{"symbol": "BTC/USDT"}'
```

### calculate_indicators
Calculate technical indicators.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py market_data calculate_indicators '{"symbol": "BTC/USDT", "indicators": ["rsi", "macd"]}'
```

### analyze_sentiment
Analyze market sentiment for a symbol.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py market_data analyze_sentiment '{"symbol": "BTC"}'
```

### set_alert
Set a price alert.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py market_data set_alert '{"symbol": "BTC/USDT", "price": 50000, "direction": "above"}'
```

### get_market_overview
Get overall market overview.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py market_data get_market_overview '{}'
```
