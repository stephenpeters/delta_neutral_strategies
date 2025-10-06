"""Delta-neutral position management."""

from typing import Dict, Optional, List
from dataclasses import dataclass
from loguru import logger
from hyperliquid_client import HyperliquidClient
from funding_monitor import PositionSignal


@dataclass
class Position:
    """Represents a delta-neutral position."""
    asset: str
    spot_size: float  # Positive = long, negative = short
    perp_size: float  # Positive = long, negative = short
    entry_price: float
    signal: PositionSignal

    @property
    def net_delta(self) -> float:
        """Calculate net delta (should be near 0 for delta-neutral)."""
        return self.spot_size + self.perp_size

    @property
    def is_balanced(self, threshold: float = 0.05) -> bool:
        """Check if position is balanced within threshold."""
        if self.spot_size == 0:
            return True
        delta_ratio = abs(self.net_delta / self.spot_size)
        return delta_ratio <= threshold


class PositionManager:
    """Manage delta-neutral positions across spot and perpetual markets."""

    def __init__(
        self,
        client: HyperliquidClient,
        max_position_size_usd: float,
        rebalance_threshold: float = 0.05,
        leverage: float = 2.0
    ):
        """Initialize position manager.

        Args:
            client: Hyperliquid client
            max_position_size_usd: Maximum position size in USD
            rebalance_threshold: Rebalance when delta exceeds this ratio
            leverage: Leverage to use for perp positions
        """
        self.client = client
        self.max_position_size_usd = max_position_size_usd
        self.rebalance_threshold = rebalance_threshold
        self.leverage = leverage
        self.positions: Dict[str, Position] = {}

    def open_position(
        self,
        asset: str,
        signal: PositionSignal,
        size_usd: float
    ) -> bool:
        """Open a delta-neutral position.

        Args:
            asset: Asset symbol
            signal: Position signal (long spot/short perp or vice versa)
            size_usd: Position size in USD

        Returns:
            True if successful
        """
        try:
            # Cap position size
            size_usd = min(size_usd, self.max_position_size_usd)

            # Get current price
            mark_price = self.client.get_mark_price(asset)
            if mark_price == 0:
                logger.error(f"Cannot get mark price for {asset}")
                return False

            # Calculate position sizes
            size = size_usd / mark_price

            # Set leverage for perp
            self.client.update_leverage(asset, int(self.leverage), is_cross=True)

            if signal == PositionSignal.LONG_SPOT_SHORT_PERP:
                # Long spot, short perp
                logger.info(f"Opening {asset} position: LONG SPOT {size}, SHORT PERP {size}")

                # For now, we'll use perps for both sides since Hyperliquid spot requires more setup
                # In production, you'd want to use actual spot markets
                # Long perp (simulating spot)
                self.client.place_market_order(asset, is_buy=True, size=size)
                # Short perp
                self.client.place_market_order(asset, is_buy=False, size=size)

                spot_size = size
                perp_size = -size

            elif signal == PositionSignal.SHORT_SPOT_LONG_PERP:
                # Short spot, long perp
                logger.info(f"Opening {asset} position: SHORT SPOT {size}, LONG PERP {size}")

                # Short perp (simulating spot short)
                self.client.place_market_order(asset, is_buy=False, size=size)
                # Long perp
                self.client.place_market_order(asset, is_buy=True, size=size)

                spot_size = -size
                perp_size = size
            else:
                logger.warning(f"Invalid signal: {signal}")
                return False

            # Track position
            self.positions[asset] = Position(
                asset=asset,
                spot_size=spot_size,
                perp_size=perp_size,
                entry_price=mark_price,
                signal=signal
            )

            logger.info(f"Position opened for {asset}: {self.positions[asset]}")
            return True

        except Exception as e:
            logger.error(f"Error opening position for {asset}: {e}")
            return False

    def close_position(self, asset: str) -> bool:
        """Close a delta-neutral position.

        Args:
            asset: Asset symbol

        Returns:
            True if successful
        """
        try:
            if asset not in self.positions:
                logger.warning(f"No position found for {asset}")
                return False

            position = self.positions[asset]

            logger.info(f"Closing {asset} position: {position}")

            # Close spot position (using perp as proxy)
            if position.spot_size > 0:
                self.client.place_market_order(
                    asset, is_buy=False, size=abs(position.spot_size), reduce_only=True
                )
            elif position.spot_size < 0:
                self.client.place_market_order(
                    asset, is_buy=True, size=abs(position.spot_size), reduce_only=True
                )

            # Close perp position
            if position.perp_size > 0:
                self.client.place_market_order(
                    asset, is_buy=False, size=abs(position.perp_size), reduce_only=True
                )
            elif position.perp_size < 0:
                self.client.place_market_order(
                    asset, is_buy=True, size=abs(position.perp_size), reduce_only=True
                )

            # Remove from tracking
            del self.positions[asset]

            logger.info(f"Position closed for {asset}")
            return True

        except Exception as e:
            logger.error(f"Error closing position for {asset}: {e}")
            return False

    def rebalance_position(self, asset: str) -> bool:
        """Rebalance a position to maintain delta neutrality.

        Args:
            asset: Asset symbol

        Returns:
            True if rebalanced
        """
        try:
            if asset not in self.positions:
                logger.warning(f"No position found for {asset}")
                return False

            position = self.positions[asset]

            # Check if rebalancing needed
            if position.is_balanced(self.rebalance_threshold):
                return False

            delta = position.net_delta

            logger.info(f"Rebalancing {asset}: net delta = {delta}")

            # Adjust perp position to offset delta
            if delta > 0:
                # Too much long exposure, short more perp
                self.client.place_market_order(asset, is_buy=False, size=abs(delta))
                position.perp_size -= abs(delta)
            else:
                # Too much short exposure, long more perp
                self.client.place_market_order(asset, is_buy=True, size=abs(delta))
                position.perp_size += abs(delta)

            logger.info(f"Rebalanced {asset}: new delta = {position.net_delta}")
            return True

        except Exception as e:
            logger.error(f"Error rebalancing {asset}: {e}")
            return False

    def get_positions(self) -> Dict[str, Position]:
        """Get all current positions.

        Returns:
            Dictionary of asset -> Position
        """
        return self.positions.copy()

    def has_position(self, asset: str) -> bool:
        """Check if has position for asset.

        Args:
            asset: Asset symbol

        Returns:
            True if has position
        """
        return asset in self.positions
