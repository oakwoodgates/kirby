"""
Quick test of multi-interval backfill functionality.

Tests backfilling a small amount of data for 15m interval to verify it works.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.asyncpg_pool import init_pool, close_pool, get_pool
from src.backfill.hyperliquid_backfiller import HyperliquidBackfiller
from src.utils.logger import setup_logging, get_logger

logger = get_logger(__name__)


async def test_backfill():
    """Test backfilling 15m candles."""
    setup_logging(log_level="INFO", log_format="text")

    logger.info("\n" + "=" * 60)
    logger.info("MULTI-INTERVAL BACKFILL TEST")
    logger.info("=" * 60)
    logger.info("Testing: 15m interval backfill for BTC")
    logger.info("Amount: 24 hours (~96 candles)")
    logger.info("")

    # Initialize database pool
    await init_pool()

    # Get initial counts
    pool = get_pool()
    async with pool.acquire() as conn:
        initial = await conn.fetchrow("""
            SELECT COUNT(*) as count, MAX(timestamp) as latest
            FROM candle
            WHERE listing_id = 1 AND interval = '15m'
        """)

        logger.info(f"Initial 15m candles: {initial['count']}")
        logger.info(f"Latest 15m candle: {initial['latest']}")

    # Create backfiller (1 day ago)
    start_date = datetime.now(timezone.utc) - timedelta(days=1)
    backfiller = HyperliquidBackfiller(
        listing_id=1,
        symbol="BTC/USDC:USDC",
        coin_name="BTC",
        start_date=start_date
    )

    try:
        await backfiller.initialize()

        # Backfill 15m candles
        logger.info("\nStarting backfill for 15m interval...")
        count = await backfiller.backfill_candles(interval="15m")
        logger.info(f"Backfilled {count} 15m candles")

        # Get final counts
        async with pool.acquire() as conn:
            final = await conn.fetchrow("""
                SELECT COUNT(*) as count, MAX(timestamp) as latest, MIN(timestamp) as earliest
                FROM candle
                WHERE listing_id = 1 AND interval = '15m'
            """)

            logger.info("\n" + "=" * 60)
            logger.info("RESULTS")
            logger.info("=" * 60)
            logger.info(f"Total 15m candles: {final['count']}")
            logger.info(f"Earliest: {final['earliest']}")
            logger.info(f"Latest: {final['latest']}")
            logger.info(f"New candles: {final['count'] - initial['count']}")

            if final['count'] > initial['count']:
                logger.info("\n[PASS] Backfill successful!")
            else:
                logger.error("\n[FAIL] No new candles were backfilled")

    except Exception as e:
        logger.error(f"Backfill test failed: {e}", exc_info=True)

    finally:
        await backfiller.close()
        await close_pool()


if __name__ == "__main__":
    asyncio.run(test_backfill())
