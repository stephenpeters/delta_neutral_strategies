# Backtesting Guide

## Overview

The backtesting framework simulates the funding arbitrage strategy on historical Hyperliquid data to evaluate performance before risking real capital.

## Quick Start

### 1. Fetch Historical Data

First, fetch historical funding rates and prices from Hyperliquid:

```bash
# Fetch last 30 days of data for BTC, ETH, and HYPE
python run_backtest.py --fetch-data --days 30

# Fetch last 90 days with custom assets
python run_backtest.py --fetch-data --days 90 --assets BTC,ETH,SOL
```

This saves data to `backtest_data/` directory for reuse.

### 2. Run Backtest

Run the backtest on cached or freshly fetched data:

```bash
# Using cached data
python run_backtest.py --use-cached

# Fetch fresh data and run backtest
python run_backtest.py --fetch-data --days 60

# Custom parameters
python run_backtest.py --use-cached \
  --capital 50000 \
  --funding-threshold 0.0002 \
  --max-position 10000 \
  --leverage 3
```

### 3. View Results

Results are saved to `backtest_results/` directory:

- **Terminal output**: Summary statistics
- **trades.csv**: All trades executed
- **positions.csv**: Position-level details
- **equity_curve.png**: Capital over time
- **funding_distribution.png**: Histogram of funding collected
- **returns_by_asset.png**: Performance breakdown by asset

## Backtesting Parameters

### Strategy Parameters

- `--capital`: Initial capital (default: $10,000)
- `--funding-threshold`: Minimum funding rate to enter position (default: 0.01%)
- `--max-position`: Max position size per asset (default: $5,000)
- `--leverage`: Leverage for perpetual positions (default: 2x)

### Data Parameters

- `--assets`: Comma-separated list of assets (default: BTC,ETH,HYPE)
- `--days`: Historical period to test (default: 30 days)
- `--fetch-data`: Fetch fresh data from Hyperliquid API
- `--use-cached`: Use previously fetched data from `backtest_data/`

### Output Parameters

- `--output-dir`: Directory for results (default: `backtest_results`)

## Understanding Results

### Performance Metrics

- **Total Return**: Absolute profit/loss in USD
- **Total Return %**: Percentage return on initial capital
- **Annualized Return**: Return extrapolated to annual basis
- **Funding Collected**: Total funding payments received

### Trading Statistics

- **Win Rate**: Percentage of profitable positions
- **Avg PnL per Trade**: Average profit/loss per position
- **Avg Funding per Trade**: Average funding collected per position

### Risk Metrics

- **Max Drawdown**: Maximum peak-to-trough decline
- **Sharpe Ratio**: Risk-adjusted return metric (higher is better)
  - < 1: Poor
  - 1-2: Good
  - 2-3: Very good
  - \> 3: Excellent

## Example Workflows

### Test Different Funding Thresholds

```bash
# Conservative: Only enter on high funding rates
python run_backtest.py --use-cached --funding-threshold 0.0005

# Moderate (default)
python run_backtest.py --use-cached --funding-threshold 0.0001

# Aggressive: Enter on any positive funding
python run_backtest.py --use-cached --funding-threshold 0.00001
```

### Test Different Leverage Levels

```bash
# Conservative
python run_backtest.py --use-cached --leverage 1.5

# Moderate (default)
python run_backtest.py --use-cached --leverage 2

# Aggressive
python run_backtest.py --use-cached --leverage 5
```

### Test Different Time Periods

```bash
# Recent performance (last month)
python run_backtest.py --fetch-data --days 30

# Medium-term (last quarter)
python run_backtest.py --fetch-data --days 90

# Long-term (last year)
python run_backtest.py --fetch-data --days 365
```

## Backtest Architecture

### Components

1. **[data_fetcher.py](data_fetcher.py)**: Fetches historical funding rates and prices from Hyperliquid API
2. **[backtester.py](backtester.py)**: Core simulation engine that replays strategy on historical data
3. **[backtest_report.py](backtest_report.py)**: Generates reports, charts, and CSV exports
4. **[run_backtest.py](run_backtest.py)**: CLI entry point for running backtests

### How It Works

1. **Data Collection**: Fetches 8-hour funding rate snapshots and hourly price data
2. **Simulation**: Replays strategy decisions at each funding period
   - Checks funding rates across all assets
   - Opens positions when funding exceeds threshold
   - Collects funding payments (8-hour rate)
   - Closes positions when funding flips or drops below threshold
3. **Accounting**: Tracks capital, positions, fees, and PnL
4. **Analysis**: Calculates performance metrics and generates visualizations

### Assumptions

- **Trading Fees**: 0.02% per trade (2 bps maker/taker)
- **Funding Periods**: 8 hours (matches Hyperliquid)
- **No Slippage**: Executes at mark price (conservative for backtests)
- **Delta Neutral**: Assumes perfect hedging (spot + perp cancel price risk)

## Limitations

1. **Historical Performance ≠ Future Results**: Past funding rates don't predict future rates
2. **Market Impact**: Real executions may experience slippage on large orders
3. **Funding Rate Changes**: Rates can change between collection periods
4. **Spot Market Proxy**: Current implementation uses perps for both sides; production should use actual spot
5. **Liquidation Risk**: Backtest doesn't fully simulate margin calls during extreme moves

## Tips for Effective Backtesting

1. **Test Multiple Periods**: Run backtests on different time periods (bull, bear, sideways markets)
2. **Parameter Sensitivity**: Test how results change with different parameters
3. **Conservative Assumptions**: Use realistic fees and slippage estimates
4. **Walk-Forward Testing**: Test on one period, validate on another
5. **Paper Trade First**: After backtesting, use `--dry-run` mode on live strategy before real capital

## Troubleshooting

### No data fetched

- Check internet connection
- Verify asset symbols are correct (use uppercase: BTC, ETH, HYPE)
- Try reducing the date range (--days parameter)

### Import errors

```bash
pip install -r requirements.txt
```

### Plots not generating

Install matplotlib:
```bash
pip install matplotlib
```

### Low returns in backtest

- Funding rates may have been low during test period
- Try longer time periods or different assets
- Adjust `--funding-threshold` to be more aggressive
