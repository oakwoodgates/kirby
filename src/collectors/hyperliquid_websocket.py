"""
Hyperliquid WebSocket collector for real-time market data.

Uses Hyperliquid Python SDK's WebSocket support to subscribe to:
- candle (1m interval) - Real-time OHLCV candlestick updates
- l2Book - Full order book snapshots with bid/ask depth
- activeAssetCtx - Asset context containing funding rate, open interest, volume, prices

This provides sub-second latency data delivery compared to polling.
"""

import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from hyperliquid.info import Info

from src.collectors.base import BaseCollector


class HyperliquidWebSocketCollector(BaseCollector):
    """
    Hyperliquid perpetual futures collector using WebSocket subscriptions.

    Subscribes to real-time data streams for a single coin via:
    - Candle updates (1m OHLCV)
    - L2 order book snapshots
    - Active asset context (funding, OI, volumes, prices)
    """

    def __init__(
        self,
        listing_id: int,
        symbol: str,
        coin_name: str,
        **kwargs,
    ):
        """
        Initialize Hyperliquid WebSocket collector.

        Args:
            listing_id: Database listing ID
            symbol: CCXT symbol format (e.g., 'BTC/USDC:USDC') - used for REST fallback
            coin_name: Hyperliquid coin name (e.g., 'BTC') - used for WebSocket subscriptions
            **kwargs: Additional args passed to BaseCollector
        """
        super().__init__(
            exchange_name='hyperliquid',
            listing_id=listing_id,
            symbol=symbol,
            **kwargs,
        )
        self.coin_name = coin_name
        self.info: Optional[Info] = None
        self.subscription_ids: Dict[str, int] = {}
        self.loop: Optional[asyncio.AbstractEventLoop] = None  # Store event loop reference

        # Track last received data timestamps for monitoring
        self.last_candle_time: Optional[datetime] = None
        self.last_l2book_time: Optional[datetime] = None
        self.last_asset_ctx_time: Optional[datetime] = None

    async def on_initialize(self) -> None:
        """
        Initialize Hyperliquid SDK Info object with WebSocket support.
        """
        self.logger.info(f"Initializing Hyperliquid WebSocket for {self.coin_name}")

        # Initialize Info with WebSocket enabled
        self.info = Info(skip_ws=False)

        self.logger.info("Hyperliquid WebSocket Info object created")

    async def run(self) -> None:
        """
        Main WebSocket collection loop.

        Subscribes to all channels and keeps connection alive.
        The SDK handles reconnection automatically.
        """
        if not self.info:
            raise RuntimeError("Info object not initialized. Call initialize() first.")

        # Store event loop reference for WebSocket callbacks
        self.loop = asyncio.get_running_loop()

        self.logger.info(f"Starting Hyperliquid WebSocket subscriptions for {self.coin_name}")

        # Subscribe to all channels
        await self._subscribe_all_channels()

        self.logger.info(
            f"WebSocket subscriptions active for {self.coin_name} "
            f"(candle, l2Book, activeAssetCtx)"
        )

        # Keep the collector running - WebSocket messages come via callbacks
        # The SDK manages the connection lifecycle
        while self.is_running:
            await asyncio.sleep(1)

    async def _subscribe_all_channels(self) -> None:
        """
        Subscribe to all required WebSocket channels.
        """
        try:
            # Subscribe to 1-minute candles
            sub_id_candle = self.info.subscribe(
                {"type": "candle", "coin": self.coin_name, "interval": "1m"},
                callback=self._handle_candle,
            )
            self.subscription_ids['candle'] = sub_id_candle
            self.logger.info(f"Subscribed to candle (sub_id={sub_id_candle})")

            # Subscribe to L2 order book
            sub_id_l2book = self.info.subscribe(
                {"type": "l2Book", "coin": self.coin_name},
                callback=self._handle_l2book,
            )
            self.subscription_ids['l2Book'] = sub_id_l2book
            self.logger.info(f"Subscribed to l2Book (sub_id={sub_id_l2book})")

            # Subscribe to asset context (funding, OI, volume, prices)
            sub_id_ctx = self.info.subscribe(
                {"type": "activeAssetCtx", "coin": self.coin_name},
                callback=self._handle_asset_ctx,
            )
            self.subscription_ids['activeAssetCtx'] = sub_id_ctx
            self.logger.info(f"Subscribed to activeAssetCtx (sub_id={sub_id_ctx})")

        except Exception as e:
            self.logger.error(f"Error subscribing to channels: {e}", exc_info=True)
            raise

    def _handle_candle(self, message: Any) -> None:
        """
        Handle incoming candle (OHLCV) messages.

        Expected message format (from Hyperliquid docs):
        {
            "channel": "candle",
            "data": {
                "t": 1234567890000,       # Start timestamp (ms)
                "T": 1234567949999,       # End timestamp (ms)
                "s": "BTC",               # Symbol
                "i": "1m",                # Interval
                "o": "50000.0",           # Open
                "h": "50100.0",           # High
                "l": "49900.0",           # Low
                "c": "50050.0",           # Close
                "v": "123.45",            # Volume
                "n": 100                  # Number of trades
            }
        }
        """
        try:
            # Parse message
            if not isinstance(message, dict) or 'data' not in message:
                self.logger.warning(f"Invalid candle message format: {message}")
                return

            data = message['data']

            # Extract timestamp (use start time 't')
            timestamp = datetime.fromtimestamp(data['t'] / 1000, tz=timezone.utc)

            # Check if we've already processed this candle
            if self.last_candle_time and timestamp <= self.last_candle_time:
                self.logger.debug(f"Candle {timestamp} already processed, skipping")
                return

            # Prepare candle data for database
            candle_data = {
                'listing_id': self.listing_id,
                'timestamp': timestamp,
                'interval': '1m',
                'open': Decimal(str(data['o'])),
                'high': Decimal(str(data['h'])),
                'low': Decimal(str(data['l'])),
                'close': Decimal(str(data['c'])),
                'volume': Decimal(str(data['v'])),
                'trades_count': data.get('n'),  # Number of trades
            }

            # Store in database (async write from callback thread)
            if self.loop:
                asyncio.run_coroutine_threadsafe(self._store_candle(candle_data), self.loop)

            self.last_candle_time = timestamp
            self.logger.info(
                f"Received candle: {self.coin_name} @ {timestamp} | "
                f"O:{data['o']} H:{data['h']} L:{data['l']} C:{data['c']} V:{data['v']}"
            )

        except Exception as e:
            self.logger.error(f"Error handling candle message: {e}", exc_info=True)

    async def _store_candle(self, candle_data: dict) -> None:
        """Store candle data in database."""
        try:
            await self.writer.insert_candles_batch([candle_data])
        except Exception as e:
            self.logger.error(f"Failed to store candle: {e}", exc_info=True)

    def _handle_l2book(self, message: Any) -> None:
        """
        Handle incoming L2 order book messages.

        Expected message format:
        {
            "channel": "l2Book",
            "data": {
                "coin": "BTC",
                "time": 1234567890000,
                "levels": [
                    [{"px": "50000.0", "sz": "1.5", "n": 3}, ...],  // bids (descending)
                    [{"px": "50001.0", "sz": "2.0", "n": 5}, ...]   // asks (ascending)
                ]
            }
        }
        """
        try:
            if not isinstance(message, dict) or 'data' not in message:
                self.logger.warning(f"Invalid l2Book message format: {message}")
                return

            data = message['data']
            timestamp = datetime.now(timezone.utc)

            # Extract best bid and ask from order book
            levels = data.get('levels', [])
            if len(levels) < 2:
                self.logger.warning("L2 book missing bid/ask levels")
                return

            bids = levels[0]  # Bids are first array
            asks = levels[1]  # Asks are second array

            if not bids or not asks:
                self.logger.warning("L2 book has empty bid or ask side")
                return

            # Best bid is first in bids array, best ask is first in asks array
            best_bid = Decimal(str(bids[0]['px'])) if bids else None
            best_ask = Decimal(str(asks[0]['px'])) if asks else None

            # Store as market metadata (bid/ask snapshot)
            metadata = {
                'listing_id': self.listing_id,
                'timestamp': timestamp,
                'bid': best_bid,
                'ask': best_ask,
                'last_price': None,  # Not in l2Book, comes from activeAssetCtx
                'volume_24h': None,
                'volume_quote_24h': None,
                'price_change_24h': None,
                'percentage_change_24h': None,
                'high_24h': None,
                'low_24h': None,
                'data': json.dumps(data),  # Store raw order book data
            }

            if self.loop:
                asyncio.run_coroutine_threadsafe(self._store_market_metadata(metadata), self.loop)

            self.last_l2book_time = timestamp
            self.logger.debug(
                f"L2 Book: {self.coin_name} | Bid={best_bid} Ask={best_ask} "
                f"Spread={float(best_ask - best_bid) if best_bid and best_ask else 'N/A'}"
            )

        except Exception as e:
            self.logger.error(f"Error handling l2Book message: {e}", exc_info=True)

    async def _store_market_metadata(self, metadata: dict) -> None:
        """Store market metadata in database."""
        try:
            await self.writer.insert_market_metadata_batch([metadata])
        except Exception as e:
            self.logger.error(f"Failed to store market metadata: {e}", exc_info=True)

    def _handle_asset_ctx(self, message: Any) -> None:
        """
        Handle incoming asset context messages (funding, OI, volume, prices).

        Expected message format:
        {
            "channel": "activeAssetCtx",
            "data": [{
                "coin": "BTC",
                "ctx": {
                    "funding": "0.0001",
                    "openInterest": "1234567.89",
                    "markPx": "50000.0",
                    "dayNtlVlm": "500000000.0",
                    "prevDayPx": "49500.0",
                    ...
                }
            }, ...]
        }
        """
        try:
            if not isinstance(message, dict) or 'data' not in message:
                self.logger.warning(f"Invalid activeAssetCtx message format: {message}")
                return

            # Data is an array of asset contexts
            data_list = message['data'] if isinstance(message['data'], list) else [message['data']]

            # Find our coin in the list
            our_ctx = None
            for item in data_list:
                if item.get('coin') == self.coin_name:
                    our_ctx = item.get('ctx', {})
                    break

            if not our_ctx:
                self.logger.debug(f"No context data for {self.coin_name} in message")
                return

            timestamp = datetime.now(timezone.utc)

            # Extract funding rate
            funding_rate = our_ctx.get('funding')
            if funding_rate is not None:
                funding_data = {
                    'listing_id': self.listing_id,
                    'timestamp': timestamp,
                    'rate': Decimal(str(funding_rate)),
                    'predicted_rate': None,  # Not provided
                    'mark_price': Decimal(str(our_ctx['markPx'])) if our_ctx.get('markPx') else None,
                    'index_price': None,  # Not provided in this message
                    'premium': None,  # Can calculate if needed
                    'next_funding_time': None,  # Not provided
                }
                if self.loop:
                    asyncio.run_coroutine_threadsafe(self._store_funding_rate(funding_data), self.loop)

            # Extract open interest
            open_interest = our_ctx.get('openInterest')
            if open_interest is not None:
                oi_data = {
                    'listing_id': self.listing_id,
                    'timestamp': timestamp,
                    'open_interest': Decimal(str(open_interest)),
                    'open_interest_value': None,  # Would need to calculate with price
                }
                if self.loop:
                    asyncio.run_coroutine_threadsafe(self._store_open_interest(oi_data), self.loop)

            # Extract market stats for metadata
            mark_price = our_ctx.get('markPx')
            day_volume = our_ctx.get('dayNtlVlm')  # Notional 24h volume
            prev_day_price = our_ctx.get('prevDayPx')

            if mark_price:
                # Calculate 24h change
                price_change = None
                percentage_change = None
                if prev_day_price:
                    price_change = Decimal(str(mark_price)) - Decimal(str(prev_day_price))
                    percentage_change = (price_change / Decimal(str(prev_day_price))) * 100

                metadata = {
                    'listing_id': self.listing_id,
                    'timestamp': timestamp,
                    'bid': None,  # Comes from l2Book
                    'ask': None,  # Comes from l2Book
                    'last_price': Decimal(str(mark_price)),
                    'volume_24h': None,  # Base volume not provided
                    'volume_quote_24h': Decimal(str(day_volume)) if day_volume else None,
                    'price_change_24h': price_change,
                    'percentage_change_24h': percentage_change,
                    'high_24h': None,  # Not provided
                    'low_24h': None,  # Not provided
                    'data': json.dumps(our_ctx),
                }
                if self.loop:
                    asyncio.run_coroutine_threadsafe(self._store_market_metadata(metadata), self.loop)

            self.last_asset_ctx_time = timestamp
            self.logger.debug(
                f"Asset Context: {self.coin_name} | "
                f"Funding={funding_rate} OI={open_interest} Mark={mark_price} Vol24h={day_volume}"
            )

        except Exception as e:
            self.logger.error(f"Error handling activeAssetCtx message: {e}", exc_info=True)

    async def _store_funding_rate(self, funding_data: dict) -> None:
        """Store funding rate in database."""
        try:
            await self.writer.insert_funding_rates_batch([funding_data])
        except Exception as e:
            self.logger.error(f"Failed to store funding rate: {e}", exc_info=True)

    async def _store_open_interest(self, oi_data: dict) -> None:
        """Store open interest in database."""
        try:
            await self.writer.insert_open_interest_batch([oi_data])
        except Exception as e:
            self.logger.error(f"Failed to store open interest: {e}", exc_info=True)

    async def on_stop(self) -> None:
        """
        Unsubscribe from all channels and cleanup resources.

        Explicitly unsubscribes from all active WebSocket channels to ensure
        clean shutdown and prevent resource leaks.
        """
        self.logger.info(f"Unsubscribing from all channels for {self.coin_name}")

        if self.info and self.subscription_ids:
            for channel, sub_id in list(self.subscription_ids.items()):
                try:
                    # Build unsubscribe payload based on channel type
                    if channel == "candle":
                        unsub_payload = {"type": "candle", "coin": self.coin_name, "interval": "1m"}
                    elif channel == "l2Book":
                        unsub_payload = {"type": "l2Book", "coin": self.coin_name}
                    elif channel == "activeAssetCtx":
                        unsub_payload = {"type": "activeAssetCtx", "coin": self.coin_name}
                    else:
                        self.logger.warning(f"Unknown channel type: {channel}")
                        continue

                    # Unsubscribe using SDK method
                    self.info.unsubscribe(unsub_payload, sub_id)
                    self.logger.debug(f"Unsubscribed from {channel} (sub_id={sub_id})")

                except Exception as e:
                    self.logger.error(f"Error unsubscribing from {channel}: {e}", exc_info=True)

            # Clear subscription tracking
            self.subscription_ids.clear()

        self.logger.info("WebSocket cleanup complete")

    async def on_heartbeat(self) -> None:
        """
        Log health information on each heartbeat.
        """
        last_candle = self.last_candle_time.strftime('%H:%M:%S') if self.last_candle_time else 'None'
        last_l2 = self.last_l2book_time.strftime('%H:%M:%S') if self.last_l2book_time else 'None'
        last_ctx = self.last_asset_ctx_time.strftime('%H:%M:%S') if self.last_asset_ctx_time else 'None'

        self.logger.info(
            f"WS {self.coin_name} | Candle: {last_candle} | L2: {last_l2} | Ctx: {last_ctx}"
        )
