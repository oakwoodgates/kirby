"""
High-performance data writer using asyncpg for batch inserts.
All insert queries use UPSERT (ON CONFLICT DO UPDATE) for idempotency.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

import asyncpg

from src.utils import get_logger

logger = get_logger(__name__)


class DataWriter:
    """
    High-performance data writer using asyncpg for batch inserts.
    Provides methods for inserting candles, funding rates, open interest, trades, and market metadata.
    """

    def __init__(self, pool: asyncpg.Pool):
        """
        Initialize the DataWriter with an asyncpg connection pool.

        Args:
            pool: asyncpg connection pool
        """
        self.pool = pool

    async def insert_candles_batch(
        self,
        candles: list[dict[str, Any]],
    ) -> int:
        """
        Batch insert candles with UPSERT logic.

        Args:
            candles: List of candle dictionaries with keys:
                - listing_id: int
                - timestamp: datetime
                - interval: str
                - open: Decimal
                - high: Decimal
                - low: Decimal
                - close: Decimal
                - volume: Decimal
                - trades_count: Optional[int]

        Returns:
            int: Number of rows inserted/updated

        Raises:
            Exception: If insert fails
        """
        if not candles:
            return 0

        query = """
            INSERT INTO candle (
                listing_id, timestamp, interval, open, high, low, close, volume, trades_count, created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
            ON CONFLICT (listing_id, timestamp, interval)
            DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                trades_count = EXCLUDED.trades_count
        """

        # Prepare batch data
        batch_data = [
            (
                c["listing_id"],
                c["timestamp"],
                c["interval"],
                c["open"],
                c["high"],
                c["low"],
                c["close"],
                c["volume"],
                c.get("trades_count"),
            )
            for c in candles
        ]

        async with self.pool.acquire() as conn:
            try:
                await conn.executemany(query, batch_data)
                logger.debug(
                    f"Inserted {len(candles)} candles",
                    extra={"count": len(candles), "table": "candle"},
                )
                return len(candles)
            except Exception as e:
                logger.error(
                    f"Failed to insert candles: {e}",
                    extra={"error": str(e), "count": len(candles)},
                )
                raise

    async def insert_funding_rates_batch(
        self,
        funding_rates: list[dict[str, Any]],
    ) -> int:
        """
        Batch insert funding rates with UPSERT logic.

        Args:
            funding_rates: List of funding rate dictionaries with keys:
                - listing_id: int
                - timestamp: datetime
                - rate: Decimal
                - predicted_rate: Optional[Decimal]
                - mark_price: Optional[Decimal]
                - index_price: Optional[Decimal]
                - premium: Optional[Decimal]
                - next_funding_time: Optional[datetime]

        Returns:
            int: Number of rows inserted/updated
        """
        if not funding_rates:
            return 0

        query = """
            INSERT INTO funding_rate (
                listing_id, timestamp, rate, predicted_rate, mark_price, index_price,
                premium, next_funding_time, created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
            ON CONFLICT (listing_id, timestamp)
            DO UPDATE SET
                rate = EXCLUDED.rate,
                predicted_rate = EXCLUDED.predicted_rate,
                mark_price = EXCLUDED.mark_price,
                index_price = EXCLUDED.index_price,
                premium = EXCLUDED.premium,
                next_funding_time = EXCLUDED.next_funding_time
        """

        batch_data = [
            (
                fr["listing_id"],
                fr["timestamp"],
                fr["rate"],
                fr.get("predicted_rate"),
                fr.get("mark_price"),
                fr.get("index_price"),
                fr.get("premium"),
                fr.get("next_funding_time"),
            )
            for fr in funding_rates
        ]

        async with self.pool.acquire() as conn:
            try:
                await conn.executemany(query, batch_data)
                logger.debug(
                    f"Inserted {len(funding_rates)} funding rates",
                    extra={"count": len(funding_rates), "table": "funding_rate"},
                )
                return len(funding_rates)
            except Exception as e:
                logger.error(
                    f"Failed to insert funding rates: {e}",
                    extra={"error": str(e), "count": len(funding_rates)},
                )
                raise

    async def insert_open_interest_batch(
        self,
        open_interest_data: list[dict[str, Any]],
    ) -> int:
        """
        Batch insert open interest with UPSERT logic.

        Args:
            open_interest_data: List of OI dictionaries with keys:
                - listing_id: int
                - timestamp: datetime
                - open_interest: Decimal
                - open_interest_value: Optional[Decimal]

        Returns:
            int: Number of rows inserted/updated
        """
        if not open_interest_data:
            return 0

        query = """
            INSERT INTO open_interest (
                listing_id, timestamp, open_interest, open_interest_value, created_at
            )
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (listing_id, timestamp)
            DO UPDATE SET
                open_interest = EXCLUDED.open_interest,
                open_interest_value = EXCLUDED.open_interest_value
        """

        batch_data = [
            (
                oi["listing_id"],
                oi["timestamp"],
                oi["open_interest"],
                oi.get("open_interest_value"),
            )
            for oi in open_interest_data
        ]

        async with self.pool.acquire() as conn:
            try:
                await conn.executemany(query, batch_data)
                logger.debug(
                    f"Inserted {len(open_interest_data)} open interest records",
                    extra={"count": len(open_interest_data), "table": "open_interest"},
                )
                return len(open_interest_data)
            except Exception as e:
                logger.error(
                    f"Failed to insert open interest: {e}",
                    extra={"error": str(e), "count": len(open_interest_data)},
                )
                raise

    async def insert_trades_batch(
        self,
        trades: list[dict[str, Any]],
    ) -> int:
        """
        Batch insert trades with UPSERT logic.

        Args:
            trades: List of trade dictionaries with keys:
                - listing_id: int
                - timestamp: datetime
                - trade_id: str
                - price: Decimal
                - amount: Decimal
                - side: str

        Returns:
            int: Number of rows inserted/updated
        """
        if not trades:
            return 0

        query = """
            INSERT INTO trade (
                listing_id, timestamp, trade_id, price, amount, side, created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            ON CONFLICT (listing_id, timestamp, trade_id)
            DO UPDATE SET
                price = EXCLUDED.price,
                amount = EXCLUDED.amount,
                side = EXCLUDED.side
        """

        batch_data = [
            (
                t["listing_id"],
                t["timestamp"],
                t["trade_id"],
                t["price"],
                t["amount"],
                t["side"],
            )
            for t in trades
        ]

        async with self.pool.acquire() as conn:
            try:
                await conn.executemany(query, batch_data)
                logger.debug(
                    f"Inserted {len(trades)} trades",
                    extra={"count": len(trades), "table": "trade"},
                )
                return len(trades)
            except Exception as e:
                logger.error(
                    f"Failed to insert trades: {e}",
                    extra={"error": str(e), "count": len(trades)},
                )
                raise

    async def insert_market_metadata_batch(
        self,
        metadata: list[dict[str, Any]],
    ) -> int:
        """
        Batch insert market metadata with UPSERT logic.

        Args:
            metadata: List of market metadata dictionaries with keys:
                - listing_id: int
                - timestamp: datetime
                - bid: Optional[Decimal]
                - ask: Optional[Decimal]
                - last_price: Optional[Decimal]
                - volume_24h: Optional[Decimal]
                - volume_quote_24h: Optional[Decimal]
                - price_change_24h: Optional[Decimal]
                - percentage_change_24h: Optional[Decimal]
                - high_24h: Optional[Decimal]
                - low_24h: Optional[Decimal]
                - data: Optional[dict]

        Returns:
            int: Number of rows inserted/updated
        """
        if not metadata:
            return 0

        query = """
            INSERT INTO market_metadata (
                listing_id, timestamp, bid, ask, last_price, volume_24h, volume_quote_24h,
                price_change_24h, percentage_change_24h, high_24h, low_24h, data, created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW())
            ON CONFLICT (listing_id, timestamp)
            DO UPDATE SET
                bid = EXCLUDED.bid,
                ask = EXCLUDED.ask,
                last_price = EXCLUDED.last_price,
                volume_24h = EXCLUDED.volume_24h,
                volume_quote_24h = EXCLUDED.volume_quote_24h,
                price_change_24h = EXCLUDED.price_change_24h,
                percentage_change_24h = EXCLUDED.percentage_change_24h,
                high_24h = EXCLUDED.high_24h,
                low_24h = EXCLUDED.low_24h,
                data = EXCLUDED.data
        """

        batch_data = [
            (
                m["listing_id"],
                m["timestamp"],
                m.get("bid"),
                m.get("ask"),
                m.get("last_price"),
                m.get("volume_24h"),
                m.get("volume_quote_24h"),
                m.get("price_change_24h"),
                m.get("percentage_change_24h"),
                m.get("high_24h"),
                m.get("low_24h"),
                m.get("data"),
            )
            for m in metadata
        ]

        async with self.pool.acquire() as conn:
            try:
                await conn.executemany(query, batch_data)
                logger.debug(
                    f"Inserted {len(metadata)} market metadata records",
                    extra={"count": len(metadata), "table": "market_metadata"},
                )
                return len(metadata)
            except Exception as e:
                logger.error(
                    f"Failed to insert market metadata: {e}",
                    extra={"error": str(e), "count": len(metadata)},
                )
                raise

    async def health_check(self) -> dict[str, Any]:
        """
        Check database connection health.

        Returns:
            dict: Health check result with status and pool stats
        """
        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")

            return {
                "status": "healthy",
                "pool_size": self.pool.get_size(),
                "pool_free": self.pool.get_size() - self.pool.get_idle_size(),
                "pool_idle": self.pool.get_idle_size(),
            }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
            }
