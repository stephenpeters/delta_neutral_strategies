"""Risk management and liquidation protection."""

from typing import Optional, Dict
from dataclasses import dataclass
from loguru import logger
from hyperliquid_client import HyperliquidClient
from position_manager import Position


@dataclass
class RiskMetrics:
    """Risk metrics for a position."""
    asset: str
    account_value: float
    position_value: float
    unrealized_pnl: float
    margin_used: float
    liquidation_price: Optional[float]
    distance_to_liquidation: Optional[float]  # As percentage
    is_safe: bool


class RiskManager:
    """Manage risk and protect against liquidation."""

    def __init__(
        self,
        client: HyperliquidClient,
        liquidation_buffer: float = 0.3,
        max_slippage: float = 0.001
    ):
        """Initialize risk manager.

        Args:
            client: Hyperliquid client
            liquidation_buffer: Minimum distance to liquidation (30% = keep liq price 30% away)
            max_slippage: Maximum acceptable slippage
        """
        self.client = client
        self.liquidation_buffer = liquidation_buffer
        self.max_slippage = max_slippage

    def check_position_risk(self, position: Position) -> RiskMetrics:
        """Check risk metrics for a position.

        Args:
            position: Position to check

        Returns:
            RiskMetrics object
        """
        try:
            # Get user state
            user_state = self.client.get_user_state()
            margin_summary = user_state.get("marginSummary", {})

            account_value = float(margin_summary.get("accountValue", 0))
            total_margin_used = float(margin_summary.get("totalMarginUsed", 0))

            # Get position data from user state
            asset_positions = user_state.get("assetPositions", [])
            position_data = None
            for pos in asset_positions:
                if pos.get("position", {}).get("coin") == position.asset:
                    position_data = pos
                    break

            if not position_data:
                logger.warning(f"Position data not found for {position.asset}")
                return RiskMetrics(
                    asset=position.asset,
                    account_value=account_value,
                    position_value=0,
                    unrealized_pnl=0,
                    margin_used=0,
                    liquidation_price=None,
                    distance_to_liquidation=None,
                    is_safe=True
                )

            position_info = position_data.get("position", {})
            unrealized_pnl = float(position_info.get("unrealizedPnl", 0))
            position_value = float(position_info.get("positionValue", 0))
            liquidation_px = position_info.get("liquidationPx")

            # Calculate distance to liquidation
            distance_to_liquidation = None
            is_safe = True

            if liquidation_px:
                liquidation_price = float(liquidation_px)
                mark_price = self.client.get_mark_price(position.asset)

                if mark_price > 0:
                    distance_to_liquidation = abs(
                        (liquidation_price - mark_price) / mark_price
                    )

                    # Check if too close to liquidation
                    if distance_to_liquidation < self.liquidation_buffer:
                        is_safe = False
                        logger.warning(
                            f"{position.asset}: Close to liquidation! "
                            f"Distance: {distance_to_liquidation:.2%}, "
                            f"Buffer: {self.liquidation_buffer:.2%}"
                        )

            return RiskMetrics(
                asset=position.asset,
                account_value=account_value,
                position_value=position_value,
                unrealized_pnl=unrealized_pnl,
                margin_used=total_margin_used,
                liquidation_price=float(liquidation_px) if liquidation_px else None,
                distance_to_liquidation=distance_to_liquidation,
                is_safe=is_safe
            )

        except Exception as e:
            logger.error(f"Error checking position risk for {position.asset}: {e}")
            return RiskMetrics(
                asset=position.asset,
                account_value=0,
                position_value=0,
                unrealized_pnl=0,
                margin_used=0,
                liquidation_price=None,
                distance_to_liquidation=None,
                is_safe=False
            )

    def check_account_risk(self) -> Dict[str, float]:
        """Check overall account risk metrics.

        Returns:
            Dictionary of risk metrics
        """
        try:
            user_state = self.client.get_user_state()
            margin_summary = user_state.get("marginSummary", {})

            account_value = float(margin_summary.get("accountValue", 0))
            total_margin_used = float(margin_summary.get("totalMarginUsed", 0))
            total_ntl_pos = float(margin_summary.get("totalNtlPos", 0))
            total_raw_usd = float(margin_summary.get("totalRawUsd", 0))

            # Calculate utilization
            utilization = total_margin_used / account_value if account_value > 0 else 0

            metrics = {
                "account_value": account_value,
                "margin_used": total_margin_used,
                "total_position_notional": total_ntl_pos,
                "total_raw_usd": total_raw_usd,
                "margin_utilization": utilization
            }

            logger.info(
                f"Account metrics: Value=${account_value:.2f}, "
                f"Margin used=${total_margin_used:.2f}, "
                f"Utilization={utilization:.2%}"
            )

            return metrics

        except Exception as e:
            logger.error(f"Error checking account risk: {e}")
            return {}

    def should_reduce_position(self, position: Position) -> bool:
        """Determine if should reduce position due to risk.

        Args:
            position: Position to check

        Returns:
            True if should reduce position
        """
        risk_metrics = self.check_position_risk(position)

        if not risk_metrics.is_safe:
            logger.warning(f"{position.asset}: Position at risk, should reduce")
            return True

        return False

    def calculate_safe_position_size(
        self,
        asset: str,
        desired_size_usd: float,
        leverage: float
    ) -> float:
        """Calculate safe position size based on account and risk limits.

        Args:
            asset: Asset symbol
            desired_size_usd: Desired position size in USD
            leverage: Leverage to use

        Returns:
            Safe position size in USD
        """
        try:
            account_metrics = self.check_account_risk()
            account_value = account_metrics.get("account_value", 0)

            if account_value == 0:
                logger.error("Account value is 0")
                return 0

            # Don't use more than 80% of account per position (conservative)
            max_size_by_account = account_value * 0.8

            # Account for leverage
            margin_required = desired_size_usd / leverage

            # Ensure we have enough margin
            if margin_required > account_value * 0.8:
                safe_size = account_value * 0.8 * leverage
                logger.info(
                    f"Reducing position size from ${desired_size_usd:.2f} "
                    f"to ${safe_size:.2f} based on account size"
                )
                return safe_size

            return min(desired_size_usd, max_size_by_account)

        except Exception as e:
            logger.error(f"Error calculating safe position size: {e}")
            return 0

    def validate_slippage(
        self,
        expected_price: float,
        executed_price: float
    ) -> bool:
        """Validate that slippage is within acceptable limits.

        Args:
            expected_price: Expected execution price
            executed_price: Actual execution price

        Returns:
            True if slippage is acceptable
        """
        if expected_price == 0:
            return False

        slippage = abs((executed_price - expected_price) / expected_price)

        if slippage > self.max_slippage:
            logger.warning(
                f"Slippage {slippage:.4%} exceeds max {self.max_slippage:.4%}"
            )
            return False

        return True

    def emergency_close_all(self, position_manager) -> bool:
        """Emergency close all positions.

        Args:
            position_manager: PositionManager instance

        Returns:
            True if successful
        """
        try:
            logger.warning("EMERGENCY: Closing all positions")

            positions = position_manager.get_positions()

            for asset in positions:
                position_manager.close_position(asset)

            # Cancel all pending orders
            self.client.cancel_all_orders()

            logger.info("Emergency close completed")
            return True

        except Exception as e:
            logger.error(f"Error in emergency close: {e}")
            return False
