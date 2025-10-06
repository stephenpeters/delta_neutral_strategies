"""Funding rate monitoring and signal generation."""

from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
from loguru import logger
from hyperliquid_client import HyperliquidClient


class PositionSignal(Enum):
    """Position signal based on funding rate."""
    LONG_SPOT_SHORT_PERP = "long_spot_short_perp"  # Positive funding
    SHORT_SPOT_LONG_PERP = "short_spot_long_perp"  # Negative funding
    NO_SIGNAL = "no_signal"  # Funding below threshold


@dataclass
class FundingData:
    """Funding rate data for an asset."""
    asset: str
    funding_rate: float
    mark_price: float
    signal: PositionSignal
    expected_apr: float  # Annualized return from funding


class FundingMonitor:
    """Monitor funding rates and generate trading signals."""

    def __init__(self, client: HyperliquidClient, funding_threshold: float = 0.0001):
        """Initialize funding monitor.

        Args:
            client: Hyperliquid client
            funding_threshold: Minimum absolute funding rate to generate signal
        """
        self.client = client
        self.funding_threshold = funding_threshold

    def get_funding_data(self, asset: str) -> Optional[FundingData]:
        """Get funding data and signal for an asset.

        Args:
            asset: Asset symbol

        Returns:
            FundingData object or None if error
        """
        try:
            funding_rate = self.client.get_funding_rate(asset)
            mark_price = self.client.get_mark_price(asset)

            if mark_price == 0:
                logger.warning(f"Invalid mark price for {asset}")
                return None

            # Determine signal
            signal = self._get_signal(funding_rate)

            # Calculate expected APR (funding is 8-hour rate, annualize it)
            # 8 hours = 3 periods per day, 365 days per year
            expected_apr = abs(funding_rate) * 3 * 365

            return FundingData(
                asset=asset,
                funding_rate=funding_rate,
                mark_price=mark_price,
                signal=signal,
                expected_apr=expected_apr
            )
        except Exception as e:
            logger.error(f"Error getting funding data for {asset}: {e}")
            return None

    def _get_signal(self, funding_rate: float) -> PositionSignal:
        """Determine position signal from funding rate.

        Args:
            funding_rate: Current funding rate

        Returns:
            PositionSignal enum
        """
        if funding_rate > self.funding_threshold:
            # Positive funding: longs pay shorts
            # We want to be short perp, long spot
            return PositionSignal.LONG_SPOT_SHORT_PERP
        elif funding_rate < -self.funding_threshold:
            # Negative funding: shorts pay longs
            # We want to be long perp, short spot
            return PositionSignal.SHORT_SPOT_LONG_PERP
        else:
            return PositionSignal.NO_SIGNAL

    def get_best_opportunities(self, assets: List[str]) -> List[FundingData]:
        """Get funding opportunities sorted by expected return.

        Args:
            assets: List of asset symbols to check

        Returns:
            List of FundingData sorted by expected APR (highest first)
        """
        opportunities = []

        for asset in assets:
            funding_data = self.get_funding_data(asset)
            if funding_data and funding_data.signal != PositionSignal.NO_SIGNAL:
                opportunities.append(funding_data)

        # Sort by expected APR (descending)
        opportunities.sort(key=lambda x: x.expected_apr, reverse=True)

        return opportunities

    def should_enter_position(self, asset: str) -> tuple[bool, Optional[PositionSignal]]:
        """Check if should enter position for an asset.

        Args:
            asset: Asset symbol

        Returns:
            Tuple of (should_enter, signal)
        """
        funding_data = self.get_funding_data(asset)

        if not funding_data:
            return False, None

        if funding_data.signal == PositionSignal.NO_SIGNAL:
            return False, None

        logger.info(
            f"{asset}: Funding={funding_data.funding_rate:.4%}, "
            f"Expected APR={funding_data.expected_apr:.2%}, "
            f"Signal={funding_data.signal.value}"
        )

        return True, funding_data.signal

    def should_exit_position(self, asset: str, current_signal: PositionSignal) -> bool:
        """Check if should exit existing position.

        Args:
            asset: Asset symbol
            current_signal: Current position signal

        Returns:
            True if should exit
        """
        funding_data = self.get_funding_data(asset)

        if not funding_data:
            logger.warning(f"Cannot get funding data for {asset}, considering exit")
            return True

        # Exit if funding rate flipped direction
        if funding_data.signal != current_signal and funding_data.signal != PositionSignal.NO_SIGNAL:
            logger.info(f"{asset}: Funding flipped from {current_signal.value} to {funding_data.signal.value}")
            return True

        # Exit if funding rate below threshold
        if funding_data.signal == PositionSignal.NO_SIGNAL:
            logger.info(f"{asset}: Funding rate {funding_data.funding_rate:.4%} below threshold")
            return True

        return False
