"""Hyperliquid API client wrapper."""

from typing import Dict, List, Optional, Any
from loguru import logger
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants


class HyperliquidClient:
    """Wrapper for Hyperliquid API interactions."""

    def __init__(self, private_key: str, account_address: Optional[str] = None):
        """Initialize Hyperliquid client.

        Args:
            private_key: Private key for signing transactions
            account_address: Account address (optional, derived from private key if not provided)
        """
        self.private_key = private_key
        self.account_address = account_address

        # Initialize Info and Exchange clients
        self.info = Info(constants.MAINNET_API_URL, skip_ws=True)
        self.exchange = Exchange(
            wallet=None,  # Will be set with private key
            base_url=constants.MAINNET_API_URL,
            account_address=account_address
        )

        logger.info("Hyperliquid client initialized")

    def get_funding_rate(self, asset: str) -> float:
        """Get current funding rate for an asset.

        Args:
            asset: Asset symbol (e.g., 'BTC', 'ETH', 'HYPE')

        Returns:
            Current funding rate (8-hour rate)
        """
        try:
            meta = self.info.meta()
            for universe_item in meta.get("universe", []):
                if universe_item.get("name") == asset:
                    funding = universe_item.get("funding", "0")
                    return float(funding)

            logger.warning(f"Funding rate not found for {asset}")
            return 0.0
        except Exception as e:
            logger.error(f"Error getting funding rate for {asset}: {e}")
            return 0.0

    def get_mark_price(self, asset: str) -> float:
        """Get mark price for an asset.

        Args:
            asset: Asset symbol

        Returns:
            Current mark price
        """
        try:
            all_mids = self.info.all_mids()
            return float(all_mids.get(asset, 0))
        except Exception as e:
            logger.error(f"Error getting mark price for {asset}: {e}")
            return 0.0

    def get_user_state(self) -> Dict[str, Any]:
        """Get current user state including positions and balances.

        Returns:
            User state dictionary
        """
        try:
            if not self.account_address:
                logger.error("Account address not set")
                return {}

            return self.info.user_state(self.account_address)
        except Exception as e:
            logger.error(f"Error getting user state: {e}")
            return {}

    def get_positions(self) -> List[Dict[str, Any]]:
        """Get current open positions.

        Returns:
            List of position dictionaries
        """
        try:
            user_state = self.get_user_state()
            return user_state.get("assetPositions", [])
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    def get_balance(self) -> float:
        """Get account USDC balance.

        Returns:
            USDC balance
        """
        try:
            user_state = self.get_user_state()
            margin_summary = user_state.get("marginSummary", {})
            return float(margin_summary.get("accountValue", 0))
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return 0.0

    def place_market_order(
        self,
        asset: str,
        is_buy: bool,
        size: float,
        reduce_only: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Place a market order.

        Args:
            asset: Asset symbol
            is_buy: True for buy, False for sell
            size: Order size
            reduce_only: If True, order will only reduce position

        Returns:
            Order response or None if error
        """
        try:
            order_result = self.exchange.market_open(
                asset,
                is_buy,
                size,
                None,  # slippage
                reduce_only=reduce_only
            )
            logger.info(f"Market order placed: {asset} {'BUY' if is_buy else 'SELL'} {size}")
            return order_result
        except Exception as e:
            logger.error(f"Error placing market order: {e}")
            return None

    def place_limit_order(
        self,
        asset: str,
        is_buy: bool,
        size: float,
        price: float,
        reduce_only: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Place a limit order.

        Args:
            asset: Asset symbol
            is_buy: True for buy, False for sell
            size: Order size
            price: Limit price
            reduce_only: If True, order will only reduce position

        Returns:
            Order response or None if error
        """
        try:
            order_result = self.exchange.order(
                asset,
                is_buy,
                size,
                price,
                {"limit": {"tif": "Gtc"}},
                reduce_only=reduce_only
            )
            logger.info(f"Limit order placed: {asset} {'BUY' if is_buy else 'SELL'} {size} @ {price}")
            return order_result
        except Exception as e:
            logger.error(f"Error placing limit order: {e}")
            return None

    def cancel_all_orders(self, asset: Optional[str] = None) -> bool:
        """Cancel all orders for an asset or all assets.

        Args:
            asset: Asset symbol (None for all assets)

        Returns:
            True if successful
        """
        try:
            self.exchange.cancel_all_orders(asset)
            logger.info(f"Cancelled all orders for {asset or 'all assets'}")
            return True
        except Exception as e:
            logger.error(f"Error cancelling orders: {e}")
            return False

    def update_leverage(self, asset: str, leverage: int, is_cross: bool = True) -> bool:
        """Update leverage for an asset.

        Args:
            asset: Asset symbol
            leverage: Leverage amount
            is_cross: True for cross margin, False for isolated

        Returns:
            True if successful
        """
        try:
            self.exchange.update_leverage(leverage, asset, is_cross)
            logger.info(f"Updated leverage for {asset}: {leverage}x ({'cross' if is_cross else 'isolated'})")
            return True
        except Exception as e:
            logger.error(f"Error updating leverage: {e}")
            return False
