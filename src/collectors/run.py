"""
Collector orchestrator - starts collectors for all active listings.

This module is the main entry point for the collectors service.
It queries the database for active listings and starts a collector
for each one based on the listing's collector configuration.
"""

import asyncio
import signal
import sys
from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.asyncpg_pool import close_pool, init_pool
from src.db.session import get_session, init_db
from src.models import Listing
from src.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)

# Global collector tasks
collector_tasks: Dict[int, asyncio.Task] = {}
shutdown_event = asyncio.Event()


async def get_active_listings() -> List[Listing]:
    """
    Fetch all active listings from the database.

    Returns:
        List of active Listing objects
    """
    async with get_session() as session:
        result = await session.execute(
            select(Listing).where(Listing.is_active == True)
        )
        listings = result.scalars().all()
        return list(listings)


async def start_collector_for_listing(listing: Listing) -> None:
    """
    Start a collector for a specific listing based on its configuration.

    Args:
        listing: The listing to start a collector for
    """
    try:
        collector_config = listing.collector_config or {}
        collector_type = collector_config.get("type", "websocket")

        # Get intervals from config
        intervals = collector_config.get("candle_intervals") or [
            collector_config.get("candle_interval", "1m")
        ]

        logger.info(
            f"Starting {collector_type} collector for listing {listing.id} "
            f"({listing.ccxt_symbol}) with intervals: {intervals}"
        )

        # Import the appropriate collector
        if collector_type == "websocket":
            from src.collectors.hyperliquid_websocket import HyperliquidWebSocketCollector

            coin_name = collector_config.get("coin_name")
            if not coin_name:
                logger.error(f"No coin_name in config for listing {listing.id}")
                return

            collector = HyperliquidWebSocketCollector(
                listing_id=listing.id,
                symbol=listing.ccxt_symbol,
                coin_name=coin_name,
                intervals=intervals,
            )
        else:
            from src.collectors.hyperliquid_polling import HyperliquidPollingCollector

            collector = HyperliquidPollingCollector(
                listing_id=listing.id,
                symbol=listing.ccxt_symbol,
                intervals=intervals,
            )

        # Initialize and run the collector
        await collector.initialize()
        await collector.run()

    except Exception as e:
        logger.error(
            f"Error in collector for listing {listing.id}: {e}",
            exc_info=True
        )


async def start_all_collectors() -> None:
    """Start collectors for all active listings."""
    logger.info("Fetching active listings...")
    listings = await get_active_listings()

    if not listings:
        logger.warning("No active listings found!")
        return

    logger.info(f"Found {len(listings)} active listing(s)")

    # Start a collector task for each listing
    for listing in listings:
        task = asyncio.create_task(
            start_collector_for_listing(listing),
            name=f"collector_{listing.id}"
        )
        collector_tasks[listing.id] = task

    logger.info(f"Started {len(collector_tasks)} collector(s)")


async def monitor_collectors() -> None:
    """Monitor collector tasks and restart if they fail."""
    while not shutdown_event.is_set():
        await asyncio.sleep(60)  # Check every minute

        for listing_id, task in list(collector_tasks.items()):
            if task.done():
                # Collector task ended - check if it failed
                try:
                    task.result()
                except Exception as e:
                    logger.error(
                        f"Collector {listing_id} failed: {e}",
                        exc_info=True
                    )

                # Restart the collector
                logger.info(f"Restarting collector for listing {listing_id}")
                listings = await get_active_listings()
                listing = next((l for l in listings if l.id == listing_id), None)

                if listing:
                    new_task = asyncio.create_task(
                        start_collector_for_listing(listing),
                        name=f"collector_{listing.id}"
                    )
                    collector_tasks[listing_id] = new_task


async def shutdown(sig=None) -> None:
    """Gracefully shutdown all collectors."""
    if sig:
        logger.info(f"Received signal {sig.name}, shutting down...")
    else:
        logger.info("Shutting down collectors...")

    shutdown_event.set()

    # Cancel all collector tasks
    for listing_id, task in collector_tasks.items():
        logger.info(f"Stopping collector for listing {listing_id}")
        task.cancel()

    # Wait for all tasks to complete
    if collector_tasks:
        await asyncio.gather(*collector_tasks.values(), return_exceptions=True)

    # Close database connections
    await close_pool()

    logger.info("Shutdown complete")


async def main() -> None:
    """Main entry point for the collector service."""
    # Set up logging
    setup_logging(log_level="INFO", log_format="json")

    logger.info("=" * 60)
    logger.info("Starting Kirby Collector Service")
    logger.info("=" * 60)

    # Initialize database
    await init_pool()
    await init_db()

    # Set up signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(shutdown(s))
        )

    try:
        # Start all collectors
        await start_all_collectors()

        # Monitor collectors and wait for shutdown
        await monitor_collectors()

    except Exception as e:
        logger.error(f"Fatal error in collector service: {e}", exc_info=True)
        await shutdown()

    logger.info("Collector service stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
