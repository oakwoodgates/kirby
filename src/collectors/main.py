"""
Main entry point for Kirby collectors.

Orchestrates all exchange collectors.
"""
import asyncio
import signal
from typing import Any

import structlog

from src.collectors.base import BaseCollector
from src.collectors.hyperliquid import HyperliquidCollector
from src.config.loader import ConfigLoader
from src.db.connection import close_db, get_session, init_db
from src.utils.logging import setup_logging


class CollectorManager:
    """Manages multiple exchange collectors."""

    def __init__(self):
        """Initialize collector manager."""
        self.logger = structlog.get_logger("kirby.collector.manager")
        self.collectors: dict[str, BaseCollector] = {}
        self.tasks: list[asyncio.Task] = []
        self._shutdown_event = asyncio.Event()

    def register_collector(self, collector: BaseCollector) -> None:
        """
        Register a collector.

        Args:
            collector: Collector instance to register
        """
        self.collectors[collector.exchange_name] = collector
        self.logger.info(
            "Registered collector",
            exchange=collector.exchange_name,
        )

    async def start_all(self) -> None:
        """Start all registered collectors."""
        self.logger.info(
            "Starting all collectors",
            collector_count=len(self.collectors),
        )

        for exchange_name, collector in self.collectors.items():
            try:
                # Initialize collector
                await collector.initialize()

                # Start collector in background task
                task = asyncio.create_task(
                    collector.start(),
                    name=f"collector-{exchange_name}",
                )
                self.tasks.append(task)

                self.logger.info(
                    "Started collector",
                    exchange=exchange_name,
                )

            except Exception as e:
                self.logger.error(
                    "Failed to start collector",
                    exchange=exchange_name,
                    error=str(e),
                    exc_info=True,
                )

    async def stop_all(self) -> None:
        """Stop all collectors gracefully."""
        self.logger.info("Stopping all collectors")

        # Signal all collectors to stop
        for collector in self.collectors.values():
            await collector.stop()

        # Wait for all tasks to complete
        if self.tasks:
            self.logger.info("Waiting for collector tasks to complete")
            await asyncio.gather(*self.tasks, return_exceptions=True)

        self.logger.info("All collectors stopped")

    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        await self._shutdown_event.wait()

    def request_shutdown(self) -> None:
        """Request graceful shutdown."""
        self.logger.info("Shutdown requested")
        self._shutdown_event.set()

    def get_health(self) -> dict[str, Any]:
        """
        Get health status of all collectors.

        Returns:
            Health status dictionary
        """
        return {
            "collectors": {
                name: collector.get_health()
                for name, collector in self.collectors.items()
            },
            "total_collectors": len(self.collectors),
            "running_collectors": sum(
                1 for c in self.collectors.values()
                if c.status.value == "running"
            ),
        }


async def main() -> None:
    """Main entry point for collector service."""
    # Set up logging
    setup_logging()
    logger = structlog.get_logger("kirby.collector")

    logger.info("Starting Kirby Collector Service")

    # Initialize database connections
    await init_db()
    logger.info("Database initialized")

    # Load and sync configuration
    try:
        config_loader = ConfigLoader()
        async with get_session() as session:
            await config_loader.sync_to_database(session)
        logger.info("Configuration synced to database")
    except Exception as e:
        logger.error(
            "Failed to sync configuration",
            error=str(e),
            exc_info=True,
        )
        # Continue even if sync fails (config might already be in DB)

    # Create collector manager
    manager = CollectorManager()

    # Register collectors
    # Add more collectors here as they are implemented
    manager.register_collector(HyperliquidCollector())

    # Set up signal handlers for graceful shutdown
    def signal_handler(sig: int) -> None:
        """Handle shutdown signals."""
        logger.info("Received signal", signal=sig)
        manager.request_shutdown()

    # Register signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))

    try:
        # Start all collectors
        await manager.start_all()

        # Wait for shutdown signal
        await manager.wait_for_shutdown()

    except Exception as e:
        logger.error(
            "Collector service error",
            error=str(e),
            exc_info=True,
        )
    finally:
        # Stop all collectors
        await manager.stop_all()

        # Close database connections
        await close_db()
        logger.info("Database connections closed")

    logger.info("Kirby Collector Service stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nCollector service interrupted by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        raise
