# Hyperliquid Funding Arbitrage Strategy

A delta-neutral trading strategy that captures funding rate inefficiencies on Hyperliquid by maintaining balanced positions across spot and perpetual futures markets.

## Strategy Overview

This bot implements a market-neutral funding arbitrage strategy:
- **Long spot / Short perp** when funding rate is positive
- **Short spot / Long perp** when funding rate is negative
- Maintains delta-neutral positions to eliminate directional price risk
- Real-time rebalancing to preserve neutrality
- Liquidation-aware position management

## Installation

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

1. Copy `.env.example` to `.env`
2. Add your Hyperliquid private key and account address
3. Adjust strategy parameters (funding thresholds, position sizes, etc.)

## Usage

```bash
# Run the strategy
python main.py

# Dry run mode (no actual trades)
python main.py --dry-run
```

## Risk Warnings

- This strategy involves leverage and perpetual futures trading
- Always start with small position sizes
- Monitor liquidation risks carefully
- Funding rates can change rapidly
- Test thoroughly on testnet first

## Architecture

- `hyperliquid_client.py` - API wrapper for Hyperliquid
- `funding_monitor.py` - Tracks funding rates across assets
- `position_manager.py` - Manages delta-neutral positions
- `risk_manager.py` - Liquidation protection and risk controls
- `strategy.py` - Main strategy orchestrator
- `config.py` - Configuration management
