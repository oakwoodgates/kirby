"""
Base backfiller for historical data ingestion.
"""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

import ccxt.async_support as ccxt

from src.db.asyncpg_pool import get_pool
from src.db.writer import DataWriter
from src.utils.logger import get_logger


class BaseBackfiller(ABC):
    """
    Abstract base class for all backfillers.

    Provides common functionality for historical data fetching:
    - CCXT exchange integration for REST API calls
    - Rate limiting and retry logic
    - Progress tracking
    - Database writing via DataWriter
    """

    def __init__(
        self,
        exchange_name: str,
        listing_id: int,
        symbol: str,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        batch_size: int = 1000,
        rate_limit_delay: float = 0.1,
        **kwargs,
    ):
        """
        Initialize base backfiller.

        Args:
            exchange_name: Name of exchange (e.g., 'hyperliquid')
            listing_id: Database listing ID
            symbol: CCXT symbol format (e.g., 'BTC/USDC:USDC')
            start_date: Start date for historical data (timezone-aware)
            end_date: End date for historical data (defaults to now if None)
            batch_size: Number of records to fetch per API call
            rate_limit_delay: Delay between API calls in seconds
            **kwargs: Additional exchange-specific parameters
        """
        self.exchange_name = exchange_name
        self.listing_id = listing_id
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date or datetime.now(timezone.utc)
        self.batch_size = batch_size
        self.rate_limit_delay = rate_limit_delay
        self.kwargs = kwargs

        # Initialize components
        self.logger = get_logger(f"{self.__class__.__name__}[{symbol}]")
        self.writer: Optional[DataWriter] = None
        self.exchange: Optional[ccxt.Exchange] = None

        # Progress tracking
        self.candles_fetched = 0
        self.funding_rates_fetched = 0
        self.open_interest_fetched = 0

    async def initialize(self) -> None:
        """
        Initialize backfiller (exchange connection, etc).
        """
        self.logger.info(f"Initializing {self.exchange_name} backfiller for {self.symbol}")

        # Get database pool and create writer
        pool = get_pool()
        if pool is None:
            raise RuntimeError("Database pool not initialized. Call init_pool() first.")
        self.writer = DataWriter(pool)

        # Initialize CCXT exchange
        exchange_class = getattr(ccxt, self.exchange_name)
        self.exchange = exchange_class({
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',  # Perpetual futures
            },
            **self.kwargs.get('exchange_options', {}),
        })

        await self.exchange.load_markets()
        self.logger.info(f"Exchange initialized: {self.exchange.id}")

        # Call subclass initialization
        await self.on_initialize()

    async def on_initialize(self) -> None:
        """
        Hook for subclass-specific initialization.
        Override this in subclasses if needed.
        """
        pass

    async def cleanup(self) -> None:
        """
        Cleanup resources (close exchange connection).
        """
        if self.exchange:
            await self.exchange.close()
            self.logger.info("Exchange connection closed")

        await self.on_cleanup()

    async def on_cleanup(self) -> None:
        """
        Hook for subclass-specific cleanup.
        Override this in subclasses if needed.
        """
        pass

    @abstractmethod
    async def backfill_candles(self) -> int:
        """
        Backfill historical candle data.

        Returns:
            Number of candles fetched and stored
        """
        pass

    @abstractmethod
    async def backfill_funding_rates(self) -> int:
        """
        Backfill historical funding rate data.

        Returns:
            Number of funding rate records fetched and stored
        """
        pass

    @abstractmethod
    async def backfill_open_interest(self) -> int:
        """
        Backfill historical open interest data.

        Returns:
            Number of open interest records fetched and stored
        """
        pass

    async def run_backfill(self, data_types: Optional[List[str]] = None) -> Dict[str, int]:
        """
        Run backfill for specified data types.

        Args:
            data_types: List of data types to backfill.
                       Options: ['candles', 'funding_rates', 'open_interest']
                       If None, backfills all types.

        Returns:
            Dictionary with counts of records fetched per data type
        """
        if data_types is None:
            data_types = ['candles', 'funding_rates', 'open_interest']

        results = {}

        try:
            await self.initialize()

            self.logger.info(
                f"Starting backfill from {self.start_date} to {self.end_date} "
                f"for data types: {', '.join(data_types)}"
            )

            # Backfill each data type
            if 'candles' in data_types:
                self.logger.info("Backfilling candles...")
                count = await self.backfill_candles()
                results['candles'] = count
                self.candles_fetched = count
                self.logger.info(f"Backfilled {count} candles")

            if 'funding_rates' in data_types:
                self.logger.info("Backfilling funding rates...")
                count = await self.backfill_funding_rates()
                results['funding_rates'] = count
                self.funding_rates_fetched = count
                self.logger.info(f"Backfilled {count} funding rates")

            if 'open_interest' in data_types:
                self.logger.info("Backfilling open interest...")
                count = await self.backfill_open_interest()
                results['open_interest'] = count
                self.open_interest_fetched = count
                self.logger.info(f"Backfilled {count} open interest records")

            self.logger.info(f"Backfill complete: {results}")

        finally:
            await self.cleanup()

        return results

    async def fetch_ohlcv_batch(
        self,
        since: int,
        limit: int = 1000,
        timeframe: str = '1m',
    ) -> List[List]:
        """
        Fetch OHLCV data batch from exchange.

        Args:
            since: Start timestamp in milliseconds
            limit: Number of candles to fetch
            timeframe: Candle timeframe (e.g., '1m', '5m', '1h')

        Returns:
            List of OHLCV arrays: [[timestamp, open, high, low, close, volume], ...]
        """
        if not self.exchange:
            raise RuntimeError("Exchange not initialized")

        try:
            ohlcv = await self.exchange.fetch_ohlcv(
                symbol=self.symbol,
                timeframe=timeframe,
                since=since,
                limit=limit,
            )
            return ohlcv

        except Exception as e:
            self.logger.error(f"Error fetching OHLCV: {e}", exc_info=True)
            return []

    def get_progress_summary(self) -> Dict[str, Any]:
        """
        Get summary of backfill progress.

        Returns:
            Dictionary with progress information
        """
        return {
            'exchange': self.exchange_name,
            'symbol': self.symbol,
            'listing_id': self.listing_id,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'candles_fetched': self.candles_fetched,
            'funding_rates_fetched': self.funding_rates_fetched,
            'open_interest_fetched': self.open_interest_fetched,
        }
