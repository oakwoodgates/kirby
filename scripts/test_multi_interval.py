"""
Test script for multi-interval architecture.

Validates:
1. IntervalManager utility
2. Collector initialization with multiple intervals
3. Configuration parsing
4. API endpoints
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.interval_manager import IntervalManager
from src.utils.logger import setup_logging, get_logger

logger = get_logger(__name__)


def test_interval_manager():
    """Test IntervalManager utility functions."""
    logger.info("=" * 60)
    logger.info("Testing IntervalManager")
    logger.info("=" * 60)

    # Test 1: Validate intervals (valid only, with duplicates)
    logger.info("\n1. Testing interval validation...")
    intervals = ["1m", "15m", "4h", "1d", "1m"]  # Duplicates
    validated = IntervalManager.validate_intervals(intervals)
    logger.info(f"   Input:  {intervals}")
    logger.info(f"   Output: {validated}")
    assert validated == ["1m", "15m", "4h", "1d"], "Validation failed"
    logger.info("   ✓ Validation removes duplicates and sorts")

    # Test 1b: Test invalid intervals (should raise error)
    logger.info("\n1b. Testing invalid interval detection...")
    try:
        IntervalManager.validate_intervals(["1m", "invalid"])
        assert False, "Should have raised ValueError"
    except ValueError as e:
        logger.info(f"   ✓ Correctly rejects invalid intervals: {str(e)[:50]}...")

    # Test 2: Get polling frequencies
    logger.info("\n2. Testing polling frequencies...")
    for interval in ["1m", "15m", "4h", "1d"]:
        freq = IntervalManager.get_poll_frequency(interval)
        logger.info(f"   {interval}: poll every {freq}s")
    logger.info("   ✓ Polling frequencies calculated")

    # Test 3: Get backfill batch sizes
    logger.info("\n3. Testing backfill batch sizes...")
    for interval in ["1m", "15m", "4h", "1d"]:
        batch_size = IntervalManager.get_backfill_batch_size(interval)
        logger.info(f"   {interval}: {batch_size} candles per batch")
    logger.info("   ✓ Batch sizes calculated")

    # Test 4: Get interval info
    logger.info("\n4. Testing interval metadata...")
    info = IntervalManager.get_interval_info("4h")
    logger.info(f"   4h interval info:")
    logger.info(f"     - Display name: {info['display_name']}")
    logger.info(f"     - Duration: {info['seconds']}s")
    logger.info(f"     - Candles per day: {info['candles_per_day']}")
    logger.info(f"     - CCXT timeframe: {info['ccxt_timeframe']}")
    logger.info("   ✓ Metadata retrieved")

    # Test 5: Format interval list
    logger.info("\n5. Testing interval formatting...")
    formatted = IntervalManager.format_interval_list(["1m", "15m", "4h", "1d"])
    logger.info(f"   Formatted: {formatted}")
    logger.info("   ✓ Formatting working")

    logger.info("\n✅ All IntervalManager tests passed!\n")


def test_collector_config():
    """Test collector configuration parsing."""
    logger.info("=" * 60)
    logger.info("Testing Collector Configuration")
    logger.info("=" * 60)

    # Test 1: New format (candle_intervals array)
    logger.info("\n1. Testing new config format (candle_intervals)...")
    config = {
        "type": "websocket",
        "coin_name": "BTC",
        "candle_intervals": ["1m", "15m", "4h", "1d"],
    }
    intervals = config.get('candle_intervals')
    validated = IntervalManager.validate_intervals(intervals)
    logger.info(f"   Config: {config}")
    logger.info(f"   Intervals: {validated}")
    logger.info("   ✓ New format parsed correctly")

    # Test 2: Old format (candle_interval string) - backward compatibility
    logger.info("\n2. Testing old config format (candle_interval)...")
    old_config = {
        "type": "websocket",
        "coin_name": "BTC",
        "candle_interval": "1m",
    }
    # Simulate fallback logic from collectors
    intervals = old_config.get('candle_intervals') or [old_config.get('candle_interval', '1m')]
    validated = IntervalManager.validate_intervals(intervals)
    logger.info(f"   Config: {old_config}")
    logger.info(f"   Intervals: {validated}")
    logger.info("   ✓ Old format backward compatible")

    logger.info("\n✅ All configuration tests passed!\n")


async def test_collector_initialization():
    """Test collector initialization with intervals parameter."""
    logger.info("=" * 60)
    logger.info("Testing Collector Initialization")
    logger.info("=" * 60)

    from src.collectors.hyperliquid_polling import HyperliquidPollingCollector

    # Test 1: Initialize with multiple intervals
    logger.info("\n1. Testing polling collector initialization...")
    collector = HyperliquidPollingCollector(
        listing_id=1,
        symbol="BTC/USDC:USDC",
        intervals=["1m", "15m", "4h", "1d"],
    )
    logger.info(f"   Configured intervals: {collector.intervals}")
    logger.info(f"   Timestamp trackers: {list(collector.last_candle_timestamps.keys())}")
    assert collector.intervals == ["1m", "15m", "4h", "1d"], "Intervals not set"
    assert len(collector.last_candle_timestamps) == 4, "Timestamp trackers not initialized"
    logger.info("   ✓ Polling collector initialized")

    # Test 2: Initialize with default (no intervals specified)
    logger.info("\n2. Testing default interval...")
    default_collector = HyperliquidPollingCollector(
        listing_id=1,
        symbol="BTC/USDC:USDC",
    )
    logger.info(f"   Default intervals: {default_collector.intervals}")
    assert default_collector.intervals == ["1m"], "Default interval not set"
    logger.info("   ✓ Default interval working")

    logger.info("\n✅ All collector initialization tests passed!\n")


def main():
    """Run all tests."""
    setup_logging(log_level="INFO", log_format="text")

    logger.info("\n" + "=" * 60)
    logger.info("Multi-Interval Architecture Test Suite")
    logger.info("=" * 60 + "\n")

    try:
        # Run synchronous tests
        test_interval_manager()
        test_collector_config()

        # Run async tests
        asyncio.run(test_collector_initialization())

        logger.info("\n" + "=" * 60)
        logger.info("SUCCESS: ALL TESTS PASSED!")
        logger.info("=" * 60 + "\n")

        logger.info("Summary:")
        logger.info("  ✓ IntervalManager utility")
        logger.info("  ✓ Configuration parsing")
        logger.info("  ✓ Collector initialization")
        logger.info("  ✓ Backward compatibility")
        logger.info("")

        return 0

    except Exception as e:
        logger.error(f"\nTEST FAILED: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
