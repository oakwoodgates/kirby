"""
Test script for backfill service.

This runs a small backfill test (last 3 days) to verify the backfill service works.
"""

import asyncio
from datetime import datetime, timedelta, timezone

from src.backfill.hyperliquid_backfiller import HyperliquidBackfiller
from src.db.asyncpg_pool import init_pool, close_pool
from src.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


async def main():
    """
    Test backfill for BTC with a small date range.
    """
    setup_logging(log_level="INFO", log_format="text")
    logger.info("=== Testing Backfill Service ===")

    # Initialize database pool
    logger.info("Initializing database connection pool...")
    await init_pool()

    try:
        # Backfill last 3 days only (small test)
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=3)

        logger.info(f"Test backfill date range: {start_date} to {end_date}")

        # Create backfiller for BTC
        backfiller = HyperliquidBackfiller(
            listing_id=1,
            symbol="BTC/USDC:USDC",
            start_date=start_date,
            end_date=end_date,
            batch_size=500,  # Smaller batches for testing
            rate_limit_delay=0.2,  # Slower for testing
        )

        # Run backfill for candles only (fastest to test)
        logger.info("Starting candle backfill...")
        results = await backfiller.run_backfill(data_types=['candles'])

        logger.info(f"\n=== Backfill Results ===")
        logger.info(f"Candles fetched: {results.get('candles', 0)}")

        # Show progress summary
        progress = backfiller.get_progress_summary()
        logger.info(f"\nProgress Summary:")
        for key, value in progress.items():
            logger.info(f"  {key}: {value}")

    except Exception as e:
        logger.error(f"Test backfill error: {e}", exc_info=True)

    finally:
        # Close database pool
        logger.info("\nClosing database connection pool...")
        await close_pool()

        logger.info("=== Test Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
