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

import asyncpg
import ccxt
import structlog

from src.config.loader import ConfigLoader
from src.db.connection import close_db, get_asyncpg_pool, get_session, init_db
from src.db.repositories import CandleRepository
from src.utils.helpers import normalize_candle_data, utc_now, validate_candle
from src.utils.logging import setup_logging


class BackfillService:
    """Service for backfilling historical candle data."""

    def __init__(self, database_url: str | None = None):
        """Initialize backfill service.

        Args:
            database_url: Optional custom database URL (for training database)
        """
        self.logger = structlog.get_logger("kirby.scripts.backfill")
        self.exchange_clients: dict[str, ccxt.Exchange] = {}
        self.database_url = database_url
        self._custom_pool = None

    async def get_db_pool(self) -> asyncpg.Pool:
        """Get database connection pool (custom or default).

        Returns:
            asyncpg.Pool instance
        """
        if self.database_url:
            # Create custom pool if not exists
            if not self._custom_pool:
                # Convert SQLAlchemy URL to asyncpg format
                asyncpg_url = str(self.database_url).replace("postgresql+asyncpg://", "postgresql://")
                self._custom_pool = await asyncpg.create_pool(
                    asyncpg_url,
                    min_size=5,
                    max_size=10,
                )
                self.logger.info("Created custom database pool", url=asyncpg_url)
            return self._custom_pool
        else:
            # Use default production pool
            return await get_asyncpg_pool()

    async def close(self) -> None:
        """Close custom database pool if it exists."""
        if self._custom_pool:
            await self._custom_pool.close()
            self.logger.info("Closed custom database pool")

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
                "binance": "binance",
                "bybit": "bybit",
                "okx": "okx",
            }

            ccxt_id = exchange_map.get(exchange_name)
            if not ccxt_id:
                raise ValueError(f"Exchange not supported: {exchange_name}")

            # Create exchange instance with exchange-specific config
            config = {
                "enableRateLimit": True,
            }

            # Binance-specific configuration
            if exchange_name == "binance":
                config["options"] = {
                    "defaultType": "future",  # Use futures by default for perps
                }

            exchange_class = getattr(ccxt, ccxt_id)
            self.exchange_clients[exchange_name] = exchange_class(config)

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
        quote = starlisting["quote"]
        market_type = starlisting["market_type"]
        interval = starlisting["interval"]
        starlisting_id = starlisting["id"]
        trading_pair = starlisting["trading_pair"]

        self.logger.info(
            "Starting backfill",
            exchange=exchange_name,
            trading_pair=trading_pair,
            market_type=market_type,
            interval=interval,
            days=days,
        )

        try:
            # Get exchange client
            exchange = self.get_exchange_client(exchange_name)

            # Construct symbol for CCXT (exchange-specific formats)
            ccxt_quote = quote

            # Hyperliquid uses USDC as the quote currency in CCXT
            if exchange_name == "hyperliquid" and quote == "USD":
                ccxt_quote = "USDC"

            # Construct symbol based on market type
            if market_type == "perps":
                # Format: BTC/USDT:USDT for perpetual futures
                symbol = f"{coin}/{ccxt_quote}:{ccxt_quote}"
            elif market_type == "spot":
                # Format: BTC/USDT for spot markets
                symbol = f"{coin}/{ccxt_quote}"
            else:
                # Fallback: treat as spot
                symbol = f"{coin}/{ccxt_quote}"

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
                        pool = await self.get_db_pool()
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
                pool = await self.get_db_pool()
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
        session = await get_session()
        try:
            starlistings = await config_loader.get_active_starlistings(session)
        finally:
            await session.close()

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
        session = await get_session()
        try:
            starlistings = await config_loader.get_active_starlistings(session)
        finally:
            await session.close()

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
