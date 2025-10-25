"""
Base collector class for exchange data ingestion.

Provides common functionality for all collectors:
- CCXT integration for market data and backfill
- Database connection management
- Error handling and reconnection logic
- Health monitoring and heartbeats
"""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import ccxt.async_support as ccxt

from src.db.asyncpg_pool import get_pool
from src.db.writer import DataWriter
from src.utils import get_logger
from src.utils.interval_manager import IntervalManager


class BaseCollector(ABC):
    """
    Abstract base class for exchange data collectors.

    Each collector is responsible for:
    1. Connecting to an exchange (via CCXT or custom WebSocket)
    2. Fetching/streaming market data across multiple intervals
    3. Writing data to TimescaleDB via DataWriter
    4. Handling errors and reconnections
    5. Sending periodic heartbeats

    Supports collecting multiple candle intervals (1m, 15m, 4h, etc.)
    simultaneously with optimal polling frequencies per interval.
    """

    def __init__(
        self,
        exchange_name: str,
        listing_id: int,
        symbol: str,
        intervals: List[str] = None,
        heartbeat_interval: int = 30,
        max_reconnect_attempts: int = 10,
        reconnect_delay: int = 5,
    ):
        """
        Initialize the base collector.

        Args:
            exchange_name: Exchange identifier (e.g., 'hyperliquid', 'binance')
            listing_id: Database listing ID for this market
            symbol: CCXT symbol format (e.g., 'BTC/USDC:USDC')
            intervals: List of candle intervals to collect (e.g., ['1m', '15m', '4h'])
            heartbeat_interval: Seconds between heartbeat logs
            max_reconnect_attempts: Maximum reconnection attempts (0 = infinite)
            reconnect_delay: Initial delay between reconnections (exponential backoff)
        """
        self.exchange_name = exchange_name
        self.listing_id = listing_id
        self.symbol = symbol
        self.heartbeat_interval = heartbeat_interval
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay = reconnect_delay

        # Validate and store intervals
        if intervals is None:
            intervals = ["1m"]  # Default to 1-minute candles
        self.intervals = IntervalManager.validate_intervals(intervals)

        # Track last candle timestamp per interval
        self.last_candle_timestamps: Dict[str, Optional[datetime]] = {
            interval: None for interval in self.intervals
        }

        self.logger = get_logger(f"{__name__}.{exchange_name}.{symbol}")
        self.ccxt_exchange: Optional[ccxt.Exchange] = None
        self.writer: Optional[DataWriter] = None
        self.is_running = False
        self.reconnect_count = 0

        self._heartbeat_task: Optional[asyncio.Task] = None
        self._main_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        """
        Initialize database connection and CCXT exchange.
        Must be called before start().
        """
        intervals_str = IntervalManager.format_interval_list(self.intervals)
        self.logger.info(
            f"Initializing collector for {self.exchange_name} {self.symbol} "
            f"(intervals: {intervals_str})"
        )

        # Get database pool and create writer
        pool = get_pool()
        if pool is None:
            raise RuntimeError("Database pool not initialized. Call init_pool() first.")
        self.writer = DataWriter(pool)

        # Initialize CCXT exchange
        self.ccxt_exchange = self._create_ccxt_exchange()
        if self.ccxt_exchange:
            await self.ccxt_exchange.load_markets()
            self.logger.info(f"Loaded {len(self.ccxt_exchange.markets)} markets from {self.exchange_name}")

        # Perform custom initialization
        await self.on_initialize()

    async def start(self) -> None:
        """
        Start the collector (non-blocking).
        Spawns background tasks for data collection and heartbeat.
        """
        if self.is_running:
            self.logger.warning("Collector already running")
            return

        self.is_running = True
        self.logger.info(f"Starting collector for {self.exchange_name} {self.symbol}")

        # Start heartbeat task
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        # Start main collection task
        self._main_task = asyncio.create_task(self._run_with_reconnect())

    async def stop(self) -> None:
        """
        Stop the collector gracefully.
        """
        self.logger.info(f"Stopping collector for {self.exchange_name} {self.symbol}")
        self.is_running = False

        # Cancel tasks
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._main_task:
            self._main_task.cancel()

        # Wait for tasks to complete
        tasks = [t for t in [self._heartbeat_task, self._main_task] if t]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # Close CCXT exchange
        if self.ccxt_exchange:
            await self.ccxt_exchange.close()

        await self.on_stop()

    async def _run_with_reconnect(self) -> None:
        """
        Main collection loop with automatic reconnection.
        """
        while self.is_running:
            try:
                # Run the collector implementation
                await self.run()

                # If run() completes without error, reset reconnect count
                self.reconnect_count = 0

            except asyncio.CancelledError:
                self.logger.info("Collector task cancelled")
                break

            except Exception as e:
                self.logger.error(f"Collector error: {e}", exc_info=True)

                # Check if we should reconnect
                self.reconnect_count += 1
                if self.max_reconnect_attempts > 0 and self.reconnect_count >= self.max_reconnect_attempts:
                    self.logger.error(
                        f"Max reconnection attempts ({self.max_reconnect_attempts}) reached. Stopping."
                    )
                    self.is_running = False
                    break

                # Exponential backoff
                delay = self.reconnect_delay * (2 ** (self.reconnect_count - 1))
                self.logger.info(
                    f"Reconnecting in {delay}s (attempt {self.reconnect_count}/{self.max_reconnect_attempts or 'infinite'})"
                )
                await asyncio.sleep(delay)

    async def _heartbeat_loop(self) -> None:
        """
        Send periodic heartbeat logs.
        """
        while self.is_running:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                if self.is_running:
                    await self.on_heartbeat()
                    self.logger.debug(
                        f"Heartbeat: {self.exchange_name} {self.symbol} (reconnects: {self.reconnect_count})"
                    )
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Heartbeat error: {e}")

    def _create_ccxt_exchange(self) -> Optional[ccxt.Exchange]:
        """
        Create CCXT exchange instance.
        Override if you need custom configuration.

        Returns:
            CCXT exchange instance or None if not using CCXT
        """
        try:
            exchange_class = getattr(ccxt, self.exchange_name.lower())
            return exchange_class({
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'swap',  # Default to futures/perpetuals
                },
            })
        except AttributeError:
            self.logger.warning(f"CCXT does not support {self.exchange_name}")
            return None

    # Abstract methods that subclasses must implement

    @abstractmethod
    async def run(self) -> None:
        """
        Main collection logic.
        This method should run continuously (loop or WebSocket connection).
        Will be called with automatic reconnection on failure.
        """
        pass

    # Optional hooks for subclasses

    async def on_initialize(self) -> None:
        """Hook called during initialization. Override to add custom setup."""
        pass

    async def on_stop(self) -> None:
        """Hook called during shutdown. Override to add custom cleanup."""
        pass

    async def on_heartbeat(self) -> None:
        """Hook called on each heartbeat. Override to add custom health checks."""
        pass

    # Helper methods for subclasses

    async def fetch_ohlcv_historical(
        self,
        interval: str = '1m',
        since: Optional[datetime] = None,
        limit: int = 1000,
    ) -> list[list]:
        """
        Fetch historical OHLCV data using CCXT.

        Args:
            interval: Candle interval (1m, 5m, 1h, etc.)
            since: Start timestamp (None for most recent)
            limit: Number of candles to fetch

        Returns:
            List of OHLCV arrays [[timestamp, open, high, low, close, volume], ...]
        """
        if not self.ccxt_exchange:
            raise RuntimeError("CCXT exchange not initialized")

        since_ms = int(since.timestamp() * 1000) if since else None
        return await self.ccxt_exchange.fetch_ohlcv(
            self.symbol,
            timeframe=interval,
            since=since_ms,
            limit=limit,
        )

    async def fetch_open_interest(self) -> Optional[dict[str, Any]]:
        """
        Fetch current open interest using CCXT.

        Returns:
            Open interest data or None if not supported
        """
        if not self.ccxt_exchange or not self.ccxt_exchange.has.get('fetchOpenInterest'):
            return None

        return await self.ccxt_exchange.fetch_open_interest(self.symbol)

    async def fetch_funding_rate(self) -> Optional[dict[str, Any]]:
        """
        Fetch current funding rate using CCXT.

        Returns:
            Funding rate data or None if not supported
        """
        if not self.ccxt_exchange or not self.ccxt_exchange.has.get('fetchFundingRate'):
            return None

        return await self.ccxt_exchange.fetch_funding_rate(self.symbol)
