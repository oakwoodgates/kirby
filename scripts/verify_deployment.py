#!/usr/bin/env python
"""
Deployment Verification Script

Verifies that both production and training databases are set up correctly.
"""

import asyncio
import sys

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.config.settings import Settings
from src.utils.logging import setup_logging


async def verify_database(db_url: str, db_name: str) -> bool:
    """Verify a database is set up correctly.

    Args:
        db_url: Database connection URL
        db_name: Display name for the database

    Returns:
        True if database is valid, False otherwise
    """
    logger = structlog.get_logger("kirby.scripts.verify")

    try:
        # Create engine
        engine = create_async_engine(str(db_url), echo=False)

        async with engine.connect() as conn:
            # Check starlistings table
            result = await conn.execute(
                text("SELECT COUNT(*) FROM starlistings WHERE active = true")
            )
            count = result.scalar()

            logger.info(
                f"{db_name} database verified",
                active_starlistings=count,
                status="✅ OK",
            )

            # Check candles table exists
            result = await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables WHERE table_name = 'candles'"
                )
            )
            candles_exists = result.scalar() is not None

            if candles_exists:
                # Check candle count
                result = await conn.execute(text("SELECT COUNT(*) FROM candles"))
                candle_count = result.scalar()
                logger.info(
                    f"{db_name} candles table verified",
                    total_candles=candle_count,
                    status="✅ OK",
                )
            else:
                logger.error(
                    f"{db_name} candles table missing", status="❌ MISSING"
                )
                return False

        await engine.dispose()
        return True

    except Exception as e:
        logger.error(
            f"{db_name} database verification failed",
            error=str(e),
            status="❌ FAILED",
        )
        return False


async def main() -> None:
    """Main entry point."""
    setup_logging()
    logger = structlog.get_logger("kirby.scripts.verify")

    logger.info("=" * 60)
    logger.info("Kirby Deployment Verification")
    logger.info("=" * 60)

    settings = Settings()

    # Verify production database
    logger.info("\nVerifying PRODUCTION database (kirby)...")
    prod_ok = await verify_database(settings.database_url, "Production")

    # Verify training database
    logger.info("\nVerifying TRAINING database (kirby_training)...")
    training_db_url = getattr(settings, "training_database_url", None)

    if not training_db_url:
        logger.error(
            "TRAINING_DATABASE_URL not configured",
            status="❌ MISSING",
        )
        training_ok = False
    else:
        training_ok = await verify_database(training_db_url, "Training")

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Verification Summary")
    logger.info("=" * 60)

    if prod_ok and training_ok:
        logger.info("✅ All databases verified successfully!")
        logger.info("\nExpected values:")
        logger.info("  - Production: 8 starlistings (BTC, SOL × perps × 4 intervals)")
        logger.info(
            "  - Training: 24 starlistings (BTC, ETH, SOL × perps/spot × 6 intervals)"
        )
        sys.exit(0)
    else:
        logger.error("❌ Deployment verification failed!")
        logger.error("\nPlease run:")
        logger.error("  ./deploy.sh")
        logger.error("\nOr manually fix the issues above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
