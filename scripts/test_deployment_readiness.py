"""
Comprehensive deployment readiness test script.

Tests:
1. Database connection and schema
2. Multi-interval configuration
3. API endpoints (including new interval endpoints)
4. Collector initialization
5. Data ingestion readiness
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from datetime import datetime, timezone

from src.db.asyncpg_pool import init_pool, close_pool, get_pool
from src.collectors.hyperliquid_websocket import HyperliquidWebSocketCollector
from src.utils.logger import setup_logging, get_logger
from src.utils.interval_manager import IntervalManager

logger = get_logger(__name__)

# API base URL (adjust if different)
API_BASE = "http://127.0.0.1:8090/api/v1"


def test_api_health():
    """Test API health endpoints."""
    logger.info("=" * 60)
    logger.info("1. Testing API Health")
    logger.info("=" * 60)

    try:
        # Basic health
        resp = requests.get(f"{API_BASE}/health", timeout=5)
        assert resp.status_code == 200, f"Health check failed: {resp.status_code}"
        logger.info("   [PASS] Basic health check")

        # Database health
        resp = requests.get(f"{API_BASE}/health/database", timeout=5)
        assert resp.status_code == 200, f"Database health failed: {resp.status_code}"
        data = resp.json()
        candles = data.get('data_counts', {}).get('candles', 0)
        active = data.get('data_counts', {}).get('active_listings', 0)
        logger.info(f"   [PASS] Database health: {candles} candles, {active} active listings")

        return True
    except Exception as e:
        logger.error(f"   [FAIL] API health check failed: {e}")
        return False


def test_listing_config():
    """Test that listings have multi-interval configuration."""
    logger.info("\n" + "=" * 60)
    logger.info("2. Testing Listing Configuration")
    logger.info("=" * 60)

    try:
        # Get listings
        resp = requests.get(f"{API_BASE}/listings", timeout=5)
        assert resp.status_code == 200, f"Failed to get listings: {resp.status_code}"
        listings = resp.json()

        if not listings:
            logger.warning("   [WARN] No active listings found - database may need seeding")
            return False

        # Check each listing for multi-interval config
        all_pass = True
        for listing in listings:
            listing_id = listing['id']
            symbol = listing['ccxt_symbol']
            config = listing.get('collector_config', {})

            # Check for new format
            intervals = config.get('candle_intervals', [])
            if not intervals:
                # Fallback to old format
                old_interval = config.get('candle_interval')
                intervals = [old_interval] if old_interval else []

            if intervals:
                intervals_str = IntervalManager.format_interval_list(intervals)
                logger.info(f"   [PASS] Listing {listing_id} ({symbol}): {intervals_str}")
            else:
                logger.warning(f"   [WARN] Listing {listing_id} ({symbol}): No intervals configured")
                all_pass = False

        return all_pass

    except Exception as e:
        logger.error(f"   [FAIL] Listing config check failed: {e}")
        return False


def test_new_interval_endpoints():
    """Test the new interval monitoring endpoints."""
    logger.info("\n" + "=" * 60)
    logger.info("3. Testing New Interval Endpoints")
    logger.info("=" * 60)

    try:
        # Test global intervals overview
        resp = requests.get(f"{API_BASE}/market/intervals/overview", timeout=5)
        assert resp.status_code == 200, f"Intervals overview failed: {resp.status_code}"
        data = resp.json()
        logger.info(f"   [PASS] Global overview: {data['global_stats']['total_listings']} listings")

        for listing in data['listings']:
            intervals_str = ", ".join(listing['configured_intervals'])
            counts = listing['interval_counts']
            logger.info(f"          {listing['ccxt_symbol']}: {intervals_str}")
            for interval, count in counts.items():
                logger.info(f"            - {interval}: {count} candles")

        # Test per-listing interval stats (listing 1)
        resp = requests.get(f"{API_BASE}/market/1/intervals", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            logger.info(f"   [PASS] Listing 1 interval stats:")
            for interval, stats in data['interval_stats'].items():
                latest = stats['latest_timestamp'] or 'None'
                count = stats['total_candles']
                freq = stats['polling_frequency_seconds']
                logger.info(f"          {interval}: {count} candles, latest={latest}, poll_freq={freq}s")
        else:
            logger.warning(f"   [WARN] Listing 1 interval stats not available (404 expected if listing doesn't exist)")

        return True

    except Exception as e:
        logger.error(f"   [FAIL] Interval endpoints test failed: {e}")
        return False


async def test_database_schema():
    """Test database schema supports multi-interval."""
    logger.info("\n" + "=" * 60)
    logger.info("4. Testing Database Schema")
    logger.info("=" * 60)

    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            # Check candle table has interval column with composite PK
            result = await conn.fetchrow("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'candle' AND column_name = 'interval'
            """)

            if result:
                logger.info(f"   [PASS] Candle table has 'interval' column ({result['data_type']})")
            else:
                logger.error("   [FAIL] Candle table missing 'interval' column!")
                return False

            # Check for data in different intervals
            intervals_query = await conn.fetch("""
                SELECT interval, COUNT(*) as count
                FROM candle
                GROUP BY interval
                ORDER BY interval
            """)

            if intervals_query:
                logger.info("   [PASS] Multi-interval data found:")
                for row in intervals_query:
                    logger.info(f"          {row['interval']}: {row['count']} candles")
            else:
                logger.warning("   [WARN] No candle data yet (expected if collectors haven't run)")

            # Check composite primary key
            pk_check = await conn.fetchrow("""
                SELECT constraint_name, constraint_type
                FROM information_schema.table_constraints
                WHERE table_name = 'candle' AND constraint_type = 'PRIMARY KEY'
            """)

            if pk_check:
                logger.info(f"   [PASS] Primary key exists: {pk_check['constraint_name']}")
            else:
                logger.warning("   [WARN] No primary key found on candle table")

        return True

    except Exception as e:
        logger.error(f"   [FAIL] Database schema check failed: {e}")
        return False


async def test_collector_initialization():
    """Test that collectors can initialize with multi-interval."""
    logger.info("\n" + "=" * 60)
    logger.info("5. Testing Collector Initialization")
    logger.info("=" * 60)

    try:
        # Test WebSocket collector with multiple intervals
        collector = HyperliquidWebSocketCollector(
            listing_id=1,
            symbol="BTC/USDC:USDC",
            coin_name="BTC",
            intervals=["1m", "15m", "4h", "1d"]
        )

        logger.info(f"   [PASS] WebSocket collector created")
        logger.info(f"          Intervals: {collector.intervals}")
        logger.info(f"          Timestamp trackers: {list(collector.last_candle_timestamps.keys())}")

        # Verify interval validation worked
        assert collector.intervals == ["1m", "15m", "4h", "1d"], "Intervals not set correctly"
        assert len(collector.last_candle_timestamps) == 4, "Timestamp trackers not initialized"

        logger.info("   [PASS] Multi-interval collector initialization successful")
        return True

    except Exception as e:
        logger.error(f"   [FAIL] Collector initialization failed: {e}")
        return False


def print_summary(results):
    """Print test summary."""
    logger.info("\n" + "=" * 60)
    logger.info("DEPLOYMENT READINESS SUMMARY")
    logger.info("=" * 60)

    total = len(results)
    passed = sum(1 for r in results if r)
    failed = total - passed

    for i, (test_name, result) in enumerate(results.items(), 1):
        status = "[PASS]" if result else "[FAIL]"
        logger.info(f"{i}. {test_name}: {status}")

    logger.info("")
    logger.info(f"Total: {passed}/{total} tests passed")

    if failed == 0:
        logger.info("\n" + "=" * 60)
        logger.info("READY FOR DEPLOYMENT!")
        logger.info("=" * 60)
        logger.info("\nNext steps:")
        logger.info("1. Seed database: python scripts/seed_database.py")
        logger.info("2. Run collectors for 5-10 min to verify data collection")
        logger.info("3. Run backfill (optional): python scripts/run_backfill.py")
        logger.info("4. Deploy to Digital Ocean")
        return 0
    else:
        logger.error("\n" + "=" * 60)
        logger.error("NOT READY FOR DEPLOYMENT")
        logger.error("=" * 60)
        logger.error(f"\n{failed} test(s) failed. Fix issues before deploying.")
        return 1


async def main():
    """Run all tests."""
    setup_logging(log_level="INFO", log_format="text")

    logger.info("\n" + "=" * 60)
    logger.info("DEPLOYMENT READINESS TEST SUITE")
    logger.info("=" * 60)
    logger.info(f"Testing against API: {API_BASE}")
    logger.info("")

    # Initialize database pool
    await init_pool()

    results = {}

    try:
        # Run all tests
        results["API Health"] = test_api_health()
        results["Listing Configuration"] = test_listing_config()
        results["New Interval Endpoints"] = test_new_interval_endpoints()
        results["Database Schema"] = await test_database_schema()
        results["Collector Initialization"] = await test_collector_initialization()

    finally:
        await close_pool()

    # Print summary
    return print_summary(results)


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
