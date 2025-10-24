"""
Hyperliquid collector using CCXT polling for market data.

This implementation uses CCXT's REST API to poll for:
- 1-minute candles (OHLCV)
- Open interest
- Market ticker data

For production use with high-frequency updates, consider implementing
WebSocket connections using Hyperliquid's native API.
"""

import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from src.collectors.base import BaseCollector


class HyperliquidPollingCollector(BaseCollector):
    """
    Hyperliquid perpetual futures collector using CCXT polling (fallback).

    Polls every 60 seconds for:
    - Latest 1m candle
    - Open interest
    - Market metadata (ticker)

    Note: This is the polling fallback. For real-time data, use HyperliquidWebSocketCollector.
    """

    def __init__(
        self,
        listing_id: int,
        symbol: str,
        poll_interval: int = 60,
        **kwargs,
    ):
        """
        Initialize Hyperliquid collector.

        Args:
            listing_id: Database listing ID
            symbol: CCXT symbol (e.g., 'BTC/USDC:USDC')
            poll_interval: Seconds between polls (default 60 for 1m candles)
            **kwargs: Additional args passed to BaseCollector
        """
        super().__init__(
            exchange_name='hyperliquid',
            listing_id=listing_id,
            symbol=symbol,
            **kwargs,
        )
        self.poll_interval = poll_interval
        self.last_candle_timestamp: Optional[datetime] = None

    async def run(self) -> None:
        """
        Main polling loop for Hyperliquid data collection.
        """
        self.logger.info(f"Starting Hyperliquid polling for {self.symbol} every {self.poll_interval}s")

        while self.is_running:
            try:
                # Fetch and store latest candle
                await self._collect_candle()

                # Fetch and store open interest
                await self._collect_open_interest()

                # Fetch and store market metadata
                await self._collect_market_metadata()

            except Exception as e:
                self.logger.error(f"Error during collection cycle: {e}", exc_info=True)

            # Wait for next poll
            await asyncio.sleep(self.poll_interval)

    async def _collect_candle(self) -> None:
        """
        Fetch latest 1m candle and write to database.
        """
        try:
            # Fetch last 2 candles to ensure we have the most recent complete one
            ohlcv = await self.fetch_ohlcv_historical(interval='1m', limit=2)

            if not ohlcv:
                self.logger.warning("No OHLCV data received")
                return

            # Get the most recent completed candle (second to last)
            # The last one might still be forming
            latest = ohlcv[-2] if len(ohlcv) >= 2 else ohlcv[-1]

            timestamp = datetime.fromtimestamp(latest[0] / 1000, tz=timezone.utc)

            # Skip if we've already processed this candle
            if self.last_candle_timestamp and timestamp <= self.last_candle_timestamp:
                self.logger.debug(f"Candle {timestamp} already processed")
                return

            # Prepare candle data
            candle_data = {
                'listing_id': self.listing_id,
                'timestamp': timestamp,
                'interval': '1m',
                'open': Decimal(str(latest[1])),
                'high': Decimal(str(latest[2])),
                'low': Decimal(str(latest[3])),
                'close': Decimal(str(latest[4])),
                'volume': Decimal(str(latest[5])),
                'trades_count': None,  # Not provided by CCXT for Hyperliquid
            }

            # Write to database
            await self.writer.insert_candles_batch([candle_data])

            self.last_candle_timestamp = timestamp
            self.logger.info(
                f"Stored candle: {self.symbol} @ {timestamp} | "
                f"O:{latest[1]} H:{latest[2]} L:{latest[3]} C:{latest[4]} V:{latest[5]}"
            )

        except Exception as e:
            self.logger.error(f"Error collecting candle: {e}", exc_info=True)
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
        """
        last_candle = self.last_candle_timestamp.strftime('%H:%M:%S') if self.last_candle_timestamp else 'None'
        self.logger.info(
            f"Hyperliquid {self.symbol} | Last candle: {last_candle} | Poll interval: {self.poll_interval}s"
        )
