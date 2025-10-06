#!/usr/bin/env python3
"""Run backtest on historical Hyperliquid data."""

import argparse
from datetime import datetime, timedelta
from loguru import logger
from data_fetcher import DataFetcher
from backtester import Backtester
from backtest_report import BacktestReporter


def main():
    """Run backtest."""
    parser = argparse.ArgumentParser(
        description="Backtest Hyperliquid funding arbitrage strategy"
    )
    parser.add_argument(
        "--assets",
        type=str,
        default="BTC,ETH,HYPE",
        help="Comma-separated list of assets (default: BTC,ETH,HYPE)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to backtest (default: 30)"
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=10000,
        help="Initial capital in USD (default: 10000)"
    )
    parser.add_argument(
        "--funding-threshold",
        type=float,
        default=0.0001,
        help="Minimum funding rate to enter (default: 0.0001 = 0.01%%)"
    )
    parser.add_argument(
        "--max-position",
        type=float,
        default=5000,
        help="Max position size per asset (default: 5000)"
    )
    parser.add_argument(
        "--leverage",
        type=float,
        default=2.0,
        help="Leverage for perp positions (default: 2.0)"
    )
    parser.add_argument(
        "--fetch-data",
        action="store_true",
        help="Fetch fresh data from Hyperliquid API"
    )
    parser.add_argument(
        "--use-cached",
        action="store_true",
        help="Use cached data from backtest_data/ directory"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="backtest_results",
        help="Output directory for results (default: backtest_results)"
    )

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("HYPERLIQUID FUNDING ARBITRAGE BACKTEST")
    logger.info("=" * 80)

    assets = args.assets.split(",")
    end_time = datetime.now()
    start_time = end_time - timedelta(days=args.days)

    logger.info(f"Assets: {assets}")
    logger.info(f"Period: {start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}")
    logger.info(f"Initial Capital: ${args.capital:,.2f}")
    logger.info(f"Funding Threshold: {args.funding_threshold:.4%}")
    logger.info(f"Max Position: ${args.max_position:,.2f}")
    logger.info(f"Leverage: {args.leverage}x")

    # Fetch or load data
    if args.fetch_data:
        logger.info("\nFetching historical data from Hyperliquid...")
        fetcher = DataFetcher()
        historical_data = fetcher.fetch_backtest_data(assets, start_time, end_time)

        # Save for future use
        fetcher.save_to_csv(historical_data, "backtest_data")

    elif args.use_cached:
        logger.info("\nLoading cached data...")
        historical_data = load_cached_data(assets)
    else:
        logger.error("Must specify either --fetch-data or --use-cached")
        return

    if not historical_data:
        logger.error("No data available for backtesting")
        return

    # Validate data
    total_points = sum(len(points) for points in historical_data.values())
    logger.info(f"Loaded {total_points} total data points")

    for asset, points in historical_data.items():
        logger.info(f"  {asset}: {len(points)} data points")

    # Run backtest
    logger.info("\nRunning backtest...")
    backtester = Backtester(
        initial_capital=args.capital,
        funding_threshold=args.funding_threshold,
        max_position_size_usd=args.max_position,
        leverage=args.leverage
    )

    result = backtester.run(historical_data, check_interval_hours=8)

    # Generate report
    logger.info("\nGenerating report...")
    BacktestReporter.generate_full_report(result, args.output_dir)

    logger.info(f"\n✅ Backtest complete! Results saved to {args.output_dir}/")


def load_cached_data(assets):
    """Load cached data from CSV files.

    Args:
        assets: List of asset symbols

    Returns:
        Dictionary of asset to data points
    """
    import csv
    from data_fetcher import HistoricalDataPoint

    historical_data = {}

    for asset in assets:
        filename = f"backtest_data/{asset}_history.csv"
        try:
            with open(filename, 'r') as f:
                reader = csv.DictReader(f)
                data_points = []

                for row in reader:
                    data_points.append(HistoricalDataPoint(
                        timestamp=int(row['timestamp']),
                        asset=row['asset'],
                        funding_rate=float(row['funding_rate']),
                        mark_price=float(row['mark_price'])
                    ))

                historical_data[asset] = data_points
                logger.info(f"Loaded {len(data_points)} data points for {asset}")

        except FileNotFoundError:
            logger.warning(f"No cached data found for {asset} at {filename}")
        except Exception as e:
            logger.error(f"Error loading cached data for {asset}: {e}")

    return historical_data


if __name__ == "__main__":
    main()
