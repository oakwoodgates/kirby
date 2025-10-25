"""
Test multi-interval collectors for a few minutes.

This script:
1. Starts collectors for BTC with all 4 intervals (1m, 15m, 4h, 1d)
2. Runs for 3 minutes
3. Monitors data collection in real-time
4. Reports on which intervals collected data
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.asyncpg_pool import init_pool, close_pool, get_pool
from src.collectors.hyperliquid_websocket import HyperliquidWebSocketCollector
from src.utils.logger import setup_logging, get_logger

logger = get_logger(__name__)

# Test duration (seconds)
TEST_DURATION = 180  # 3 minutes


async def monitor_data_collection():
    """Monitor data collection every 15 seconds."""
    pool = get_pool()
    start_time = datetime.now(timezone.utc)

    logger.info("\n" + "=" * 60)
    logger.info("MONITORING DATA COLLECTION")
    logger.info("=" * 60)

    while True:
        await asyncio.sleep(15)

        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        if elapsed >= TEST_DURATION:
            break

        async with pool.acquire() as conn:
            # Get counts per interval
            result = await conn.fetch("""
                SELECT interval, COUNT(*) as count, MAX(timestamp) as latest
                FROM candle
                WHERE listing_id = 1
                GROUP BY interval
                ORDER BY interval
            """)

            logger.info(f"\n[{elapsed:.0f}s elapsed] Data collection status:")
            for row in result:
                interval = row['interval']
                count = row['count']
                latest = row['latest'].strftime('%H:%M:%S') if row['latest'] else 'None'
                logger.info(f"  {interval:>3}: {count:>5} candles (latest: {latest})")


async def test_collectors():
    """Test collectors with multi-interval support."""
    setup_logging(log_level="INFO", log_format="text")

    logger.info("\n" + "=" * 60)
    logger.info("MULTI-INTERVAL COLLECTOR TEST")
    logger.info("=" * 60)
    logger.info(f"Duration: {TEST_DURATION} seconds")
    logger.info(f"Intervals: 1m, 15m, 4h, 1d")
    logger.info("")

    # Initialize database pool
    await init_pool()

    # Get initial counts
    pool = get_pool()
    async with pool.acquire() as conn:
        initial_counts = await conn.fetch("""
            SELECT interval, COUNT(*) as count
            FROM candle
            WHERE listing_id = 1
            GROUP BY interval
            ORDER BY interval
        """)

        logger.info("Initial candle counts:")
        initial_dict = {}
        for row in initial_counts:
            interval = row['interval']
            count = row['count']
            initial_dict[interval] = count
            logger.info(f"  {interval}: {count}")

    # Create collector with all intervals
    collector = HyperliquidWebSocketCollector(
        listing_id=1,
        symbol="BTC/USDC:USDC",
        coin_name="BTC",
        intervals=["1m", "15m", "4h", "1d"]
    )

    logger.info(f"\nCollector created with intervals: {collector.intervals}")
    logger.info("Initializing collector...")

    await collector.initialize()

    logger.info("Starting collector...")

    try:
        # Start collector and monitor in parallel
        collector_task = asyncio.create_task(collector.run())
        monitor_task = asyncio.create_task(monitor_data_collection())

        # Wait for test duration
        await asyncio.sleep(TEST_DURATION)

        # Stop collector
        logger.info("\n\nStopping collector...")
        await collector.stop()

        # Wait for tasks to complete
        await asyncio.wait_for(collector_task, timeout=10)
        monitor_task.cancel()

        # Get final counts
        async with pool.acquire() as conn:
            final_counts = await conn.fetch("""
                SELECT interval, COUNT(*) as count, MAX(timestamp) as latest
                FROM candle
                WHERE listing_id = 1
                GROUP BY interval
                ORDER BY interval
            """)

            logger.info("\n" + "=" * 60)
            logger.info("FINAL RESULTS")
            logger.info("=" * 60)

            success = False
            for row in final_counts:
                interval = row['interval']
                count = row['count']
                latest = row['latest'].strftime('%Y-%m-%d %H:%M:%S') if row['latest'] else 'None'
                initial = initial_dict.get(interval, 0)
                new_candles = count - initial

                logger.info(f"{interval}:")
                logger.info(f"  Total: {count} candles (+{new_candles} new)")
                logger.info(f"  Latest: {latest}")

                # We expect at least 1m candles (should get 2-3 in 3 minutes)
                if interval == "1m" and new_candles >= 2:
                    success = True

            logger.info("\n" + "=" * 60)
            if success:
                logger.info("TEST PASSED - Multi-interval collection working!")
                logger.info("\nNote: 15m, 4h, 1d intervals may not have new candles")
                logger.info("in 3 minutes - this is expected behavior.")
            else:
                logger.error("TEST FAILED - No new candles collected")
            logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)

    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(test_collectors())
