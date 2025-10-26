"""
Hyperliquid exchange collector.

Collects real-time candle data via WebSocket.
"""
import asyncio
import json
from typing import Any

import websockets
from websockets.client import WebSocketClientProtocol

from src.collectors.base import BaseCollector
from src.utils.helpers import normalize_candle_data, validate_candle


class HyperliquidCollector(BaseCollector):
    """
    Hyperliquid WebSocket collector for real-time candle data.

    Subscribes to candle updates for configured starlistings.
    """

    WEBSOCKET_URL = "wss://api.hyperliquid.xyz/ws"

    def __init__(self):
        """Initialize Hyperliquid collector."""
        super().__init__("hyperliquid")
        self.ws: WebSocketClientProtocol | None = None
        self.subscriptions: dict[str, int] = {}  # subscription_key -> starlisting_id

    async def connect(self) -> None:
        """Connect to Hyperliquid WebSocket API."""
        self.logger.info("Connecting to Hyperliquid WebSocket", url=self.WEBSOCKET_URL)

        try:
            self.ws = await websockets.connect(
                self.WEBSOCKET_URL,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10,
            )

            self.logger.info("Connected to Hyperliquid WebSocket")

            # Subscribe to candles for all starlistings
            await self._subscribe_to_candles()

        except Exception as e:
            self.logger.error(
                "Failed to connect to Hyperliquid WebSocket",
                error=str(e),
                exc_info=True,
            )
            raise

    async def disconnect(self) -> None:
        """Disconnect from Hyperliquid WebSocket."""
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

        await super().disconnect()

    async def _subscribe_to_candles(self) -> None:
        """Subscribe to candle updates for all starlistings."""
        if not self.ws:
            raise RuntimeError("WebSocket not connected")

        for starlisting in self.starlistings:
            coin = starlisting.coin.symbol
            interval = starlisting.interval.name

            # Create subscription message
            subscription = {
                "method": "subscribe",
                "subscription": {
                    "type": "candle",
                    "coin": coin,
                    "interval": interval,
                },
            }

            # Send subscription
            await self.ws.send(json.dumps(subscription))

            # Track subscription
            sub_key = f"{coin}_{interval}"
            self.subscriptions[sub_key] = starlisting.id

            self.logger.info(
                "Subscribed to candles",
                coin=coin,
                interval=interval,
                starlisting_id=starlisting.id,
            )

        self.logger.info(
            "Subscribed to all candles",
            subscription_count=len(self.subscriptions),
        )

    async def collect(self) -> None:
        """
        Collect candle data from WebSocket.

        Runs continuously until stopped or error.
        """
        if not self.ws:
            raise RuntimeError("WebSocket not connected")

        self.logger.info("Starting candle collection")

        try:
            async for message in self.ws:
                # Check if stop requested
                if self._stop_event.is_set():
                    self.logger.info("Stop event detected, exiting collection loop")
                    break

                try:
                    # Parse message
                    data = json.loads(message)

                    # Process candle update
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
        # Check if this is a candle update
        if data.get("channel") != "candle":
            # Not a candle update, might be subscription confirmation
            self.logger.debug("Received non-candle message", data=data)
            return

        # Extract candle data
        candle_data = data.get("data")
        if not candle_data:
            self.logger.warning("Candle message missing data field", data=data)
            return

        # Get coin and interval from candle data
        coin = candle_data.get("s")  # symbol
        interval = candle_data.get("i")  # interval

        if not coin or not interval:
            self.logger.warning(
                "Candle data missing coin or interval",
                candle_data=candle_data,
            )
            return

        # Find corresponding starlisting
        sub_key = f"{coin}_{interval}"
        starlisting_id = self.subscriptions.get(sub_key)

        if not starlisting_id:
            self.logger.warning(
                "Received candle for unknown subscription",
                coin=coin,
                interval=interval,
            )
            return

        try:
            # Normalize candle data
            normalized_candle = normalize_candle_data(candle_data, source="hyperliquid")

            # Validate candle
            if not validate_candle(normalized_candle):
                self.logger.warning(
                    "Invalid candle data",
                    coin=coin,
                    interval=interval,
                    candle=normalized_candle,
                )
                return

            # Store candle
            await self.store_candles([normalized_candle], starlisting_id)

            self.logger.debug(
                "Processed candle",
                coin=coin,
                interval=interval,
                starlisting_id=starlisting_id,
                time=normalized_candle["time"].isoformat(),
                close=normalized_candle["close"],
            )

        except Exception as e:
            self.logger.error(
                "Failed to process candle",
                coin=coin,
                interval=interval,
                error=str(e),
                exc_info=True,
            )
