"""
Backfill historical candle data for training database (Binance, Bybit, etc.).

This script backfills historical data from multiple exchanges for ML training
and backtesting. Uses config/training_stars.yaml and kirby_training database.

Usage:
    python -m scripts.backfill_training --days=365
    python -m scripts.backfill_training --exchange=binance --coin=BTC --days=90

    # In Docker:
    docker compose exec collector python -m scripts.backfill_training --days=365
"""
import argparse
import asyncio

import structlog
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from scripts.backfill import BackfillService
from src.config.loader import ConfigLoader
from src.config.settings import Settings
from src.utils.logging import setup_logging


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Backfill training data for ML/backtesting"
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
        help="Exchange filter (e.g., binance)",
    )
    parser.add_argument(
        "--coin",
        type=str,
        help="Coin filter (e.g., BTC)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Backfill all active training stars",
    )

    args = parser.parse_args()

    # Set up logging
    setup_logging()
    logger = structlog.get_logger("kirby.scripts.backfill_training")

    # Get training database URL
    settings = Settings()
    training_db_url = settings.training_database_url

    if not training_db_url:
        logger.error("TRAINING_DATABASE_URL not set in .env")
        logger.info("Please add TRAINING_DATABASE_URL to your .env file")
        logger.info("Example: TRAINING_DATABASE_URL=postgresql+asyncpg://kirby:password@timescaledb:5432/kirby_training")
        return

    logger.info("Using training database", url=str(training_db_url))

    # Create direct engine and session for training database
    engine = create_async_engine(
        str(training_db_url),
        echo=False,
        pool_size=5,
        max_overflow=10,
    )

    async_session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    service = None
    try:
        # Create backfill service with training database URL
        service = BackfillService(database_url=str(training_db_url))

        # Load training stars from training database
        async with async_session_factory() as session:
            config_loader = ConfigLoader()
            starlistings = await config_loader.get_active_starlistings(session)

            # Filter if needed
            if args.exchange or args.coin:
                starlistings = [
                    sl for sl in starlistings
                    if (not args.exchange or sl["exchange"] == args.exchange)
                    and (not args.coin or sl["coin"] == args.coin)
                ]

        logger.info("Loaded training stars", count=len(starlistings))

        if not starlistings:
            logger.warning("No training stars found matching filter")
            logger.info("Did you run 'python -m scripts.sync_training_config' first?")
            return

        # Backfill each training star
        total_candles = 0
        for starlisting in starlistings:
            candles = await service.backfill_starlisting(starlisting, days=args.days)
            total_candles += candles

        logger.info(
            "Training data backfill complete",
            total_starlistings=len(starlistings),
            total_candles=total_candles,
        )

    except Exception as e:
        logger.error("Training backfill failed", error=str(e), exc_info=True)
    finally:
        # Close custom database pool if it exists
        if service:
            await service.close()
        await engine.dispose()
        logger.info("Database connections closed")


if __name__ == "__main__":
    asyncio.run(main())
