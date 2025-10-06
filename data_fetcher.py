"""Fetch historical data from Hyperliquid for backtesting."""

import time
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import requests
from loguru import logger


@dataclass
class HistoricalDataPoint:
    """Single data point for backtesting."""
    timestamp: int
    asset: str
    funding_rate: float
    mark_price: float
    open_interest: Optional[float] = None


class DataFetcher:
    """Fetch historical funding rates and prices from Hyperliquid."""

    BASE_URL = "https://api.hyperliquid.xyz/info"

    def __init__(self):
        """Initialize data fetcher."""
        self.session = requests.Session()

    def get_funding_history(
        self,
        asset: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[HistoricalDataPoint]:
        """Fetch historical funding rates.

        Args:
            asset: Asset symbol (e.g., 'BTC', 'ETH', 'HYPE')
            start_time: Start datetime
            end_time: End datetime

        Returns:
            List of historical data points
        """
        try:
            # Convert to milliseconds
            start_ms = int(start_time.timestamp() * 1000)
            end_ms = int(end_time.timestamp() * 1000)

            payload = {
                "type": "fundingHistory",
                "coin": asset,
                "startTime": start_ms,
                "endTime": end_ms
            }

            response = self.session.post(self.BASE_URL, json=payload)
            response.raise_for_status()

            data = response.json()

            data_points = []
            for item in data:
                data_points.append(HistoricalDataPoint(
                    timestamp=item.get("time", 0),
                    asset=asset,
                    funding_rate=float(item.get("fundingRate", 0)),
                    mark_price=float(item.get("premium", 0)),  # This might need adjustment
                ))

            logger.info(f"Fetched {len(data_points)} funding data points for {asset}")
            return data_points

        except Exception as e:
            logger.error(f"Error fetching funding history for {asset}: {e}")
            return []

    def get_candles(
        self,
        asset: str,
        start_time: datetime,
        end_time: datetime,
        interval: str = "1h"
    ) -> List[Dict]:
        """Fetch historical price candles.

        Args:
            asset: Asset symbol
            start_time: Start datetime
            end_time: End datetime
            interval: Candle interval (e.g., '1h', '4h', '1d')

        Returns:
            List of candle data
        """
        try:
            start_ms = int(start_time.timestamp() * 1000)
            end_ms = int(end_time.timestamp() * 1000)

            payload = {
                "type": "candleSnapshot",
                "req": {
                    "coin": asset,
                    "interval": interval,
                    "startTime": start_ms,
                    "endTime": end_ms
                }
            }

            response = self.session.post(self.BASE_URL, json=payload)
            response.raise_for_status()

            candles = response.json()

            logger.info(f"Fetched {len(candles)} candles for {asset}")
            return candles

        except Exception as e:
            logger.error(f"Error fetching candles for {asset}: {e}")
            return []

    def fetch_backtest_data(
        self,
        assets: List[str],
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, List[HistoricalDataPoint]]:
        """Fetch all data needed for backtesting.

        Args:
            assets: List of asset symbols
            start_time: Start datetime
            end_time: End datetime

        Returns:
            Dictionary mapping asset to list of data points
        """
        all_data = {}

        for asset in assets:
            logger.info(f"Fetching data for {asset}...")

            # Get funding history
            funding_data = self.get_funding_history(asset, start_time, end_time)

            # Get price data
            candles = self.get_candles(asset, start_time, end_time, interval="1h")

            # Merge funding and price data
            # Create a map of timestamps to prices
            price_map = {}
            for candle in candles:
                if isinstance(candle, dict):
                    ts = candle.get("t", 0)
                    close = float(candle.get("c", 0))
                    price_map[ts] = close

            # Update funding data with prices
            enriched_data = []
            for fd in funding_data:
                # Find closest price
                closest_price = self._find_closest_price(fd.timestamp, price_map)
                if closest_price:
                    fd.mark_price = closest_price
                enriched_data.append(fd)

            all_data[asset] = enriched_data

            # Rate limit
            time.sleep(0.5)

        return all_data

    def _find_closest_price(
        self,
        timestamp: int,
        price_map: Dict[int, float]
    ) -> Optional[float]:
        """Find the closest price to a timestamp.

        Args:
            timestamp: Target timestamp
            price_map: Map of timestamp to price

        Returns:
            Closest price or None
        """
        if not price_map:
            return None

        closest_ts = min(price_map.keys(), key=lambda x: abs(x - timestamp))
        return price_map[closest_ts]

    def save_to_csv(
        self,
        data: Dict[str, List[HistoricalDataPoint]],
        output_dir: str = "backtest_data"
    ):
        """Save historical data to CSV files.

        Args:
            data: Historical data
            output_dir: Output directory
        """
        import os
        import csv

        os.makedirs(output_dir, exist_ok=True)

        for asset, data_points in data.items():
            filename = f"{output_dir}/{asset}_history.csv"

            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'datetime', 'asset', 'funding_rate', 'mark_price'])

                for dp in data_points:
                    dt = datetime.fromtimestamp(dp.timestamp / 1000)
                    writer.writerow([
                        dp.timestamp,
                        dt.isoformat(),
                        dp.asset,
                        dp.funding_rate,
                        dp.mark_price
                    ])

            logger.info(f"Saved {len(data_points)} data points to {filename}")
