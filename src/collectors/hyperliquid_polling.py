"""
Hyperliquid collector using CCXT polling for market data.

This implementation uses CCXT's REST API to poll for:
- Candles (OHLCV) across multiple intervals (1m, 15m, 4h, 1d, etc.)
- Open interest
- Market ticker data

Each interval is collected independently with optimal polling frequencies:
- 1m polls every 30s
- 15m polls every 7.5 min
- 4h polls every 2 hours
- 1d polls every 12 hours

For production use with high-frequency updates, consider implementing
WebSocket connections using Hyperliquid's native API.
"""

import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from src.collectors.base import BaseCollector
from src.utils.interval_manager import IntervalManager


class HyperliquidPollingCollector(BaseCollector):
    """
    Hyperliquid perpetual futures collector using CCXT polling (fallback).

    Collects data across multiple intervals in parallel:
    - Candles (1m, 15m, 4h, 1d, etc.) - each polled at optimal frequency
    - Open interest
    - Market metadata (ticker)

    Each interval runs independently with its own polling schedule:
    - 1m candles polled every 30 seconds
    - 15m candles polled every 7.5 minutes
    - 4h candles polled every 2 hours
    - 1d candles polled every 12 hours

    Note: This is the polling fallback. For real-time data, use HyperliquidWebSocketCollector.
    """

    def __init__(
        self,
        listing_id: int,
        symbol: str,
        **kwargs,
    ):
        """
        Initialize Hyperliquid collector.

        Args:
            listing_id: Database listing ID
            symbol: CCXT symbol (e.g., 'BTC/USDC:USDC')
            **kwargs: Additional args passed to BaseCollector (including 'intervals')
        """
        super().__init__(
            exchange_name='hyperliquid',
            listing_id=listing_id,
            symbol=symbol,
            **kwargs,
        )

    async def run(self) -> None:
        """
        Main polling loop for Hyperliquid data collection.

        Spawns parallel tasks:
        - One task per interval for candle collection
        - One task for open interest (polls every 60s)
        - One task for market metadata (polls every 60s)
        """
        intervals_str = IntervalManager.format_interval_list(self.intervals)
        self.logger.info(f"Starting Hyperliquid polling for {self.symbol} (intervals: {intervals_str})")

        # Create parallel tasks for each interval
        tasks = []

        # Spawn a task for each candle interval
        for interval in self.intervals:
            task = asyncio.create_task(
                self._collect_interval(interval),
                name=f"candle_{interval}"
            )
            tasks.append(task)

        # Spawn tasks for other data types (poll every 60s)
        tasks.append(asyncio.create_task(self._collect_open_interest_loop(), name="open_interest"))
        tasks.append(asyncio.create_task(self._collect_market_metadata_loop(), name="market_metadata"))

        # Wait for all tasks to complete (they run until is_running=False)
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _collect_interval(self, interval: str) -> None:
        """
        Collect candles for a specific interval on its own schedule.

        Args:
            interval: Candle interval (e.g., '1m', '15m', '4h', '1d')
        """
        poll_freq = IntervalManager.get_poll_frequency(interval)
        self.logger.info(f"Starting {interval} candle collection (poll every {poll_freq}s)")

        while self.is_running:
            try:
                await self._collect_candle(interval)
            except Exception as e:
                self.logger.error(f"Error collecting {interval} candle: {e}", exc_info=True)

            # Wait for next poll
            await asyncio.sleep(poll_freq)

    async def _collect_open_interest_loop(self) -> None:
        """Poll open interest every 60 seconds."""
        while self.is_running:
            try:
                await self._collect_open_interest()
            except Exception as e:
                self.logger.error(f"Error in OI loop: {e}", exc_info=True)
            await asyncio.sleep(60)

    async def _collect_market_metadata_loop(self) -> None:
        """Poll market metadata every 60 seconds."""
        while self.is_running:
            try:
                await self._collect_market_metadata()
            except Exception as e:
                self.logger.error(f"Error in metadata loop: {e}", exc_info=True)
            await asyncio.sleep(60)

    async def _collect_candle(self, interval: str) -> None:
        """
        Fetch latest candle for a specific interval and write to database.

        Args:
            interval: Candle interval (e.g., '1m', '15m', '4h', '1d')
        """
        try:
            # Convert to CCXT timeframe format
            ccxt_timeframe = IntervalManager.get_ccxt_timeframe(interval)

            # Fetch last 2 candles to ensure we have the most recent complete one
            ohlcv = await self.fetch_ohlcv_historical(interval=ccxt_timeframe, limit=2)

            if not ohlcv:
                self.logger.warning(f"No OHLCV data received for {interval}")
                return

            # Get the most recent completed candle (second to last)
            # The last one might still be forming
            latest = ohlcv[-2] if len(ohlcv) >= 2 else ohlcv[-1]

            timestamp = datetime.fromtimestamp(latest[0] / 1000, tz=timezone.utc)

            # Skip if we've already processed this candle for this interval
            last_ts = self.last_candle_timestamps.get(interval)
            if last_ts and timestamp <= last_ts:
                self.logger.debug(f"{interval} candle {timestamp} already processed")
                return

            # Prepare candle data
            candle_data = {
                'listing_id': self.listing_id,
                'timestamp': timestamp,
                'interval': interval,
                'open': Decimal(str(latest[1])),
                'high': Decimal(str(latest[2])),
                'low': Decimal(str(latest[3])),
                'close': Decimal(str(latest[4])),
                'volume': Decimal(str(latest[5])),
                'trades_count': None,  # Not provided by CCXT for Hyperliquid
            }

            # Write to database
            await self.writer.insert_candles_batch([candle_data])

            # Update last timestamp for this interval
            self.last_candle_timestamps[interval] = timestamp
            self.logger.info(
                f"Stored {interval} candle: {self.symbol} @ {timestamp} | "
                f"O:{latest[1]} H:{latest[2]} L:{latest[3]} C:{latest[4]} V:{latest[5]}"
            )

        except Exception as e:
            self.logger.error(f"Error collecting {interval} candle: {e}", exc_info=True)
            raise

    async def _collect_open_interest(self) -> None:
        """
        Fetch current open interest and write to database.
        """
        try:
            oi_data = await self.fetch_open_interest()

            if not oi_data:
                self.logger.debug("Open interest not available")
                return

            # Parse Hyperliquid open interest response
            # Structure varies by exchange, check CCXT docs
            timestamp = datetime.now(timezone.utc)
            open_interest = oi_data.get('openInterestAmount')
            open_interest_value = oi_data.get('openInterestValue')

            if open_interest is None:
                self.logger.warning("Open interest data missing 'openInterestAmount'")
                return

            # Prepare OI data
            oi_record = {
                'listing_id': self.listing_id,
                'timestamp': timestamp,
                'open_interest': Decimal(str(open_interest)),
                'open_interest_value': Decimal(str(open_interest_value)) if open_interest_value else None,
            }

            # Write to database
            await self.writer.insert_open_interest_batch([oi_record])

            self.logger.debug(f"Stored open interest: {open_interest}")

        except Exception as e:
            self.logger.error(f"Error collecting open interest: {e}", exc_info=True)
            # Don't raise - OI is optional

    async def _collect_market_metadata(self) -> None:
        """
        Fetch market ticker/metadata and write to database.
        """
        try:
            if not self.ccxt_exchange:
                return

            # Fetch ticker data
            ticker = await self.ccxt_exchange.fetch_ticker(self.symbol)

            if not ticker:
                self.logger.warning("No ticker data received")
                return

            timestamp = datetime.now(timezone.utc)

            # Prepare market metadata
            metadata = {
                'listing_id': self.listing_id,
                'timestamp': timestamp,
                'bid': Decimal(str(ticker['bid'])) if ticker.get('bid') else None,
                'ask': Decimal(str(ticker['ask'])) if ticker.get('ask') else None,
                'last_price': Decimal(str(ticker['last'])) if ticker.get('last') else None,
                'volume_24h': Decimal(str(ticker['baseVolume'])) if ticker.get('baseVolume') else None,
                'volume_quote_24h': Decimal(str(ticker['quoteVolume'])) if ticker.get('quoteVolume') else None,
                'price_change_24h': Decimal(str(ticker['change'])) if ticker.get('change') else None,
                'percentage_change_24h': Decimal(str(ticker['percentage'])) if ticker.get('percentage') else None,
                'high_24h': Decimal(str(ticker['high'])) if ticker.get('high') else None,
                'low_24h': Decimal(str(ticker['low'])) if ticker.get('low') else None,
                'data': json.dumps(ticker.get('info')) if ticker.get('info') else None,  # Store raw exchange data as JSON string
            }

            # Write to database
            await self.writer.insert_market_metadata_batch([metadata])

            self.logger.debug(
                f"Stored ticker: Last={ticker.get('last')} "
                f"Bid={ticker.get('bid')} Ask={ticker.get('ask')} "
                f"Vol24h={ticker.get('baseVolume')}"
            )

        except Exception as e:
            self.logger.error(f"Error collecting market metadata: {e}", exc_info=True)
            # Don't raise - metadata is optional

    async def on_heartbeat(self) -> None:
        """
        Log health information on each heartbeat.
        Shows last candle timestamp for each interval.
        """
        # Build status for each interval
        interval_status = []
        for interval in self.intervals:
            last_ts = self.last_candle_timestamps.get(interval)
            ts_str = last_ts.strftime('%H:%M:%S') if last_ts else 'None'
            poll_freq = IntervalManager.get_poll_frequency(interval)
            interval_status.append(f"{interval}:{ts_str}({poll_freq}s)")

        status_str = " | ".join(interval_status)
        self.logger.info(f"Hyperliquid {self.symbol} | {status_str}")
