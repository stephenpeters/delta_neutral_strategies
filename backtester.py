"""Backtesting engine for funding arbitrage strategy."""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger
from data_fetcher import HistoricalDataPoint
from funding_monitor import PositionSignal


@dataclass
class BacktestPosition:
    """Position during backtest."""
    asset: str
    entry_time: int
    entry_price: float
    size: float
    signal: PositionSignal
    spot_size: float
    perp_size: float
    exit_time: Optional[int] = None
    exit_price: Optional[float] = None
    funding_collected: float = 0.0
    pnl: float = 0.0


@dataclass
class BacktestTrade:
    """Single trade record."""
    timestamp: int
    asset: str
    action: str  # 'open' or 'close'
    price: float
    size: float
    signal: Optional[PositionSignal] = None


@dataclass
class BacktestResult:
    """Results from a backtest run."""
    start_time: int
    end_time: int
    initial_capital: float
    final_capital: float
    total_return: float
    total_return_pct: float
    funding_collected: float
    num_trades: int
    num_winning_trades: int
    num_losing_trades: int
    win_rate: float
    max_drawdown: float
    sharpe_ratio: float
    positions: List[BacktestPosition] = field(default_factory=list)
    trades: List[BacktestTrade] = field(default_factory=list)
    equity_curve: List[Tuple[int, float]] = field(default_factory=list)


class Backtester:
    """Backtest the funding arbitrage strategy."""

    def __init__(
        self,
        initial_capital: float = 10000,
        funding_threshold: float = 0.0001,
        max_position_size_usd: float = 5000,
        leverage: float = 2.0,
        rebalance_threshold: float = 0.05,
        trading_fee: float = 0.0002  # 0.02% per trade
    ):
        """Initialize backtester.

        Args:
            initial_capital: Starting capital in USD
            funding_threshold: Minimum funding rate to enter
            max_position_size_usd: Max position size per asset
            leverage: Leverage for perp positions
            rebalance_threshold: When to rebalance
            trading_fee: Trading fee per trade (maker/taker)
        """
        self.initial_capital = initial_capital
        self.funding_threshold = funding_threshold
        self.max_position_size_usd = max_position_size_usd
        self.leverage = leverage
        self.rebalance_threshold = rebalance_threshold
        self.trading_fee = trading_fee

        self.capital = initial_capital
        self.positions: Dict[str, BacktestPosition] = {}
        self.trades: List[BacktestTrade] = []
        self.equity_curve: List[Tuple[int, float]] = []

    def run(
        self,
        historical_data: Dict[str, List[HistoricalDataPoint]],
        check_interval_hours: int = 8
    ) -> BacktestResult:
        """Run backtest on historical data.

        Args:
            historical_data: Map of asset to historical data points
            check_interval_hours: Hours between strategy checks (default: 8, matches funding)

        Returns:
            BacktestResult object
        """
        logger.info(f"Starting backtest with ${self.initial_capital} capital")

        # Flatten and sort all data points by timestamp
        all_points = []
        for asset, points in historical_data.items():
            all_points.extend(points)
        all_points.sort(key=lambda x: x.timestamp)

        if not all_points:
            logger.error("No historical data provided")
            return self._create_result(0, 0)

        start_time = all_points[0].timestamp
        end_time = all_points[-1].timestamp

        # Group data by timestamp (approximately)
        data_by_time: Dict[int, Dict[str, HistoricalDataPoint]] = {}
        for point in all_points:
            # Round to nearest 8 hours
            interval_ms = check_interval_hours * 3600 * 1000
            rounded_time = (point.timestamp // interval_ms) * interval_ms

            if rounded_time not in data_by_time:
                data_by_time[rounded_time] = {}
            data_by_time[rounded_time][point.asset] = point

        # Run simulation
        timestamps = sorted(data_by_time.keys())
        for ts in timestamps:
            market_data = data_by_time[ts]
            self._process_timestamp(ts, market_data)

        # Close all remaining positions at end
        for asset in list(self.positions.keys()):
            if asset in market_data:
                self._close_position(asset, ts, market_data[asset].mark_price)

        # Generate results
        return self._create_result(start_time, end_time)

    def _process_timestamp(
        self,
        timestamp: int,
        market_data: Dict[str, HistoricalDataPoint]
    ):
        """Process one timestamp in the backtest.

        Args:
            timestamp: Current timestamp
            market_data: Market data for all assets at this time
        """
        # 1. Update existing positions (collect funding, check exit)
        for asset in list(self.positions.keys()):
            if asset not in market_data:
                continue

            data_point = market_data[asset]
            self._update_position(asset, timestamp, data_point)

        # 2. Look for new opportunities
        opportunities = []
        for asset, data_point in market_data.items():
            if asset in self.positions:
                continue  # Already have position

            signal = self._get_signal(data_point.funding_rate)
            if signal != PositionSignal.NO_SIGNAL:
                opportunities.append((asset, data_point, signal))

        # Sort by funding rate (best opportunities first)
        opportunities.sort(
            key=lambda x: abs(x[1].funding_rate),
            reverse=True
        )

        # Enter best opportunities (if we have capital)
        for asset, data_point, signal in opportunities:
            if self._can_open_position():
                self._open_position(asset, timestamp, data_point, signal)

        # Track equity
        equity = self._calculate_equity(timestamp, market_data)
        self.equity_curve.append((timestamp, equity))

    def _get_signal(self, funding_rate: float) -> PositionSignal:
        """Get position signal from funding rate."""
        if funding_rate > self.funding_threshold:
            return PositionSignal.LONG_SPOT_SHORT_PERP
        elif funding_rate < -self.funding_threshold:
            return PositionSignal.SHORT_SPOT_LONG_PERP
        else:
            return PositionSignal.NO_SIGNAL

    def _can_open_position(self) -> bool:
        """Check if can open new position."""
        # Conservative: only use 80% of capital for positions
        max_positions = int((self.capital * 0.8) / self.max_position_size_usd)
        return len(self.positions) < max(1, max_positions)

    def _open_position(
        self,
        asset: str,
        timestamp: int,
        data_point: HistoricalDataPoint,
        signal: PositionSignal
    ):
        """Open a new position."""
        size_usd = min(self.max_position_size_usd, self.capital * 0.8)
        size = size_usd / data_point.mark_price

        # Calculate trading fees (open both spot and perp)
        fees = size_usd * self.trading_fee * 2  # Both sides
        self.capital -= fees

        if signal == PositionSignal.LONG_SPOT_SHORT_PERP:
            spot_size = size
            perp_size = -size
        else:
            spot_size = -size
            perp_size = size

        position = BacktestPosition(
            asset=asset,
            entry_time=timestamp,
            entry_price=data_point.mark_price,
            size=size,
            signal=signal,
            spot_size=spot_size,
            perp_size=perp_size
        )

        self.positions[asset] = position
        self.trades.append(BacktestTrade(
            timestamp=timestamp,
            asset=asset,
            action='open',
            price=data_point.mark_price,
            size=size,
            signal=signal
        ))

        logger.debug(
            f"[{datetime.fromtimestamp(timestamp/1000)}] "
            f"OPEN {asset} @ ${data_point.mark_price:.2f}, "
            f"Funding: {data_point.funding_rate:.4%}, Signal: {signal.value}"
        )

    def _update_position(
        self,
        asset: str,
        timestamp: int,
        data_point: HistoricalDataPoint
    ):
        """Update position (collect funding, check exit)."""
        position = self.positions[asset]

        # Collect funding (8-hour rate)
        funding_pnl = self._calculate_funding_pnl(position, data_point.funding_rate)
        position.funding_collected += funding_pnl
        self.capital += funding_pnl

        # Check if should exit
        new_signal = self._get_signal(data_point.funding_rate)

        # Exit if signal flipped or no signal
        should_exit = (
            new_signal != position.signal or
            new_signal == PositionSignal.NO_SIGNAL
        )

        if should_exit:
            self._close_position(asset, timestamp, data_point.mark_price)

    def _calculate_funding_pnl(
        self,
        position: BacktestPosition,
        funding_rate: float
    ) -> float:
        """Calculate funding PnL for a position.

        For long spot/short perp: we receive funding when rate is positive
        For short spot/long perp: we receive funding when rate is negative
        """
        position_value = abs(position.perp_size) * position.entry_price

        if position.signal == PositionSignal.LONG_SPOT_SHORT_PERP:
            # Short perp receives funding when rate is positive
            return position_value * funding_rate if funding_rate > 0 else 0
        else:
            # Long perp pays funding when rate is positive (receives when negative)
            return -position_value * funding_rate if funding_rate > 0 else position_value * abs(funding_rate)

    def _close_position(self, asset: str, timestamp: int, price: float):
        """Close a position."""
        if asset not in self.positions:
            return

        position = self.positions[asset]

        # Calculate price PnL (should be ~0 for delta neutral)
        price_change = price - position.entry_price
        price_pnl = position.spot_size * price_change + position.perp_size * price_change

        # Trading fees for closing
        size_usd = abs(position.size) * price
        fees = size_usd * self.trading_fee * 2  # Both sides

        total_pnl = position.funding_collected + price_pnl - fees
        position.pnl = total_pnl
        position.exit_time = timestamp
        position.exit_price = price

        self.capital += total_pnl

        self.trades.append(BacktestTrade(
            timestamp=timestamp,
            asset=asset,
            action='close',
            price=price,
            size=position.size
        ))

        logger.debug(
            f"[{datetime.fromtimestamp(timestamp/1000)}] "
            f"CLOSE {asset} @ ${price:.2f}, "
            f"PnL: ${total_pnl:.2f} (Funding: ${position.funding_collected:.2f})"
        )

        del self.positions[asset]

    def _calculate_equity(
        self,
        timestamp: int,
        market_data: Dict[str, HistoricalDataPoint]
    ) -> float:
        """Calculate current equity including unrealized PnL."""
        equity = self.capital

        for asset, position in self.positions.items():
            if asset in market_data:
                current_price = market_data[asset].mark_price
                price_change = current_price - position.entry_price
                unrealized_pnl = position.spot_size * price_change + position.perp_size * price_change
                equity += unrealized_pnl + position.funding_collected

        return equity

    def _create_result(self, start_time: int, end_time: int) -> BacktestResult:
        """Create backtest result summary."""
        total_return = self.capital - self.initial_capital
        total_return_pct = total_return / self.initial_capital

        # Calculate statistics
        winning_trades = sum(1 for t in self.trades if t.action == 'close')
        # This is simplified - need to track actual wins/losses
        closed_positions = [p for p in self.positions.values() if p.exit_time is not None]
        num_winning = sum(1 for p in closed_positions if p.pnl > 0)
        num_losing = sum(1 for p in closed_positions if p.pnl < 0)
        win_rate = num_winning / max(1, len(closed_positions))

        # Calculate max drawdown
        max_drawdown = self._calculate_max_drawdown()

        # Calculate Sharpe ratio (simplified)
        sharpe = self._calculate_sharpe_ratio()

        total_funding = sum(p.funding_collected for p in closed_positions)

        return BacktestResult(
            start_time=start_time,
            end_time=end_time,
            initial_capital=self.initial_capital,
            final_capital=self.capital,
            total_return=total_return,
            total_return_pct=total_return_pct,
            funding_collected=total_funding,
            num_trades=len([t for t in self.trades if t.action == 'open']),
            num_winning_trades=num_winning,
            num_losing_trades=num_losing,
            win_rate=win_rate,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe,
            positions=closed_positions,
            trades=self.trades,
            equity_curve=self.equity_curve
        )

    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown."""
        if not self.equity_curve:
            return 0.0

        peak = self.equity_curve[0][1]
        max_dd = 0.0

        for _, equity in self.equity_curve:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak
            max_dd = max(max_dd, dd)

        return max_dd

    def _calculate_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio (simplified)."""
        if len(self.equity_curve) < 2:
            return 0.0

        returns = []
        for i in range(1, len(self.equity_curve)):
            prev_equity = self.equity_curve[i-1][1]
            curr_equity = self.equity_curve[i][1]
            ret = (curr_equity - prev_equity) / prev_equity
            returns.append(ret)

        if not returns:
            return 0.0

        import statistics
        avg_return = statistics.mean(returns)
        std_return = statistics.stdev(returns) if len(returns) > 1 else 0

        if std_return == 0:
            return 0.0

        # Annualize (assuming 8-hour periods)
        periods_per_year = 365 * 3  # 3 periods per day
        sharpe = (avg_return * periods_per_year) / (std_return * (periods_per_year ** 0.5))

        return sharpe
