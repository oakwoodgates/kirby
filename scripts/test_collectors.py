"""
Test script to run Hyperliquid collectors for BTC and HYPE.

This will start collectors for both listings and run them for a specified duration.
Press Ctrl+C to stop gracefully.
"""

import asyncio
import signal

from src.collectors.hyperliquid_websocket import HyperliquidWebSocketCollector
from src.db.asyncpg_pool import init_pool, close_pool
from src.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


# Global collectors list for graceful shutdown
collectors = []


async def main():
    """
    Main function to initialize and run collectors.
    """
    setup_logging(log_level="INFO", log_format="text")
    logger.info("=== Starting Hyperliquid WebSocket Collectors Test ===")

    # Initialize database pool
    logger.info("Initializing database connection pool...")
    await init_pool()

    try:
        # Create WebSocket collectors for BTC and HYPE
        # Listing IDs from seeding: 1=BTC/USDC:USDC, 2=HYPE/USDC:USDC

        btc_collector = HyperliquidWebSocketCollector(
            listing_id=1,
            symbol="BTC/USDC:USDC",
            coin_name="BTC",  # For Hyperliquid SDK WebSocket subscriptions
            heartbeat_interval=30,  # Heartbeat every 30 seconds
            max_reconnect_attempts=5,
        )

        hype_collector = HyperliquidWebSocketCollector(
            listing_id=2,
            symbol="HYPE/USDC:USDC",
            coin_name="HYPE",  # For Hyperliquid SDK WebSocket subscriptions
            heartbeat_interval=30,
            max_reconnect_attempts=5,
        )

        collectors.extend([btc_collector, hype_collector])

        # Initialize collectors
        logger.info("Initializing collectors...")
        await btc_collector.initialize()
        await hype_collector.initialize()

        # Start collectors (non-blocking)
        logger.info("Starting BTC collector...")
        await btc_collector.start()

        logger.info("Starting HYPE collector...")
        await hype_collector.start()

        logger.info("\n=== Collectors Running ===")
        logger.info("Press Ctrl+C to stop\n")

        # Wait indefinitely (collectors run in background tasks)
        while True:
            await asyncio.sleep(1)

    except asyncio.CancelledError:
        logger.info("Received cancellation signal")
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        logger.info("\n=== Stopping Collectors ===")

        # Stop all collectors gracefully
        stop_tasks = [collector.stop() for collector in collectors]
        await asyncio.gather(*stop_tasks, return_exceptions=True)

        # Close database pool
        logger.info("Closing database connection pool...")
        await close_pool()

        logger.info("=== Collectors stopped successfully ===")


def signal_handler(signum, frame):
    """
    Handle shutdown signals gracefully.
    """
    logger.info(f"\nReceived signal {signum}")
    raise KeyboardInterrupt


if __name__ == "__main__":
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown complete")
