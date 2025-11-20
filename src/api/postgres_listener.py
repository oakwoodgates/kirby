"""PostgreSQL LISTEN/NOTIFY listener for real-time updates.

This module listens for PostgreSQL NOTIFY events triggered when new candles,
funding rates, or open interest records are inserted or updated. When a
notification is received, it queries the database for the full data and
broadcasts it to all subscribed WebSocket clients.

This approach provides near real-time updates (typically < 100ms latency) without
requiring a separate message broker like Redis.
"""

import asyncio
import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict

import asyncpg
from structlog import get_logger

from src.api.websocket_manager import ConnectionManager
from src.config.settings import settings

logger = get_logger(__name__)


class PostgresNotificationListener:
    """Listens for PostgreSQL NOTIFY events and broadcasts to WebSocket clients.

    This class maintains a dedicated asyncpg connection for LISTEN/NOTIFY operations,
    separate from the main connection pool to avoid blocking other queries.

    Handles three types of notifications:
    - candle_updates: New OHLCV candle data
    - funding_updates: New funding rate data
    - oi_updates: New open interest data
    """

    def __init__(self, connection_manager: ConnectionManager):
        """Initialize the notification listener.

        Args:
            connection_manager: WebSocket connection manager to broadcast messages to
        """
        self.connection_manager = connection_manager
        self.connection: asyncpg.Connection | None = None
        self.listener_task: asyncio.Task | None = None
        self.is_running = False

        logger.info("postgres_listener_initialized")

    async def start(self) -> None:
        """Start the notification listener.

        Creates a dedicated asyncpg connection and starts listening for notifications
        on three channels: candle_updates, funding_updates, and oi_updates.
        """
        if self.is_running:
            logger.warning("postgres_listener_already_running")
            return

        try:
            # Create dedicated connection for LISTEN (not from pool)
            self.connection = await asyncpg.connect(dsn=settings.asyncpg_url_str)

            # Register notification callbacks for all channels
            await self.connection.add_listener("candle_updates", self._notification_callback)
            await self.connection.add_listener("funding_updates", self._notification_callback)
            await self.connection.add_listener("oi_updates", self._notification_callback)

            # Start listener task
            self.is_running = True
            self.listener_task = asyncio.create_task(self._listen_loop())

            logger.info("postgres_listener_started", channels=["candle_updates", "funding_updates", "oi_updates"])

        except Exception as e:
            logger.error("postgres_listener_start_failed", error=str(e))
            raise

    async def stop(self) -> None:
        """Stop the notification listener and clean up resources."""
        if not self.is_running:
            return

        self.is_running = False

        # Cancel listener task
        if self.listener_task:
            self.listener_task.cancel()
            try:
                await self.listener_task
            except asyncio.CancelledError:
                pass
            self.listener_task = None

        # Close connection
        if self.connection:
            await self.connection.remove_listener("candle_updates", self._notification_callback)
            await self.connection.remove_listener("funding_updates", self._notification_callback)
            await self.connection.remove_listener("oi_updates", self._notification_callback)
            await self.connection.close()
            self.connection = None

        logger.info("postgres_listener_stopped")

    def _notification_callback(
        self, connection: asyncpg.Connection, pid: int, channel: str, payload: str
    ) -> None:
        """Callback invoked when a NOTIFY event is received.

        This is called synchronously by asyncpg, so we schedule the async
        handling as a task.

        Args:
            connection: The asyncpg connection
            pid: PostgreSQL backend process ID
            channel: Channel name ('candle_updates', 'funding_updates', or 'oi_updates')
            payload: JSON payload with starlisting_id/trading_pair_id and time
        """
        try:
            # Parse notification payload
            data = json.loads(payload)
            time_str = data.get("time")

            if not time_str:
                logger.warning(
                    "notification_missing_time",
                    channel=channel,
                    payload=payload,
                )
                return

            # Route to appropriate handler based on channel
            if channel == "candle_updates":
                # Candles use starlisting_id (per interval)
                starlisting_id = data.get("starlisting_id")
                if not starlisting_id:
                    logger.warning(
                        "notification_missing_starlisting_id",
                        channel=channel,
                        payload=payload,
                    )
                    return
                asyncio.create_task(
                    self._handle_candle_notification(starlisting_id, time_str)
                )
            elif channel == "funding_updates":
                # Funding uses trading_pair_id (shared across intervals)
                trading_pair_id = data.get("trading_pair_id")
                if not trading_pair_id:
                    logger.warning(
                        "notification_missing_trading_pair_id",
                        channel=channel,
                        payload=payload,
                    )
                    return
                asyncio.create_task(
                    self._handle_funding_notification(trading_pair_id, time_str)
                )
            elif channel == "oi_updates":
                # OI uses trading_pair_id (shared across intervals)
                trading_pair_id = data.get("trading_pair_id")
                if not trading_pair_id:
                    logger.warning(
                        "notification_missing_trading_pair_id",
                        channel=channel,
                        payload=payload,
                    )
                    return
                asyncio.create_task(
                    self._handle_oi_notification(trading_pair_id, time_str)
                )
            else:
                logger.warning("unknown_notification_channel", channel=channel)

        except json.JSONDecodeError as e:
            logger.error(
                "notification_json_parse_failed",
                channel=channel,
                payload=payload,
                error=str(e),
            )
        except Exception as e:
            logger.error(
                "notification_callback_error",
                channel=channel,
                error=str(e),
            )

    async def _handle_candle_notification(self, starlisting_id: int, time_str: str) -> None:
        """Handle a candle notification by querying the database and broadcasting.

        Args:
            starlisting_id: The starlisting ID of the new candle
            time_str: ISO timestamp of the candle
        """
        try:
            # Check if anyone is subscribed to this starlisting
            subscriber_count = self.connection_manager.get_subscriber_count(starlisting_id)
            if subscriber_count == 0:
                # No subscribers, skip query
                return

            # Query database for full candle data + starlisting metadata
            candle_data = await self._query_candle_data(starlisting_id, time_str)

            if not candle_data:
                logger.warning(
                    "notification_candle_not_found",
                    starlisting_id=starlisting_id,
                    time=time_str,
                )
                return

            # Broadcast to all subscribers
            sent_count = await self.connection_manager.broadcast_to_subscribers(
                starlisting_id, candle_data
            )

            logger.debug(
                "candle_notification_broadcasted",
                starlisting_id=starlisting_id,
                sent_count=sent_count,
            )

        except Exception as e:
            logger.error(
                "candle_notification_handler_error",
                starlisting_id=starlisting_id,
                time=time_str,
                error=str(e),
            )

    async def _handle_funding_notification(self, trading_pair_id: int, time_str: str) -> None:
        """Handle a funding rate notification by querying the database and broadcasting.

        Since funding rates are per trading_pair_id (not per starlisting), we need to:
        1. Find all starlistings with this trading_pair_id
        2. Broadcast to subscribers of each starlisting

        Args:
            trading_pair_id: The trading pair ID of the new funding rate
            time_str: ISO timestamp of the funding rate
        """
        try:
            # Get all starlisting IDs for this trading pair
            starlisting_ids = await self._get_starlistings_for_trading_pair(trading_pair_id)

            if not starlisting_ids:
                logger.warning(
                    "notification_no_starlistings_for_trading_pair",
                    trading_pair_id=trading_pair_id,
                )
                return

            # Broadcast to each starlisting's subscribers
            total_sent = 0
            for starlisting_id in starlisting_ids:
                # Check if anyone is subscribed to this starlisting
                subscriber_count = self.connection_manager.get_subscriber_count(starlisting_id)
                if subscriber_count == 0:
                    # No subscribers, skip query
                    continue

                # Query database for full funding rate data + starlisting metadata
                funding_data = await self._query_funding_data(trading_pair_id, starlisting_id, time_str)

                if not funding_data:
                    logger.warning(
                        "notification_funding_not_found",
                        trading_pair_id=trading_pair_id,
                        starlisting_id=starlisting_id,
                        time=time_str,
                    )
                    continue

                # Broadcast to all subscribers of this starlisting
                sent_count = await self.connection_manager.broadcast_to_subscribers(
                    starlisting_id, funding_data
                )
                total_sent += sent_count

            logger.debug(
                "funding_notification_broadcasted",
                trading_pair_id=trading_pair_id,
                starlisting_count=len(starlisting_ids),
                total_sent=total_sent,
            )

        except Exception as e:
            logger.error(
                "funding_notification_handler_error",
                trading_pair_id=trading_pair_id,
                time=time_str,
                error=str(e),
            )

    async def _handle_oi_notification(self, trading_pair_id: int, time_str: str) -> None:
        """Handle an open interest notification by querying the database and broadcasting.

        Since open interest is per trading_pair_id (not per starlisting), we need to:
        1. Find all starlistings with this trading_pair_id
        2. Broadcast to subscribers of each starlisting

        Args:
            trading_pair_id: The trading pair ID of the new OI record
            time_str: ISO timestamp of the OI record
        """
        try:
            # Get all starlisting IDs for this trading pair
            starlisting_ids = await self._get_starlistings_for_trading_pair(trading_pair_id)

            if not starlisting_ids:
                logger.warning(
                    "notification_no_starlistings_for_trading_pair",
                    trading_pair_id=trading_pair_id,
                )
                return

            # Broadcast to each starlisting's subscribers
            total_sent = 0
            for starlisting_id in starlisting_ids:
                # Check if anyone is subscribed to this starlisting
                subscriber_count = self.connection_manager.get_subscriber_count(starlisting_id)
                if subscriber_count == 0:
                    # No subscribers, skip query
                    continue

                # Query database for full OI data + starlisting metadata
                oi_data = await self._query_oi_data(trading_pair_id, starlisting_id, time_str)

                if not oi_data:
                    logger.warning(
                        "notification_oi_not_found",
                        trading_pair_id=trading_pair_id,
                        starlisting_id=starlisting_id,
                        time=time_str,
                    )
                    continue

                # Broadcast to all subscribers of this starlisting
                sent_count = await self.connection_manager.broadcast_to_subscribers(
                    starlisting_id, oi_data
                )
                total_sent += sent_count

            logger.debug(
                "oi_notification_broadcasted",
                trading_pair_id=trading_pair_id,
                starlisting_count=len(starlisting_ids),
                total_sent=total_sent,
            )

        except Exception as e:
            logger.error(
                "oi_notification_handler_error",
                trading_pair_id=trading_pair_id,
                time=time_str,
                error=str(e),
            )

    async def _get_starlistings_for_trading_pair(self, trading_pair_id: int) -> list[int]:
        """Get all starlisting IDs for a given trading pair.

        Args:
            trading_pair_id: The trading pair ID

        Returns:
            List of starlisting IDs
        """
        if not self.connection:
            return []

        query = """
            SELECT id
            FROM starlistings
            WHERE trading_pair_id = $1
              AND active = true
        """

        try:
            rows = await self.connection.fetch(query, trading_pair_id)
            return [row["id"] for row in rows]

        except Exception as e:
            logger.error(
                "query_starlistings_for_trading_pair_failed",
                trading_pair_id=trading_pair_id,
                error=str(e),
            )
            return []

    async def _query_candle_data(
        self, starlisting_id: int, time_str: str
    ) -> Dict[str, Any] | None:
        """Query the database for candle data and metadata.

        This performs a single optimized query joining candles with starlistings
        and all related tables to get complete metadata.

        Args:
            starlisting_id: The starlisting ID
            time_str: ISO timestamp of the candle

        Returns:
            Formatted message dict ready to broadcast, or None if not found
        """
        if not self.connection:
            return None

        query = """
            SELECT
                c.time,
                c.open,
                c.high,
                c.low,
                c.close,
                c.volume,
                c.num_trades,
                s.id as starlisting_id,
                e.name as exchange,
                co.symbol as coin,
                qc.symbol as quote,
                mt.name as market_type,
                i.name as interval
            FROM candles c
            JOIN starlistings s ON c.starlisting_id = s.id
            JOIN exchanges e ON s.exchange_id = e.id
            JOIN coins co ON s.coin_id = co.id
            JOIN quote_currencies qc ON s.quote_currency_id = qc.id
            JOIN market_types mt ON s.market_type_id = mt.id
            JOIN intervals i ON s.interval_id = i.id
            WHERE c.starlisting_id = $1
              AND date_trunc('second', c.time) = date_trunc('second', $2::timestamptz)
            LIMIT 1
        """

        try:
            # Parse the ISO timestamp string to datetime object for asyncpg
            # The trigger sends format like "2025-11-17T17:33:14+00"
            time_dt = datetime.fromisoformat(time_str)

            row = await self.connection.fetchrow(query, starlisting_id, time_dt)

            if not row:
                return None

            # Format trading pair
            trading_pair = f"{row['coin']}/{row['quote']}"

            # Build message matching REST API format
            message = {
                "type": "candle",
                "starlisting_id": row["starlisting_id"],
                "exchange": row["exchange"],
                "coin": row["coin"],
                "quote": row["quote"],
                "trading_pair": trading_pair,
                "market_type": row["market_type"],
                "interval": row["interval"],
                "data": {
                    "time": row["time"].isoformat(),
                    "open": str(row["open"]) if row["open"] is not None else None,
                    "high": str(row["high"]) if row["high"] is not None else None,
                    "low": str(row["low"]) if row["low"] is not None else None,
                    "close": str(row["close"]) if row["close"] is not None else None,
                    "volume": str(row["volume"]) if row["volume"] is not None else None,
                    "num_trades": row["num_trades"],
                },
            }

            return message

        except Exception as e:
            logger.error(
                "query_candle_data_failed",
                starlisting_id=starlisting_id,
                time=time_str,
                error=str(e),
            )
            return None

    async def _query_funding_data(
        self, trading_pair_id: int, starlisting_id: int, time_str: str
    ) -> Dict[str, Any] | None:
        """Query the database for funding rate data and metadata.

        This performs a single optimized query joining funding_rates with starlistings
        and all related tables to get complete metadata.

        Args:
            trading_pair_id: The trading pair ID (used for querying funding_rates)
            starlisting_id: The starlisting ID (used for metadata and response)
            time_str: ISO timestamp of the funding rate

        Returns:
            Formatted message dict ready to broadcast, or None if not found
        """
        if not self.connection:
            return None

        query = """
            SELECT
                f.time,
                f.funding_rate,
                f.premium,
                f.mark_price,
                f.index_price,
                f.oracle_price,
                f.mid_price,
                f.next_funding_time,
                s.id as starlisting_id,
                e.name as exchange,
                co.symbol as coin,
                qc.symbol as quote,
                mt.name as market_type
            FROM funding_rates f
            JOIN starlistings s ON s.id = $2
            JOIN exchanges e ON s.exchange_id = e.id
            JOIN coins co ON s.coin_id = co.id
            JOIN quote_currencies qc ON s.quote_currency_id = qc.id
            JOIN market_types mt ON s.market_type_id = mt.id
            WHERE f.trading_pair_id = $1
              AND date_trunc('second', f.time) = date_trunc('second', $3::timestamptz)
            LIMIT 1
        """

        try:
            time_dt = datetime.fromisoformat(time_str)
            row = await self.connection.fetchrow(query, trading_pair_id, starlisting_id, time_dt)

            if not row:
                return None

            trading_pair = f"{row['coin']}/{row['quote']}"

            message = {
                "type": "funding",
                "starlisting_id": row["starlisting_id"],
                "exchange": row["exchange"],
                "coin": row["coin"],
                "quote": row["quote"],
                "trading_pair": trading_pair,
                "market_type": row["market_type"],
                "data": {
                    "time": row["time"].isoformat(),
                    "funding_rate": str(row["funding_rate"]) if row["funding_rate"] is not None else None,
                    "premium": str(row["premium"]) if row["premium"] is not None else None,
                    "mark_price": str(row["mark_price"]) if row["mark_price"] is not None else None,
                    "index_price": str(row["index_price"]) if row["index_price"] is not None else None,
                    "oracle_price": str(row["oracle_price"]) if row["oracle_price"] is not None else None,
                    "mid_price": str(row["mid_price"]) if row["mid_price"] is not None else None,
                    "next_funding_time": row["next_funding_time"].isoformat() if row["next_funding_time"] else None,
                },
            }

            return message

        except Exception as e:
            logger.error(
                "query_funding_data_failed",
                trading_pair_id=trading_pair_id,
                starlisting_id=starlisting_id,
                time=time_str,
                error=str(e),
            )
            return None

    async def _query_oi_data(
        self, trading_pair_id: int, starlisting_id: int, time_str: str
    ) -> Dict[str, Any] | None:
        """Query the database for open interest data and metadata.

        This performs a single optimized query joining open_interest with starlistings
        and all related tables to get complete metadata.

        Args:
            trading_pair_id: The trading pair ID (used for querying open_interest)
            starlisting_id: The starlisting ID (used for metadata and response)
            time_str: ISO timestamp of the OI record

        Returns:
            Formatted message dict ready to broadcast, or None if not found
        """
        if not self.connection:
            return None

        query = """
            SELECT
                o.time,
                o.open_interest,
                o.notional_value,
                o.day_base_volume,
                o.day_notional_volume,
                s.id as starlisting_id,
                e.name as exchange,
                co.symbol as coin,
                qc.symbol as quote,
                mt.name as market_type
            FROM open_interest o
            JOIN starlistings s ON s.id = $2
            JOIN exchanges e ON s.exchange_id = e.id
            JOIN coins co ON s.coin_id = co.id
            JOIN quote_currencies qc ON s.quote_currency_id = qc.id
            JOIN market_types mt ON s.market_type_id = mt.id
            WHERE o.trading_pair_id = $1
              AND date_trunc('second', o.time) = date_trunc('second', $3::timestamptz)
            LIMIT 1
        """

        try:
            time_dt = datetime.fromisoformat(time_str)
            row = await self.connection.fetchrow(query, trading_pair_id, starlisting_id, time_dt)

            if not row:
                return None

            trading_pair = f"{row['coin']}/{row['quote']}"

            message = {
                "type": "open_interest",
                "starlisting_id": row["starlisting_id"],
                "exchange": row["exchange"],
                "coin": row["coin"],
                "quote": row["quote"],
                "trading_pair": trading_pair,
                "market_type": row["market_type"],
                "data": {
                    "time": row["time"].isoformat(),
                    "open_interest": str(row["open_interest"]) if row["open_interest"] is not None else None,
                    "notional_value": str(row["notional_value"]) if row["notional_value"] is not None else None,
                    "day_base_volume": str(row["day_base_volume"]) if row["day_base_volume"] is not None else None,
                    "day_notional_volume": str(row["day_notional_volume"]) if row["day_notional_volume"] is not None else None,
                },
            }

            return message

        except Exception as e:
            logger.error(
                "query_oi_data_failed",
                trading_pair_id=trading_pair_id,
                starlisting_id=starlisting_id,
                time=time_str,
                error=str(e),
            )
            return None

    async def _listen_loop(self) -> None:
        """Background task that keeps the connection alive.

        This is needed because asyncpg's LISTEN requires an active connection.
        The actual notifications are handled by the callback.
        """
        try:
            while self.is_running:
                # Keep connection alive with periodic ping
                # (notifications are handled by callback, not here)
                await asyncio.sleep(30)

                if self.connection:
                    # Simple query to keep connection alive
                    await self.connection.fetchval("SELECT 1")

        except asyncio.CancelledError:
            # Normal shutdown
            pass
        except Exception as e:
            logger.error("listen_loop_error", error=str(e))

            # Attempt reconnection
            if self.is_running:
                logger.info("attempting_reconnection")
                await asyncio.sleep(5)

                try:
                    # Reconnect
                    await self.stop()
                    await self.start()
                except Exception as reconnect_error:
                    logger.error("reconnection_failed", error=str(reconnect_error))
