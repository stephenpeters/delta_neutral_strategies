# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A delta-neutral funding arbitrage trading strategy for Hyperliquid. The bot automatically captures funding rate inefficiencies by maintaining balanced positions across spot and perpetual futures markets.

**Strategy**:
- Long spot / Short perp when funding rate is positive (longs pay shorts)
- Short spot / Long perp when funding rate is negative (shorts pay longs)
- Maintains delta-neutral positions to eliminate directional price risk

## Development Commands

```bash
# Install dependencies
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configuration
cp .env.example .env
# Edit .env with your Hyperliquid credentials

# Backtesting (always start here!)
python run_backtest.py --fetch-data --days 30  # Fetch historical data
python run_backtest.py --use-cached            # Run backtest on cached data

# Live Trading
python main.py --dry-run        # Dry-run mode (no real trades)
python main.py                  # Live trading
python main.py --interval 600   # Custom check interval
python main.py --log-level DEBUG  # Debug logging
```

## Architecture

### Component Structure

- **[hyperliquid_client.py](hyperliquid_client.py)**: Low-level API wrapper for Hyperliquid exchange
  - Handles funding rates, positions, orders, and account data
  - Uses official `hyperliquid-python-sdk`

- **[funding_monitor.py](funding_monitor.py)**: Tracks funding rates and generates trading signals
  - Calculates expected APR from funding rates
  - Determines position signals (long spot/short perp or vice versa)
  - Identifies best opportunities across multiple assets

- **[position_manager.py](position_manager.py)**: Manages delta-neutral positions
  - Opens/closes positions across spot and perp markets
  - Rebalances positions to maintain delta neutrality
  - Tracks position state (spot size, perp size, entry price)

- **[risk_manager.py](risk_manager.py)**: Risk controls and liquidation protection
  - Monitors distance to liquidation
  - Validates position sizes based on account value
  - Checks slippage on executions
  - Emergency close functionality

- **[strategy.py](strategy.py)**: Main orchestrator that ties everything together
  - Runs periodic iterations to check opportunities
  - Manages existing positions (exit signals, rebalancing)
  - Enters new positions when opportunities arise
  - Monitors account health

- **[config.py](config.py)**: Configuration management using Pydantic
  - Loads settings from environment variables
  - Validates configuration parameters

- **[main.py](main.py)**: Entry point with CLI interface

### Backtesting Components

- **[data_fetcher.py](data_fetcher.py)**: Fetches historical funding rates and prices from Hyperliquid API
- **[backtester.py](backtester.py)**: Simulation engine that replays strategy on historical data
- **[backtest_report.py](backtest_report.py)**: Generates performance reports and visualizations
- **[run_backtest.py](run_backtest.py)**: CLI for running backtests

See [BACKTEST_README.md](BACKTEST_README.md) for detailed backtesting guide.

### Key Concepts

**Delta Neutrality**: Net delta = spot_size + perp_size ≈ 0. This isolates funding rate returns from directional price movements.

**Funding Rate**: 8-hour rate paid between longs and shorts. Annualized to estimate APR (rate × 3 periods/day × 365 days).

**Risk Parameters**:
- `FUNDING_RATE_THRESHOLD`: Minimum funding rate to enter (default: 0.01%)
- `REBALANCE_THRESHOLD`: Rebalance when delta exceeds 5% of position
- `LIQUIDATION_BUFFER`: Keep liquidation price 30% away
- `MAX_SLIPPAGE`: Maximum acceptable slippage (0.1%)

### Important Notes

1. **Spot Market Proxy**: Current implementation uses perp positions for both sides since Hyperliquid spot markets require additional setup. In production, replace with actual spot market orders.

2. **Leverage Management**: Conservative 2x leverage by default. Higher leverage increases returns but also liquidation risk.

3. **Position Sizing**: Limited to 80% of account value per position to maintain margin buffer.

4. **Dry Run Mode**: Always test with `--dry-run` first before live trading.

5. **Logs**: Strategy logs are stored in `logs/` directory with daily rotation.
