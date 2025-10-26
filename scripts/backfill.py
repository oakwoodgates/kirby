"""
Backfill historical candle data using CCXT.

Usage:
    python -m scripts.backfill --days=365
    python -m scripts.backfill --exchange=hyperliquid --coin=BTC --days=90
    python -m scripts.backfill --all
"""
import argparse
import asyncio
from datetime import datetime, timedelta
from typing import Any

import ccxt
import structlog

from src.config.loader import ConfigLoader
from src.db.connection import close_db, get_asyncpg_pool, get_session, init_db
from src.db.repositories import CandleRepository
from src.utils.helpers import normalize_candle_data, utc_now, validate_candle
from src.utils.logging import setup_logging


class BackfillService:
    """Service for backfilling historical candle data."""

    def __init__(self):
        """Initialize backfill service."""
        self.logger = structlog.get_logger("kirby.scripts.backfill")
        self.exchange_clients: dict[str, ccxt.Exchange] = {}

    def get_exchange_client(self, exchange_name: str) -> ccxt.Exchange:
        """
        Get or create CCXT exchange client.

        Args:
            exchange_name: Exchange name

        Returns:
            CCXT exchange instance
        """
        if exchange_name not in self.exchange_clients:
            # Map our exchange names to CCXT exchange IDs
            exchange_map = {
                "hyperliquid": "hyperliquid",
                # Add more exchanges as needed
            }

            ccxt_id = exchange_map.get(exchange_name)
            if not ccxt_id:
                raise ValueError(f"Exchange not supported: {exchange_name}")

            # Create exchange instance
            exchange_class = getattr(ccxt, ccxt_id)
            self.exchange_clients[exchange_name] = exchange_class({
                "enableRateLimit": True,
            })

            self.logger.info(
                "Created CCXT exchange client",
                exchange=exchange_name,
            )

        return self.exchange_clients[exchange_name]

    async def backfill_starlisting(
        self,
        starlisting: dict[str, Any],
        days: int = 365,
        batch_size: int = 500,
    ) -> int:
        """
        Backfill historical data for a starlisting.

        Args:
            starlisting: Starlisting dictionary
            days: Number of days to backfill
            batch_size: Number of candles to fetch per request

        Returns:
            Number of candles backfilled
        """
        exchange_name = starlisting["exchange"]
        coin = starlisting["coin"]
        market_type = starlisting["market_type"]
        interval = starlisting["interval"]
        starlisting_id = starlisting["id"]

        self.logger.info(
            "Starting backfill",
            exchange=exchange_name,
            coin=coin,
            market_type=market_type,
            interval=interval,
            days=days,
        )

        try:
            # Get exchange client
            exchange = self.get_exchange_client(exchange_name)

            # Construct symbol (e.g., BTC/USD:BTC for perps)
            # This varies by exchange, adjust as needed
            if market_type == "perps":
                symbol = f"{coin}/USD:{coin}"
            else:
                symbol = f"{coin}/USD"

            # Calculate timeframe
            end_time = utc_now()
            start_time = end_time - timedelta(days=days)

            # Convert to milliseconds
            since = int(start_time.timestamp() * 1000)
            end_ms = int(end_time.timestamp() * 1000)

            total_candles = 0
            candles_batch = []

            self.logger.info(
                "Fetching candles",
                symbol=symbol,
                interval=interval,
                start_time=start_time.isoformat(),
                end_time=end_time.isoformat(),
            )

            # Fetch candles in batches
            current_since = since
            while current_since < end_ms:
                try:
                    # Fetch OHLCV data
                    ohlcv = exchange.fetch_ohlcv(
                        symbol=symbol,
                        timeframe=interval,
                        since=current_since,
                        limit=batch_size,
                    )

                    if not ohlcv:
                        self.logger.info(
                            "No more candles available",
                            current_since=current_since,
                        )
                        break

                    # Process candles
                    for raw_candle in ohlcv:
                        try:
                            # Normalize candle
                            candle = normalize_candle_data(raw_candle, source="ccxt")

                            # Validate candle
                            if not validate_candle(candle):
                                self.logger.warning(
                                    "Invalid candle, skipping",
                                    candle=candle,
                                )
                                continue

                            # Add to batch
                            candle["starlisting_id"] = starlisting_id
                            candles_batch.append(candle)

                        except Exception as e:
                            self.logger.warning(
                                "Failed to process candle",
                                error=str(e),
                                raw_candle=raw_candle,
                            )

                    # Store batch if we have enough candles
                    if len(candles_batch) >= 100:
                        pool = await get_asyncpg_pool()
                        candle_repo = CandleRepository(pool)
                        stored = await candle_repo.upsert_candles(candles_batch)
                        total_candles += stored

                        self.logger.info(
                            "Stored batch",
                            batch_size=stored,
                            total=total_candles,
                        )

                        candles_batch = []

                    # Update since to last candle timestamp
                    if ohlcv:
                        current_since = ohlcv[-1][0] + 1

                    # Rate limiting (CCXT handles this, but be extra safe)
                    await asyncio.sleep(0.1)

                except ccxt.RateLimitExceeded:
                    self.logger.warning("Rate limit exceeded, waiting...")
                    await asyncio.sleep(2)
                except Exception as e:
                    self.logger.error(
                        "Error fetching batch",
                        error=str(e),
                        exc_info=True,
                    )
                    # Continue to next batch
                    await asyncio.sleep(1)

            # Store remaining candles
            if candles_batch:
                pool = await get_asyncpg_pool()
                candle_repo = CandleRepository(pool)
                stored = await candle_repo.upsert_candles(candles_batch)
                total_candles += stored

            self.logger.info(
                "Backfill complete",
                exchange=exchange_name,
                coin=coin,
                interval=interval,
                total_candles=total_candles,
            )

            return total_candles

        except Exception as e:
            self.logger.error(
                "Backfill failed",
                exchange=exchange_name,
                coin=coin,
                interval=interval,
                error=str(e),
                exc_info=True,
            )
            return 0

    async def backfill_all(self, days: int = 365) -> None:
        """
        Backfill all active starlistings.

        Args:
            days: Number of days to backfill
        """
        self.logger.info("Starting backfill for all starlistings", days=days)

        # Load starlistings
        config_loader = ConfigLoader()
        async with get_session() as session:
            starlistings = await config_loader.get_active_starlistings(session)

        self.logger.info("Loaded starlistings", count=len(starlistings))

        total_candles = 0
        for starlisting in starlistings:
            candles = await self.backfill_starlisting(starlisting, days=days)
            total_candles += candles

        self.logger.info(
            "Backfill complete",
            total_starlistings=len(starlistings),
            total_candles=total_candles,
        )

    async def backfill_filtered(
        self,
        exchange: str | None = None,
        coin: str | None = None,
        days: int = 365,
    ) -> None:
        """
        Backfill filtered starlistings.

        Args:
            exchange: Exchange filter (optional)
            coin: Coin filter (optional)
            days: Number of days to backfill
        """
        self.logger.info(
            "Starting filtered backfill",
            exchange=exchange,
            coin=coin,
            days=days,
        )

        # Load starlistings
        config_loader = ConfigLoader()
        async with get_session() as session:
            starlistings = await config_loader.get_active_starlistings(session)

        # Filter starlistings
        filtered = [
            sl
            for sl in starlistings
            if (not exchange or sl["exchange"] == exchange)
            and (not coin or sl["coin"] == coin)
        ]

        self.logger.info("Filtered starlistings", count=len(filtered))

        total_candles = 0
        for starlisting in filtered:
            candles = await self.backfill_starlisting(starlisting, days=days)
            total_candles += candles

        self.logger.info(
            "Filtered backfill complete",
            total_starlistings=len(filtered),
            total_candles=total_candles,
        )


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Backfill historical candle data for Kirby"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Number of days to backfill (default: 365)",
    )
    parser.add_argument(
        "--exchange",
        type=str,
        help="Exchange filter (e.g., hyperliquid)",
    )
    parser.add_argument(
        "--coin",
        type=str,
        help="Coin filter (e.g., BTC)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Backfill all active starlistings",
    )

    args = parser.parse_args()

    # Set up logging
    setup_logging()
    logger = structlog.get_logger("kirby.scripts.backfill")

    # Initialize database
    logger.info("Initializing database connection")
    await init_db()

    try:
        # Create backfill service
        service = BackfillService()

        # Run backfill
        if args.all or (not args.exchange and not args.coin):
            await service.backfill_all(days=args.days)
        else:
            await service.backfill_filtered(
                exchange=args.exchange,
                coin=args.coin,
                days=args.days,
            )

    except Exception as e:
        logger.error(
            "Backfill failed",
            error=str(e),
            exc_info=True,
        )
    finally:
        await close_db()
        logger.info("Database connections closed")


if __name__ == "__main__":
    asyncio.run(main())
