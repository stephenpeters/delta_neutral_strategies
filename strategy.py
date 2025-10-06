"""Main funding arbitrage strategy orchestrator."""

import time
from typing import Dict, List
from loguru import logger
from config import StrategyConfig
from hyperliquid_client import HyperliquidClient
from funding_monitor import FundingMonitor, PositionSignal
from position_manager import PositionManager
from risk_manager import RiskManager


class FundingArbStrategy:
    """Hyperliquid funding arbitrage strategy."""

    def __init__(self, config: StrategyConfig, dry_run: bool = False):
        """Initialize strategy.

        Args:
            config: Strategy configuration
            dry_run: If True, don't execute actual trades
        """
        self.config = config
        self.dry_run = dry_run

        # Initialize components
        logger.info("Initializing Hyperliquid Funding Arbitrage Strategy")

        self.client = HyperliquidClient(
            private_key=config.private_key,
            account_address=config.account_address
        )

        self.funding_monitor = FundingMonitor(
            client=self.client,
            funding_threshold=config.funding_rate_threshold
        )

        self.position_manager = PositionManager(
            client=self.client,
            max_position_size_usd=config.max_position_size_usd,
            rebalance_threshold=config.rebalance_threshold,
            leverage=config.leverage
        )

        self.risk_manager = RiskManager(
            client=self.client,
            liquidation_buffer=config.liquidation_buffer,
            max_slippage=config.max_slippage
        )

        self.running = False

        if self.dry_run:
            logger.warning("RUNNING IN DRY RUN MODE - No actual trades will be executed")

    def start(self, check_interval: int = 300):
        """Start the strategy.

        Args:
            check_interval: Interval between checks in seconds (default: 5 minutes)
        """
        logger.info(f"Starting strategy with {len(self.config.assets)} assets: {self.config.assets}")
        logger.info(f"Check interval: {check_interval}s")

        self.running = True

        try:
            while self.running:
                self._run_iteration()
                logger.info(f"Sleeping for {check_interval}s...")
                time.sleep(check_interval)

        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
            self.stop()

        except Exception as e:
            logger.error(f"Unexpected error in strategy loop: {e}")
            self.stop()

    def stop(self):
        """Stop the strategy."""
        logger.info("Stopping strategy...")
        self.running = False

    def _run_iteration(self):
        """Run one iteration of the strategy."""
        try:
            logger.info("=" * 80)
            logger.info("Running strategy iteration")

            # 1. Check account risk
            self._check_account_health()

            # 2. Check existing positions
            self._manage_existing_positions()

            # 3. Look for new opportunities
            self._find_new_opportunities()

            logger.info("Iteration complete")

        except Exception as e:
            logger.error(f"Error in iteration: {e}")

    def _check_account_health(self):
        """Check overall account health."""
        logger.info("Checking account health...")

        account_metrics = self.risk_manager.check_account_risk()

        if not account_metrics:
            logger.error("Could not retrieve account metrics")
            return

        # Check if margin utilization is too high
        utilization = account_metrics.get("margin_utilization", 0)
        if utilization > 0.8:  # 80% utilization
            logger.warning(f"High margin utilization: {utilization:.2%}")

    def _manage_existing_positions(self):
        """Manage existing positions."""
        logger.info("Managing existing positions...")

        positions = self.position_manager.get_positions()

        if not positions:
            logger.info("No existing positions")
            return

        for asset, position in positions.items():
            logger.info(f"Checking position: {asset}")

            # Check risk
            risk_metrics = self.risk_manager.check_position_risk(position)

            if not risk_metrics.is_safe:
                logger.warning(f"{asset}: Position at risk, closing...")
                if not self.dry_run:
                    self.position_manager.close_position(asset)
                continue

            # Check if should exit based on funding
            should_exit = self.funding_monitor.should_exit_position(
                asset, position.signal
            )

            if should_exit:
                logger.info(f"{asset}: Exit signal, closing position...")
                if not self.dry_run:
                    self.position_manager.close_position(asset)
                continue

            # Check if needs rebalancing
            if not position.is_balanced(self.config.rebalance_threshold):
                logger.info(f"{asset}: Position imbalanced, rebalancing...")
                if not self.dry_run:
                    self.position_manager.rebalance_position(asset)

    def _find_new_opportunities(self):
        """Find and enter new funding opportunities."""
        logger.info("Looking for new opportunities...")

        # Get best opportunities
        opportunities = self.funding_monitor.get_best_opportunities(
            self.config.assets
        )

        if not opportunities:
            logger.info("No opportunities found")
            return

        logger.info(f"Found {len(opportunities)} opportunities")

        for opp in opportunities:
            # Skip if already have position
            if self.position_manager.has_position(opp.asset):
                logger.info(f"{opp.asset}: Already have position, skipping")
                continue

            # Log opportunity
            logger.info(
                f"{opp.asset}: Funding={opp.funding_rate:.4%}, "
                f"APR={opp.expected_apr:.2%}, "
                f"Signal={opp.signal.value}"
            )

            # Calculate safe position size
            safe_size = self.risk_manager.calculate_safe_position_size(
                opp.asset,
                self.config.max_position_size_usd,
                self.config.leverage
            )

            if safe_size < 100:  # Minimum $100 position
                logger.warning(f"{opp.asset}: Position size too small (${safe_size:.2f})")
                continue

            # Enter position
            logger.info(f"{opp.asset}: Entering position with size ${safe_size:.2f}")

            if not self.dry_run:
                success = self.position_manager.open_position(
                    opp.asset,
                    opp.signal,
                    safe_size
                )

                if success:
                    logger.info(f"{opp.asset}: Position opened successfully")
                else:
                    logger.error(f"{opp.asset}: Failed to open position")

    def get_status(self) -> Dict:
        """Get current strategy status.

        Returns:
            Status dictionary
        """
        positions = self.position_manager.get_positions()
        account_metrics = self.risk_manager.check_account_risk()

        return {
            "running": self.running,
            "dry_run": self.dry_run,
            "num_positions": len(positions),
            "positions": {
                asset: {
                    "spot_size": pos.spot_size,
                    "perp_size": pos.perp_size,
                    "net_delta": pos.net_delta,
                    "entry_price": pos.entry_price,
                    "signal": pos.signal.value
                }
                for asset, pos in positions.items()
            },
            "account": account_metrics
        }
