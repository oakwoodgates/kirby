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
from src.utils.helpers import timestamp_to_datetime, utc_now


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
        self.subscriptions: dict[str, int] = {}  # coin -> starlisting_id mapping

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

    async def _subscribe_to_asset_contexts(self) -> None:
        """Subscribe to activeAssetCtx updates for all unique coins."""
        if not self.ws:
            raise RuntimeError("WebSocket not connected")

        # Get unique coins from starlistings
        unique_coins = {}
        for starlisting in self.starlistings:
            coin = starlisting.coin.symbol
            if coin not in unique_coins:
                unique_coins[coin] = starlisting.id

        for coin, starlisting_id in unique_coins.items():
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
            self.subscriptions[coin] = starlisting_id

            self.logger.info(
                "Subscribed to asset context",
                coin=coin,
                starlisting_id=starlisting_id,
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

        # Extract context data
        ctx_data = data.get("data")
        if not ctx_data:
            self.logger.warning("Asset context message missing data field", data=data)
            return

        # Get coin from context
        coin = ctx_data.get("coin")
        if not coin:
            self.logger.warning("Asset context data missing coin", ctx_data=ctx_data)
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

            # Store data for each matching starlisting
            for starlisting in matching_starlistings:
                # Store funding rate
                if funding_data:
                    await self._store_funding_rate(funding_data, starlisting.id)

                # Store open interest
                if oi_data:
                    await self._store_open_interest(oi_data, starlisting.id)

            self.logger.debug(
                "Processed asset context",
                coin=coin,
                num_starlistings=len(matching_starlistings),
                funding_rate=funding_data.get("funding_rate") if funding_data else None,
                open_interest=oi_data.get("open_interest") if oi_data else None,
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

    async def _store_funding_rate(
        self, funding_data: dict[str, Any], starlisting_id: int
    ) -> None:
        """Store funding rate data to database."""
        try:
            pool = await get_asyncpg_pool()

            # Add starlisting_id
            funding_data["starlisting_id"] = starlisting_id

            # Upsert funding rate
            await pool.execute(
                """
                INSERT INTO funding_rates (
                    starlisting_id, time, funding_rate, premium,
                    mark_price, index_price, oracle_price, mid_price, next_funding_time
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (starlisting_id, time)
                DO UPDATE SET
                    funding_rate = EXCLUDED.funding_rate,
                    premium = EXCLUDED.premium,
                    mark_price = EXCLUDED.mark_price,
                    index_price = EXCLUDED.index_price,
                    oracle_price = EXCLUDED.oracle_price,
                    mid_price = EXCLUDED.mid_price,
                    next_funding_time = EXCLUDED.next_funding_time
                """,
                funding_data["starlisting_id"],
                funding_data["time"],
                funding_data["funding_rate"],
                funding_data["premium"],
                funding_data["mark_price"],
                funding_data["index_price"],
                funding_data["oracle_price"],
                funding_data["mid_price"],
                funding_data["next_funding_time"],
            )

            self.logger.debug(
                "Stored funding rate",
                starlisting_id=starlisting_id,
                funding_rate=funding_data["funding_rate"],
            )

        except Exception as e:
            self.logger.error(
                "Failed to store funding rate",
                starlisting_id=starlisting_id,
                error=str(e),
                exc_info=True,
            )

    async def _store_open_interest(
        self, oi_data: dict[str, Any], starlisting_id: int
    ) -> None:
        """Store open interest data to database."""
        try:
            pool = await get_asyncpg_pool()

            # Add starlisting_id
            oi_data["starlisting_id"] = starlisting_id

            # Upsert open interest
            await pool.execute(
                """
                INSERT INTO open_interest (
                    starlisting_id, time, open_interest, notional_value,
                    day_base_volume, day_notional_volume
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (starlisting_id, time)
                DO UPDATE SET
                    open_interest = EXCLUDED.open_interest,
                    notional_value = EXCLUDED.notional_value,
                    day_base_volume = EXCLUDED.day_base_volume,
                    day_notional_volume = EXCLUDED.day_notional_volume
                """,
                oi_data["starlisting_id"],
                oi_data["time"],
                oi_data["open_interest"],
                oi_data["notional_value"],
                oi_data["day_base_volume"],
                oi_data["day_notional_volume"],
            )

            self.logger.debug(
                "Stored open interest",
                starlisting_id=starlisting_id,
                open_interest=oi_data["open_interest"],
            )

        except Exception as e:
            self.logger.error(
                "Failed to store open interest",
                starlisting_id=starlisting_id,
                error=str(e),
                exc_info=True,
            )
