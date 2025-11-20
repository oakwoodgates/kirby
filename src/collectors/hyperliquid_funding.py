"""
Hyperliquid funding rate and open interest collector.

Collects real-time funding rate and open interest data via WebSocket.
"""
import asyncio
import json
from datetime import datetime
from decimal import Decimal
from typing import Any

import websockets
from websockets.client import WebSocketClientProtocol

from src.collectors.base import BaseCollector
from src.db.connection import get_asyncpg_pool, get_session
from src.db.repositories import StarlistingRepository
from src.utils.helpers import timestamp_to_datetime, truncate_to_minute, utc_now


class HyperliquidFundingCollector(BaseCollector):
    """
    Hyperliquid WebSocket collector for funding rates and open interest.

    Subscribes to asset context updates for configured starlistings.
    """

    WEBSOCKET_URL = "wss://api.hyperliquid.xyz/ws"

    def __init__(self):
        """Initialize Hyperliquid funding collector."""
        super().__init__("hyperliquid_funding")
        self.ws: WebSocketClientProtocol | None = None
        self.subscriptions: dict[str, int] = {}  # coin -> trading_pair_id mapping

        # Buffering for 1-minute intervals
        self.funding_buffer: dict[str, dict[str, Any]] = {}  # coin -> latest funding data
        self.oi_buffer: dict[str, dict[str, Any]] = {}  # coin -> latest OI data
        self.flush_task: asyncio.Task | None = None

    async def initialize(self) -> None:
        """
        Initialize the collector by loading starlistings from hyperliquid exchange.

        Override to load starlistings from the 'hyperliquid' exchange instead of 'hyperliquid_funding'.
        """
        self.logger.info("Initializing collector", exchange=self.exchange_name)

        # Load starlistings from database for hyperliquid exchange
        session = await get_session()
        try:
            starlisting_repo = StarlistingRepository(session)
            all_starlistings = await starlisting_repo.get_active_starlistings()
        finally:
            await session.close()

        # Filter for hyperliquid exchange (not hyperliquid_funding)
        self.starlistings = [
            sl
            for sl in all_starlistings
            if sl.exchange.name == "hyperliquid"
        ]

        self.logger.info(
            "Loaded starlistings",
            exchange=self.exchange_name,
            count=len(self.starlistings),
        )

        if not self.starlistings:
            self.logger.warning("No active starlistings found for exchange", exchange=self.exchange_name)

    async def connect(self) -> None:
        """Connect to Hyperliquid WebSocket API."""
        self.logger.info("Connecting to Hyperliquid WebSocket for funding data", url=self.WEBSOCKET_URL)

        try:
            self.ws = await websockets.connect(
                self.WEBSOCKET_URL,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10,
            )

            self.logger.info("Connected to Hyperliquid WebSocket for funding")

            # Subscribe to asset contexts for all unique coins
            await self._subscribe_to_asset_contexts()

            # Start periodic flush task (every 1 minute)
            await self._start_flush_task()

        except Exception as e:
            self.logger.error(
                "Failed to connect to Hyperliquid WebSocket",
                error=str(e),
                exc_info=True,
            )
            raise

    async def disconnect(self) -> None:
        """Disconnect from Hyperliquid WebSocket."""
        # Stop flush task first
        await self._stop_flush_task()

        if self.ws:
            try:
                await self.ws.close()
                self.logger.info("Disconnected from Hyperliquid WebSocket")
            except Exception as e:
                self.logger.error(
                    "Error disconnecting from WebSocket",
                    error=str(e),
                )
            finally:
                self.ws = None
                self.subscriptions.clear()
                # Clear buffers
                self.funding_buffer.clear()
                self.oi_buffer.clear()

        await super().disconnect()

    async def _subscribe_to_asset_contexts(self) -> None:
        """Subscribe to activeAssetCtx updates for all unique coins."""
        if not self.ws:
            raise RuntimeError("WebSocket not connected")

        # Get unique coins from starlistings
        # Map coin to trading_pair_id (since funding/OI are per trading pair, not interval)
        unique_coins = {}
        for starlisting in self.starlistings:
            coin = starlisting.coin.symbol
            if coin not in unique_coins:
                unique_coins[coin] = starlisting.trading_pair_id

        for coin, trading_pair_id in unique_coins.items():
            # Create subscription message
            subscription = {
                "method": "subscribe",
                "subscription": {
                    "type": "activeAssetCtx",
                    "coin": coin,
                },
            }

            # Send subscription
            await self.ws.send(json.dumps(subscription))

            # Track subscription
            self.subscriptions[coin] = trading_pair_id

            self.logger.info(
                "Subscribed to asset context",
                coin=coin,
                trading_pair_id=trading_pair_id,
            )

        self.logger.info(
            "Subscribed to all asset contexts",
            subscription_count=len(self.subscriptions),
        )

    async def collect(self) -> None:
        """
        Collect funding rate and OI data from WebSocket.

        Runs continuously until stopped or error.
        """
        if not self.ws:
            raise RuntimeError("WebSocket not connected")

        self.logger.info("Starting funding data collection")

        try:
            async for message in self.ws:
                # Check if stop requested
                if self._stop_event.is_set():
                    self.logger.info("Stop event detected, exiting collection loop")
                    break

                try:
                    # Parse message
                    data = json.loads(message)

                    # Log message receipt
                    self.logger.debug("Received WebSocket message", channel=data.get("channel"))

                    # Process asset context update
                    await self._process_message(data)

                except json.JSONDecodeError as e:
                    self.logger.warning(
                        "Failed to parse WebSocket message",
                        error=str(e),
                        message=message[:200],  # Log first 200 chars
                    )
                except Exception as e:
                    self.logger.error(
                        "Error processing message",
                        error=str(e),
                        exc_info=True,
                    )

        except websockets.ConnectionClosed as e:
            self.logger.warning(
                "WebSocket connection closed",
                code=e.code,
                reason=e.reason,
            )
            raise
        except Exception as e:
            self.logger.error(
                "Error in collection loop",
                error=str(e),
                exc_info=True,
            )
            raise

    async def _process_message(self, data: dict[str, Any]) -> None:
        """
        Process a WebSocket message.

        Args:
            data: Parsed JSON message from WebSocket
        """
        # Check if this is an activeAssetCtx update
        if data.get("channel") != "activeAssetCtx":
            # Not an asset context update, might be subscription confirmation
            self.logger.debug("Received non-activeAssetCtx message", data=data)
            return

        # Extract message data
        msg_data = data.get("data")
        if not msg_data:
            self.logger.warning("Asset context message missing data field", data=data)
            return

        # Get coin from message data
        coin = msg_data.get("coin")
        if not coin:
            self.logger.warning("Asset context data missing coin", msg_data=msg_data)
            return

        # Extract the actual context data (nested inside "ctx")
        ctx_data = msg_data.get("ctx")
        if not ctx_data:
            self.logger.warning("Asset context missing ctx field", msg_data=msg_data)
            return

        # Find all starlistings for this coin (there may be multiple intervals)
        matching_starlistings = [
            sl for sl in self.starlistings if sl.coin.symbol == coin
        ]

        if not matching_starlistings:
            self.logger.warning(
                "Received context for unknown coin",
                coin=coin,
            )
            return

        try:
            current_time = utc_now()

            # Extract funding rate data
            funding_data = self._extract_funding_data(ctx_data, current_time)

            # Extract open interest data
            oi_data = self._extract_open_interest_data(ctx_data, current_time)

            # Get canonical starlisting (first one for this coin)
            # Funding/OI are per trading pair, not per interval
            canonical_starlisting = matching_starlistings[0]

            # Buffer data (will be flushed every minute)
            # Store the latest value for each coin - overwrites previous updates within the same minute
            if funding_data:
                self.funding_buffer[coin] = {
                    "trading_pair_id": canonical_starlisting.trading_pair_id,
                    **funding_data,
                }

            if oi_data:
                self.oi_buffer[coin] = {
                    "trading_pair_id": canonical_starlisting.trading_pair_id,
                    **oi_data,
                }

            self.logger.debug(
                "Buffered funding/OI data",
                coin=coin,
                trading_pair_id=canonical_starlisting.trading_pair_id,
                funding_rate=str(funding_data.get("funding_rate")) if funding_data else None,
                open_interest=str(oi_data.get("open_interest")) if oi_data else None,
            )

        except Exception as e:
            self.logger.error(
                "Failed to process asset context",
                coin=coin,
                error=str(e),
                exc_info=True,
            )

    def _extract_funding_data(
        self, ctx_data: dict[str, Any], current_time: datetime
    ) -> dict[str, Any] | None:
        """Extract funding rate data from asset context."""
        try:
            funding_rate_str = ctx_data.get("funding")
            if funding_rate_str is None:
                return None

            funding_data = {
                "time": current_time,
                "funding_rate": Decimal(funding_rate_str),
                "premium": Decimal(ctx_data["premium"]) if "premium" in ctx_data else None,
                "mark_price": Decimal(ctx_data["markPx"]) if "markPx" in ctx_data else None,
                "index_price": Decimal(ctx_data["oraclePx"]) if "oraclePx" in ctx_data else None,
                "oracle_price": Decimal(ctx_data["oraclePx"]) if "oraclePx" in ctx_data else None,
                "mid_price": Decimal(ctx_data["midPx"]) if "midPx" in ctx_data else None,
                "next_funding_time": None,  # Hyperliquid doesn't provide this in context
            }

            return funding_data

        except (ValueError, KeyError) as e:
            self.logger.warning(
                "Failed to extract funding data",
                error=str(e),
                ctx_data=ctx_data,
            )
            return None

    def _extract_open_interest_data(
        self, ctx_data: dict[str, Any], current_time: datetime
    ) -> dict[str, Any] | None:
        """Extract open interest data from asset context."""
        try:
            oi_str = ctx_data.get("openInterest")
            if oi_str is None:
                return None

            oi_data = {
                "time": current_time,
                "open_interest": Decimal(oi_str),
                "notional_value": None,  # Calculate if we have price
                "day_base_volume": Decimal(ctx_data["dayBaseVlm"]) if "dayBaseVlm" in ctx_data else None,
                "day_notional_volume": Decimal(ctx_data["dayNtlVlm"]) if "dayNtlVlm" in ctx_data else None,
            }

            # Calculate notional value if we have mark price
            if "markPx" in ctx_data and ctx_data["markPx"]:
                mark_price = Decimal(ctx_data["markPx"])
                oi_data["notional_value"] = oi_data["open_interest"] * mark_price

            return oi_data

        except (ValueError, KeyError) as e:
            self.logger.warning(
                "Failed to extract open interest data",
                error=str(e),
                ctx_data=ctx_data,
            )
            return None

    async def _start_flush_task(self) -> None:
        """Start the periodic flush task that runs every minute."""
        if self.flush_task is not None:
            self.logger.warning("Flush task already running")
            return

        self.flush_task = asyncio.create_task(self._flush_loop())
        self.logger.info("Started flush task (1-minute intervals)")

    async def _stop_flush_task(self) -> None:
        """Stop the periodic flush task."""
        if self.flush_task is None:
            return

        self.flush_task.cancel()
        try:
            await self.flush_task
        except asyncio.CancelledError:
            pass
        finally:
            self.flush_task = None
            self.logger.info("Stopped flush task")

    async def _flush_loop(self) -> None:
        """
        Periodic flush loop that runs every minute on the minute boundary.

        Flushes buffered funding/OI data to database every 60 seconds.
        """
        while True:
            try:
                # Calculate time to next minute boundary
                now = utc_now()
                seconds_until_next_minute = 60 - now.second

                # Wait until the top of the next minute
                await asyncio.sleep(seconds_until_next_minute)

                # Flush buffers
                await self._flush_buffers()

            except asyncio.CancelledError:
                self.logger.info("Flush loop cancelled")
                raise
            except Exception as e:
                self.logger.error(
                    "Error in flush loop",
                    error=str(e),
                    exc_info=True,
                )
                # Continue on error, try again next minute
                await asyncio.sleep(60)

    async def _flush_buffers(self) -> None:
        """
        Flush buffered funding and OI data to database.

        Uses minute-precision timestamps (start of the current minute).
        """
        if not self.funding_buffer and not self.oi_buffer:
            return

        # Get current minute (truncated timestamp)
        flush_time = truncate_to_minute(utc_now())

        funding_count = len(self.funding_buffer)
        oi_count = len(self.oi_buffer)

        try:
            pool = await get_asyncpg_pool()

            # Flush funding rates
            if self.funding_buffer:
                for coin, funding_data in self.funding_buffer.items():
                    await pool.execute(
                        """
                        INSERT INTO funding_rates (
                            trading_pair_id, time, funding_rate, premium,
                            mark_price, index_price, oracle_price, mid_price, next_funding_time
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        ON CONFLICT (trading_pair_id, time)
                        DO UPDATE SET
                            funding_rate = EXCLUDED.funding_rate,
                            premium = EXCLUDED.premium,
                            mark_price = EXCLUDED.mark_price,
                            index_price = EXCLUDED.index_price,
                            oracle_price = EXCLUDED.oracle_price,
                            mid_price = EXCLUDED.mid_price,
                            next_funding_time = EXCLUDED.next_funding_time
                        """,
                        funding_data["trading_pair_id"],
                        flush_time,  # Use truncated minute timestamp
                        funding_data["funding_rate"],
                        funding_data["premium"],
                        funding_data["mark_price"],
                        funding_data["index_price"],
                        funding_data["oracle_price"],
                        funding_data["mid_price"],
                        funding_data["next_funding_time"],
                    )

            # Flush open interest
            if self.oi_buffer:
                for coin, oi_data in self.oi_buffer.items():
                    await pool.execute(
                        """
                        INSERT INTO open_interest (
                            trading_pair_id, time, open_interest, notional_value,
                            day_base_volume, day_notional_volume
                        )
                        VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (trading_pair_id, time)
                        DO UPDATE SET
                            open_interest = EXCLUDED.open_interest,
                            notional_value = EXCLUDED.notional_value,
                            day_base_volume = EXCLUDED.day_base_volume,
                            day_notional_volume = EXCLUDED.day_notional_volume
                        """,
                        oi_data["trading_pair_id"],
                        flush_time,  # Use truncated minute timestamp
                        oi_data["open_interest"],
                        oi_data["notional_value"],
                        oi_data["day_base_volume"],
                        oi_data["day_notional_volume"],
                    )

            self.logger.info(
                "Flushed buffers to database",
                flush_time=flush_time.isoformat(),
                funding_count=funding_count,
                oi_count=oi_count,
            )

            # Clear buffers after successful flush
            self.funding_buffer.clear()
            self.oi_buffer.clear()

        except Exception as e:
            self.logger.error(
                "Failed to flush buffers",
                error=str(e),
                funding_count=funding_count,
                oi_count=oi_count,
                exc_info=True,
            )
            # Don't clear buffers on error - will retry next minute
