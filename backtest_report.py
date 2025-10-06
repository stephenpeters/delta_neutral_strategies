"""Generate backtest reports and visualizations."""

from typing import Optional
from datetime import datetime
from loguru import logger
from backtester import BacktestResult


class BacktestReporter:
    """Generate reports from backtest results."""

    @staticmethod
    def print_summary(result: BacktestResult):
        """Print a summary of backtest results.

        Args:
            result: BacktestResult object
        """
        start_dt = datetime.fromtimestamp(result.start_time / 1000)
        end_dt = datetime.fromtimestamp(result.end_time / 1000)
        duration_days = (result.end_time - result.start_time) / (1000 * 86400)

        print("\n" + "=" * 80)
        print("BACKTEST RESULTS")
        print("=" * 80)
        print(f"\nPeriod: {start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d')}")
        print(f"Duration: {duration_days:.1f} days")
        print(f"\n{'PERFORMANCE METRICS':-^80}")
        print(f"Initial Capital:        ${result.initial_capital:,.2f}")
        print(f"Final Capital:          ${result.final_capital:,.2f}")
        print(f"Total Return:           ${result.total_return:,.2f} ({result.total_return_pct:+.2%})")
        print(f"Funding Collected:      ${result.funding_collected:,.2f}")

        # Annualized return
        years = duration_days / 365
        annualized_return = (result.total_return_pct / years) if years > 0 else 0
        print(f"Annualized Return:      {annualized_return:.2%}")

        print(f"\n{'TRADING STATISTICS':-^80}")
        print(f"Total Trades:           {result.num_trades}")
        print(f"Winning Trades:         {result.num_winning_trades}")
        print(f"Losing Trades:          {result.num_losing_trades}")
        print(f"Win Rate:               {result.win_rate:.2%}")

        print(f"\n{'RISK METRICS':-^80}")
        print(f"Max Drawdown:           {result.max_drawdown:.2%}")
        print(f"Sharpe Ratio:           {result.sharpe_ratio:.2f}")

        # Average trade metrics
        if result.positions:
            avg_pnl = sum(p.pnl for p in result.positions) / len(result.positions)
            avg_funding = sum(p.funding_collected for p in result.positions) / len(result.positions)

            print(f"\n{'AVERAGE TRADE':-^80}")
            print(f"Avg PnL per Trade:      ${avg_pnl:.2f}")
            print(f"Avg Funding per Trade:  ${avg_funding:.2f}")

        # Best and worst trades
        if result.positions:
            best_trade = max(result.positions, key=lambda p: p.pnl)
            worst_trade = min(result.positions, key=lambda p: p.pnl)

            print(f"\n{'BEST/WORST TRADES':-^80}")
            print(f"Best Trade:  {best_trade.asset} - ${best_trade.pnl:,.2f}")
            print(f"Worst Trade: {worst_trade.asset} - ${worst_trade.pnl:,.2f}")

        print("\n" + "=" * 80 + "\n")

    @staticmethod
    def save_trades_csv(result: BacktestResult, filename: str = "backtest_trades.csv"):
        """Save trade history to CSV.

        Args:
            result: BacktestResult object
            filename: Output filename
        """
        import csv

        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'datetime', 'asset', 'action', 'price',
                'size', 'signal'
            ])

            for trade in result.trades:
                dt = datetime.fromtimestamp(trade.timestamp / 1000)
                writer.writerow([
                    trade.timestamp,
                    dt.isoformat(),
                    trade.asset,
                    trade.action,
                    trade.price,
                    trade.size,
                    trade.signal.value if trade.signal else ''
                ])

        logger.info(f"Saved {len(result.trades)} trades to {filename}")

    @staticmethod
    def save_positions_csv(result: BacktestResult, filename: str = "backtest_positions.csv"):
        """Save position history to CSV.

        Args:
            result: BacktestResult object
            filename: Output filename
        """
        import csv

        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'asset', 'entry_time', 'exit_time', 'entry_price', 'exit_price',
                'size', 'signal', 'funding_collected', 'pnl', 'duration_hours'
            ])

            for pos in result.positions:
                entry_dt = datetime.fromtimestamp(pos.entry_time / 1000)
                exit_dt = datetime.fromtimestamp(pos.exit_time / 1000) if pos.exit_time else None
                duration_hours = (pos.exit_time - pos.entry_time) / (1000 * 3600) if pos.exit_time else 0

                writer.writerow([
                    pos.asset,
                    entry_dt.isoformat(),
                    exit_dt.isoformat() if exit_dt else '',
                    pos.entry_price,
                    pos.exit_price or '',
                    pos.size,
                    pos.signal.value,
                    pos.funding_collected,
                    pos.pnl,
                    duration_hours
                ])

        logger.info(f"Saved {len(result.positions)} positions to {filename}")

    @staticmethod
    def plot_equity_curve(result: BacktestResult, filename: str = "equity_curve.png"):
        """Plot equity curve.

        Args:
            result: BacktestResult object
            filename: Output filename
        """
        try:
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates

            timestamps = [datetime.fromtimestamp(t / 1000) for t, _ in result.equity_curve]
            equity = [e for _, e in result.equity_curve]

            plt.figure(figsize=(12, 6))
            plt.plot(timestamps, equity, linewidth=2)
            plt.axhline(y=result.initial_capital, color='r', linestyle='--',
                       label=f'Initial Capital: ${result.initial_capital:,.0f}')

            plt.title('Equity Curve', fontsize=16, fontweight='bold')
            plt.xlabel('Date', fontsize=12)
            plt.ylabel('Equity ($)', fontsize=12)
            plt.grid(True, alpha=0.3)
            plt.legend()

            # Format x-axis
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            plt.gcf().autofmt_xdate()

            plt.tight_layout()
            plt.savefig(filename, dpi=150)
            plt.close()

            logger.info(f"Saved equity curve to {filename}")

        except ImportError:
            logger.warning("matplotlib not installed, skipping plot")

    @staticmethod
    def plot_funding_distribution(result: BacktestResult, filename: str = "funding_distribution.png"):
        """Plot distribution of funding collected.

        Args:
            result: BacktestResult object
            filename: Output filename
        """
        try:
            import matplotlib.pyplot as plt

            funding_per_position = [p.funding_collected for p in result.positions]

            plt.figure(figsize=(10, 6))
            plt.hist(funding_per_position, bins=30, edgecolor='black', alpha=0.7)
            plt.axvline(x=0, color='r', linestyle='--', linewidth=2)

            plt.title('Funding Collected Distribution', fontsize=16, fontweight='bold')
            plt.xlabel('Funding Collected ($)', fontsize=12)
            plt.ylabel('Number of Positions', fontsize=12)
            plt.grid(True, alpha=0.3)

            plt.tight_layout()
            plt.savefig(filename, dpi=150)
            plt.close()

            logger.info(f"Saved funding distribution to {filename}")

        except ImportError:
            logger.warning("matplotlib not installed, skipping plot")

    @staticmethod
    def plot_returns_by_asset(result: BacktestResult, filename: str = "returns_by_asset.png"):
        """Plot returns breakdown by asset.

        Args:
            result: BacktestResult object
            filename: Output filename
        """
        try:
            import matplotlib.pyplot as plt
            from collections import defaultdict

            # Aggregate by asset
            asset_returns = defaultdict(float)
            asset_funding = defaultdict(float)

            for pos in result.positions:
                asset_returns[pos.asset] += pos.pnl
                asset_funding[pos.asset] += pos.funding_collected

            assets = sorted(asset_returns.keys())
            returns = [asset_returns[a] for a in assets]
            funding = [asset_funding[a] for a in assets]

            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

            # Total returns by asset
            ax1.bar(assets, returns, edgecolor='black', alpha=0.7)
            ax1.axhline(y=0, color='r', linestyle='--', linewidth=1)
            ax1.set_title('Total Returns by Asset', fontsize=14, fontweight='bold')
            ax1.set_xlabel('Asset', fontsize=12)
            ax1.set_ylabel('Total Return ($)', fontsize=12)
            ax1.grid(True, alpha=0.3, axis='y')

            # Funding collected by asset
            ax2.bar(assets, funding, color='green', edgecolor='black', alpha=0.7)
            ax2.set_title('Funding Collected by Asset', fontsize=14, fontweight='bold')
            ax2.set_xlabel('Asset', fontsize=12)
            ax2.set_ylabel('Funding Collected ($)', fontsize=12)
            ax2.grid(True, alpha=0.3, axis='y')

            plt.tight_layout()
            plt.savefig(filename, dpi=150)
            plt.close()

            logger.info(f"Saved returns by asset to {filename}")

        except ImportError:
            logger.warning("matplotlib not installed, skipping plot")

    @staticmethod
    def generate_full_report(
        result: BacktestResult,
        output_dir: str = "backtest_results"
    ):
        """Generate complete backtest report with all outputs.

        Args:
            result: BacktestResult object
            output_dir: Output directory
        """
        import os
        os.makedirs(output_dir, exist_ok=True)

        # Print summary
        BacktestReporter.print_summary(result)

        # Save CSVs
        BacktestReporter.save_trades_csv(
            result,
            f"{output_dir}/trades.csv"
        )
        BacktestReporter.save_positions_csv(
            result,
            f"{output_dir}/positions.csv"
        )

        # Generate plots
        BacktestReporter.plot_equity_curve(
            result,
            f"{output_dir}/equity_curve.png"
        )
        BacktestReporter.plot_funding_distribution(
            result,
            f"{output_dir}/funding_distribution.png"
        )
        BacktestReporter.plot_returns_by_asset(
            result,
            f"{output_dir}/returns_by_asset.png"
        )

        logger.info(f"Full backtest report saved to {output_dir}/")
