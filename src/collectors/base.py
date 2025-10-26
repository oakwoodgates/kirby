"""
Base collector framework for exchange data collection.
"""
import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any

import structlog

from src.config.settings import settings
from src.db.connection import get_asyncpg_pool, get_session
from src.db.repositories import CandleRepository, StarlistingRepository
from src.utils.helpers import utc_now


class CollectorStatus(Enum):
    """Collector status states."""

    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class BaseCollector(ABC):
    """
    Base class for exchange collectors.

    Implements lifecycle management, error handling, and auto-restart logic.
    Subclasses must implement connect() and collect() methods.
    """

    def __init__(self, exchange_name: str):
        """
        Initialize the collector.

        Args:
            exchange_name: Name of the exchange (e.g., 'hyperliquid')
        """
        self.exchange_name = exchange_name
        self.logger = structlog.get_logger(f"kirby.collector.{exchange_name}")
        self.status = CollectorStatus.IDLE
        self.starlistings: list[dict[str, Any]] = []
        self.retry_count = 0
        self.last_error: Exception | None = None
        self.last_collection_time: datetime | None = None
        self._stop_event = asyncio.Event()
        self._connection_healthy = False

    async def initialize(self) -> None:
        """
        Initialize the collector by loading starlistings.

        This should be called before start().
        """
        self.logger.info("Initializing collector", exchange=self.exchange_name)

        # Load starlistings from database
        async with get_session() as session:
            starlisting_repo = StarlistingRepository(session)
            all_starlistings = await starlisting_repo.get_active_starlistings()

        # Filter for this exchange
        self.starlistings = [
            sl
            for sl in all_starlistings
            if sl.exchange.name == self.exchange_name
        ]

        self.logger.info(
            "Loaded starlistings",
            exchange=self.exchange_name,
            count=len(self.starlistings),
        )

        if not self.starlistings:
            self.logger.warning(
                "No active starlistings found for exchange",
                exchange=self.exchange_name,
            )

    async def start(self) -> None:
        """
        Start the collector with auto-restart on failure.

        This method handles:
        - Connection establishment
        - Data collection loop
        - Error handling and retry logic
        - Graceful shutdown
        """
        self.status = CollectorStatus.STARTING
        self.logger.info("Starting collector", exchange=self.exchange_name)

        while not self._stop_event.is_set():
            try:
                # Connect to exchange
                await self.connect()
                self._connection_healthy = True
                self.status = CollectorStatus.RUNNING
                self.retry_count = 0

                self.logger.info(
                    "Collector connected and running",
                    exchange=self.exchange_name,
                )

                # Run collection loop
                await self.collect()

            except asyncio.CancelledError:
                self.logger.info("Collector cancelled", exchange=self.exchange_name)
                break

            except Exception as e:
                self.status = CollectorStatus.ERROR
                self.last_error = e
                self._connection_healthy = False

                self.logger.error(
                    "Collector error",
                    exchange=self.exchange_name,
                    error=str(e),
                    retry_count=self.retry_count,
                    exc_info=True,
                )

                # Check retry limit
                if self.retry_count >= settings.collector_max_retries:
                    self.logger.error(
                        "Max retries reached, stopping collector",
                        exchange=self.exchange_name,
                        max_retries=settings.collector_max_retries,
                    )
                    break

                self.retry_count += 1

                # Wait before retry
                if not self._stop_event.is_set():
                    self.logger.info(
                        "Retrying connection",
                        exchange=self.exchange_name,
                        retry_in=settings.collector_restart_delay,
                    )
                    await asyncio.sleep(settings.collector_restart_delay)

            finally:
                await self.disconnect()

        self.status = CollectorStatus.STOPPED
        self.logger.info("Collector stopped", exchange=self.exchange_name)

    async def stop(self) -> None:
        """Stop the collector gracefully."""
        self.status = CollectorStatus.STOPPING
        self.logger.info("Stopping collector", exchange=self.exchange_name)
        self._stop_event.set()

    async def disconnect(self) -> None:
        """Disconnect from exchange (default implementation)."""
        self._connection_healthy = False

    @abstractmethod
    async def connect(self) -> None:
        """
        Connect to the exchange.

        Must be implemented by subclasses.
        Should establish WebSocket connection or initialize API client.
        """
        pass

    @abstractmethod
    async def collect(self) -> None:
        """
        Collect data from the exchange.

        Must be implemented by subclasses.
        Should run the main collection loop until stopped or error.
        """
        pass

    async def store_candles(
        self,
        candles: list[dict[str, Any]],
        starlisting_id: int,
    ) -> int:
        """
        Store candles to database using bulk insert.

        Args:
            candles: List of candle dictionaries
            starlisting_id: Starlisting ID

        Returns:
            Number of candles inserted
        """
        if not candles:
            return 0

        try:
            # Add starlisting_id to each candle
            for candle in candles:
                candle["starlisting_id"] = starlisting_id

            # Use asyncpg for high-performance bulk insert
            pool = await get_asyncpg_pool()
            candle_repo = CandleRepository(pool)
            count = await candle_repo.upsert_candles(candles)

            self.last_collection_time = utc_now()

            self.logger.debug(
                "Stored candles",
                exchange=self.exchange_name,
                starlisting_id=starlisting_id,
                count=count,
            )

            return count

        except Exception as e:
            self.logger.error(
                "Failed to store candles",
                exchange=self.exchange_name,
                starlisting_id=starlisting_id,
                error=str(e),
                exc_info=True,
            )
            raise

    def get_health(self) -> dict[str, Any]:
        """
        Get collector health status.

        Returns:
            Health status dictionary
        """
        return {
            "exchange": self.exchange_name,
            "status": self.status.value,
            "healthy": self._connection_healthy and self.status == CollectorStatus.RUNNING,
            "last_collection": self.last_collection_time.isoformat() if self.last_collection_time else None,
            "retry_count": self.retry_count,
            "last_error": str(self.last_error) if self.last_error else None,
            "starlistings_count": len(self.starlistings),
        }
