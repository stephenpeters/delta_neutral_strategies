#!/usr/bin/env python3
"""Main entry point for Hyperliquid funding arbitrage strategy."""

import sys
import argparse
from loguru import logger
from config import get_config
from strategy import FundingArbStrategy


def setup_logging(log_level: str = "INFO"):
    """Setup logging configuration.

    Args:
        log_level: Logging level
    """
    logger.remove()  # Remove default handler
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level=log_level
    )
    logger.add(
        "logs/strategy_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="30 days",
        level=log_level
    )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Hyperliquid Funding Arbitrage Strategy"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode (no actual trades)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Check interval in seconds (default: 300)"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level)

    # Load configuration
    config = get_config()

    # Validate configuration
    if not config.private_key:
        logger.error("HYPERLIQUID_PRIVATE_KEY not set in .env file")
        sys.exit(1)

    if not config.account_address:
        logger.error("HYPERLIQUID_ACCOUNT_ADDRESS not set in .env file")
        sys.exit(1)

    # Create and start strategy
    logger.info("=" * 80)
    logger.info("Hyperliquid Funding Arbitrage Strategy")
    logger.info("=" * 80)

    strategy = FundingArbStrategy(config, dry_run=args.dry_run)

    try:
        strategy.start(check_interval=args.interval)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        strategy.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
