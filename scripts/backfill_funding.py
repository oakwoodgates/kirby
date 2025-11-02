"""
Backfill historical funding rate data using Hyperliquid SDK.

Usage:
    python -m scripts.backfill_funding --days=365
    python -m scripts.backfill_funding --coin=BTC --days=90
    python -m scripts.backfill_funding --all
"""
import argparse
import asyncio
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import structlog
from hyperliquid.info import Info

from src.config.loader import ConfigLoader
from src.db.connection import close_db, get_asyncpg_pool, get_session, init_db
from src.utils.helpers import truncate_to_minute, utc_now
from src.utils.logging import setup_logging


class FundingBackfillService:
    """Service for backfilling historical funding rate data."""

    def __init__(self):
        """Initialize backfill service."""
        self.logger = structlog.get_logger("kirby.scripts.backfill_funding")
        self.info = Info()

    async def backfill_coin(
        self,
        coin: str,
        starlisting_id: int,
        days: int = 365,
    ) -> int:
        """
        Backfill historical funding rates for a coin.

        Args:
            coin: Coin symbol (e.g., "BTC")
            starlisting_id: Starlisting ID to associate with funding data
            days: Number of days to backfill

        Returns:
            Number of funding rate records backfilled
        """
        self.logger.info(
            "Starting funding rate backfill",
            coin=coin,
            starlisting_id=starlisting_id,
            days=days,
        )

        try:
            # Calculate time range
            end_time = utc_now()
            start_time = end_time - timedelta(days=days)

            # Convert to milliseconds for Hyperliquid API
            start_ms = int(start_time.timestamp() * 1000)

            self.logger.info(
                "Fetching funding history",
                coin=coin,
                start_time=start_time.isoformat(),
                end_time=end_time.isoformat(),
            )

            # Fetch funding history from Hyperliquid
            # Note: funding_history takes positional args, not keyword args
            funding_history = self.info.funding_history(
                coin,  # Positional: coin symbol
                startTime=start_ms,
            )

            if not funding_history:
                self.logger.warning(
                    "No funding history returned",
                    coin=coin,
                )
                return 0

            self.logger.info(
                "Retrieved funding history",
                coin=coin,
                records=len(funding_history),
            )

            # Process and store funding rates
            funding_records = []
            for record in funding_history:
                try:
                    # Parse the record
                    funding_record = self._parse_funding_record(
                        record, starlisting_id
                    )
                    if funding_record:
                        funding_records.append(funding_record)
                except Exception as e:
                    self.logger.warning(
                        "Failed to parse funding record",
                        error=str(e),
                        record=record,
                    )

            # Batch insert funding rates
            if funding_records:
                stored = await self._store_funding_rates(funding_records)

                self.logger.info(
                    "Backfill complete",
                    coin=coin,
                    total_records=stored,
                    start_time=start_time.isoformat(),
                    end_time=end_time.isoformat(),
                )

                return stored
            else:
                self.logger.warning("No valid funding records to store", coin=coin)
                return 0

        except Exception as e:
            self.logger.error(
                "Backfill failed",
                coin=coin,
                error=str(e),
                exc_info=True,
            )
            return 0

    def _parse_funding_record(
        self, record: dict[str, Any], starlisting_id: int
    ) -> dict[str, Any] | None:
        """
        Parse a funding history record from Hyperliquid.

        Args:
            record: Raw funding record from API
            starlisting_id: Starlisting ID

        Returns:
            Parsed funding record or None if invalid
        """
        try:
            # Extract timestamp (milliseconds)
            time_ms = int(record.get("time", 0))
            if not time_ms:
                return None

            # Convert to datetime and truncate to minute precision
            # (aligns with candle data timestamps and 1-minute storage interval)
            time = datetime.fromtimestamp(time_ms / 1000).astimezone()
            time = truncate_to_minute(time)

            # Extract funding rate and premium
            funding_rate_str = record.get("fundingRate")
            premium_str = record.get("premium")

            if funding_rate_str is None:
                return None

            return {
                "time": time,
                "starlisting_id": starlisting_id,
                "funding_rate": Decimal(funding_rate_str),
                "premium": Decimal(premium_str) if premium_str else None,
                # Note: Historical data doesn't include all fields
                # (mark_price, index_price, etc. are only in real-time data)
                "mark_price": None,
                "index_price": None,
                "oracle_price": None,
                "mid_price": None,
                "next_funding_time": None,
            }

        except Exception as e:
            self.logger.warning(
                "Failed to parse funding record",
                error=str(e),
                record=record,
            )
            return None

    async def _store_funding_rates(
        self, funding_records: list[dict[str, Any]]
    ) -> int:
        """
        Store funding rate records to database.

        Args:
            funding_records: List of funding rate records

        Returns:
            Number of records stored
        """
        pool = await get_asyncpg_pool()

        # Prepare data for bulk insert
        records_to_insert = [
            (
                record["starlisting_id"],
                record["time"],
                record["funding_rate"],
                record["premium"],
                record["mark_price"],
                record["index_price"],
                record["oracle_price"],
                record["mid_price"],
                record["next_funding_time"],
            )
            for record in funding_records
        ]

        # Bulk upsert using asyncpg
        query = """
            INSERT INTO funding_rates (
                starlisting_id, time, funding_rate, premium,
                mark_price, index_price, oracle_price, mid_price, next_funding_time
            )
            SELECT * FROM UNNEST($1::integer[], $2::timestamptz[], $3::numeric[],
                                 $4::numeric[], $5::numeric[], $6::numeric[],
                                 $7::numeric[], $8::numeric[], $9::timestamptz[])
            ON CONFLICT (time, starlisting_id)
            DO UPDATE SET
                funding_rate = EXCLUDED.funding_rate,
                premium = EXCLUDED.premium,
                mark_price = EXCLUDED.mark_price,
                index_price = EXCLUDED.index_price,
                oracle_price = EXCLUDED.oracle_price,
                mid_price = EXCLUDED.mid_price,
                next_funding_time = EXCLUDED.next_funding_time
        """

        # Transpose records for UNNEST
        starlisting_ids = [r[0] for r in records_to_insert]
        times = [r[1] for r in records_to_insert]
        funding_rates = [r[2] for r in records_to_insert]
        premiums = [r[3] for r in records_to_insert]
        mark_prices = [r[4] for r in records_to_insert]
        index_prices = [r[5] for r in records_to_insert]
        oracle_prices = [r[6] for r in records_to_insert]
        mid_prices = [r[7] for r in records_to_insert]
        next_funding_times = [r[8] for r in records_to_insert]

        await pool.execute(
            query,
            starlisting_ids,
            times,
            funding_rates,
            premiums,
            mark_prices,
            index_prices,
            oracle_prices,
            mid_prices,
            next_funding_times,
        )

        self.logger.info(
            "Stored funding rates",
            count=len(records_to_insert),
        )

        return len(records_to_insert)

    async def backfill_all(self, days: int = 365) -> None:
        """
        Backfill all active coins with funding data.

        Args:
            days: Number of days to backfill
        """
        self.logger.info("Starting funding backfill for all coins", days=days)

        # Load starlistings
        config_loader = ConfigLoader()
        session = await get_session()
        try:
            starlistings = await config_loader.get_active_starlistings(session)
        finally:
            await session.close()

        # Get unique coins (funding is per coin, not per interval)
        unique_coins = {}
        for starlisting in starlistings:
            coin = starlisting["coin"]
            if coin not in unique_coins:
                # Use the first (canonical) starlisting for this coin
                unique_coins[coin] = starlisting["id"]

        self.logger.info("Loaded unique coins", count=len(unique_coins))

        total_records = 0
        for coin, starlisting_id in unique_coins.items():
            records = await self.backfill_coin(coin, starlisting_id, days=days)
            total_records += records

        self.logger.info(
            "Funding backfill complete",
            total_coins=len(unique_coins),
            total_records=total_records,
        )

    async def backfill_filtered(
        self,
        coin: str | None = None,
        days: int = 365,
    ) -> None:
        """
        Backfill funding rates for specific coin(s).

        Args:
            coin: Coin filter (e.g., "BTC")
            days: Number of days to backfill
        """
        self.logger.info(
            "Starting filtered funding backfill",
            coin=coin,
            days=days,
        )

        # Load starlistings
        config_loader = ConfigLoader()
        session = await get_session()
        try:
            starlistings = await config_loader.get_active_starlistings(session)
        finally:
            await session.close()

        # Filter by coin
        if coin:
            # Find the canonical starlisting for this coin
            coin_starlisting = None
            for sl in starlistings:
                if sl["coin"] == coin:
                    coin_starlisting = sl
                    break

            if not coin_starlisting:
                self.logger.error("Coin not found in starlistings", coin=coin)
                return

            records = await self.backfill_coin(
                coin, coin_starlisting["id"], days=days
            )

            self.logger.info(
                "Filtered backfill complete",
                coin=coin,
                total_records=records,
            )
        else:
            # No filter, backfill all
            await self.backfill_all(days=days)


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Backfill historical funding rate data for Kirby"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Number of days to backfill (default: 365)",
    )
    parser.add_argument(
        "--coin",
        type=str,
        help="Coin filter (e.g., BTC)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Backfill all active coins",
    )

    args = parser.parse_args()

    # Set up logging
    setup_logging()
    logger = structlog.get_logger("kirby.scripts.backfill_funding")

    # Initialize database
    logger.info("Initializing database connection")
    await init_db()

    service = None
    try:
        # Create backfill service
        service = FundingBackfillService()

        # Run backfill
        if args.all or not args.coin:
            await service.backfill_all(days=args.days)
        else:
            await service.backfill_filtered(
                coin=args.coin,
                days=args.days,
            )

    except Exception as e:
        logger.error(
            "Funding backfill failed",
            error=str(e),
            exc_info=True,
        )
        sys.exit(1)
    finally:
        # Clean up resources
        if service and hasattr(service.info, 'ws') and service.info.ws:
            try:
                await service.info.ws.close()
                logger.debug("Closed Hyperliquid WebSocket connection")
            except Exception:
                pass  # Ignore errors during cleanup

        await close_db()
        logger.info("Database connections closed")


if __name__ == "__main__":
    asyncio.run(main())
    sys.exit(0)
