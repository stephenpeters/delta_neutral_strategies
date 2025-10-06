"""Configuration management for Hyperliquid funding arbitrage strategy."""

import os
from typing import List
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


class StrategyConfig(BaseModel):
    """Strategy configuration parameters."""

    # API Configuration
    private_key: str = Field(default_factory=lambda: os.getenv("HYPERLIQUID_PRIVATE_KEY", ""))
    account_address: str = Field(default_factory=lambda: os.getenv("HYPERLIQUID_ACCOUNT_ADDRESS", ""))

    # Strategy Parameters
    funding_rate_threshold: float = Field(
        default_factory=lambda: float(os.getenv("FUNDING_RATE_THRESHOLD", "0.0001"))
    )
    rebalance_threshold: float = Field(
        default_factory=lambda: float(os.getenv("REBALANCE_THRESHOLD", "0.05"))
    )
    max_position_size_usd: float = Field(
        default_factory=lambda: float(os.getenv("MAX_POSITION_SIZE_USD", "10000"))
    )
    leverage: float = Field(
        default_factory=lambda: float(os.getenv("LEVERAGE", "2"))
    )
    assets: List[str] = Field(
        default_factory=lambda: os.getenv("ASSETS", "HYPE,BTC,ETH").split(",")
    )

    # Risk Management
    liquidation_buffer: float = Field(
        default_factory=lambda: float(os.getenv("LIQUIDATION_BUFFER", "0.3"))
    )
    max_slippage: float = Field(
        default_factory=lambda: float(os.getenv("MAX_SLIPPAGE", "0.001"))
    )

    # Logging
    log_level: str = Field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
    )

    class Config:
        arbitrary_types_allowed = True


def get_config() -> StrategyConfig:
    """Get strategy configuration."""
    return StrategyConfig()
